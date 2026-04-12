import streamlit as st
import requests
import re
from math import inf

st.set_page_config(page_title="Scanner Híbrido (Clima + Arbitraje)", layout="wide")
st.title("🚨 Scanner Híbrido: Edge + Arbitraje (Clima)")

API_KEY = "TU_API_KEY_OPENWEATHER"

# =========================
# 1) POLYMARKET (markets)
# =========================
@st.cache_data(ttl=60)
def get_polymarket_markets(limit=80):
    url = "https://gamma-api.polymarket.com/markets"
    data = requests.get(url, timeout=20).json()

    out = []
    for m in data:
        q = (m.get("question") or "").strip()
        outcomes = m.get("outcomes") or []
        # esperamos binario [YES, NO]
        if len(outcomes) >= 2:
            try:
                yes = float(outcomes[0])
                no = float(outcomes[1])
            except:
                continue

            # filtramos solo clima/temperatura
            if "temperature" in q.lower():
                out.append({
                    "question": q,
                    "yes": yes,  # precio en dólares (0-1)
                    "no": no
                })
        if len(out) >= limit:
            break
    return out

# =========================
# 2) PARSEAR PREGUNTA
# Ej: "Will the highest temperature in London be 26°C or higher..."
# =========================
def parse_question(q):
    # threshold °C
    t = None
    m_t = re.search(r"(\d+)\s*°?\s*C", q, re.IGNORECASE)
    if m_t:
        t = int(m_t.group(1))

    # ciudad después de "in ..."
    city = None
    m_c = re.search(r"in\s+([A-Za-z\s]+)", q)
    if m_c:
        city = m_c.group(1).strip()

    return city, t

# =========================
# 3) GEO (OpenWeather)
# =========================
@st.cache_data(ttl=3600)
def get_coordinates(city):
    url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={API_KEY}"
    res = requests.get(url, timeout=20).json()
    if res:
        return res[0]["lat"], res[0]["lon"]
    return None

# =========================
# 4) ESTACIÓN + METAR (NOAA)
# =========================
@st.cache_data(ttl=3600)
def get_station(lat, lon):
    url = "https://aviationweather.gov/api/data/stationinfo?format=json"
    stations = requests.get(url, timeout=30).json()

    best = None
    best_d = inf
    for s in stations:
        if "lat" in s and "lon" in s and "icaoId" in s:
            try:
                d = (lat - float(s["lat"]))**2 + (lon - float(s["lon"]))**2
            except:
                continue
            if d < best_d:
                best_d = d
                best = s["icaoId"]
    return best

@st.cache_data(ttl=120)
def get_metar(icao):
    url = f"https://aviationweather.gov/api/data/metar?ids={icao}&format=json"
    data = requests.get(url, timeout=20).json()
    if not data:
        return None
    m = data[0]
    temp = m.get("temp")
    dew = m.get("dewp")
    hum = None
    if temp is not None and dew is not None:
        hum = 100 - 5 * (temp - dew)
    return {
        "temp": temp,
        "humidity": hum,
        "pressure": m.get("altim"),
        "raw": m.get("rawOb")
    }

# =========================
# 5) MODELO SIMPLE (prob real)
# =========================
def model_prob(d, threshold):
    if not d or d["temp"] is None:
        return None

    temp = d["temp"]
    hum = d["humidity"]
    pres = d["pressure"]

    score = 0.0

    # temperatura vs umbral
    if threshold:
        if temp >= threshold:
            score += 60
        else:
            score += max(0, (temp / threshold) * 60)

    # humedad (menos humedad => más prob de calor)
    if hum is not None:
        if hum < 60:
            score += 20
        else:
            score -= 10

    # presión (alta => estabilidad)
    if pres is not None:
        if pres > 1015:
            score += 20
        else:
            score -= 10

    return max(0, min(100, score))

# =========================
# 6) ARBITRAJE INTRA (YES+NO)
# =========================
def arb_intra(yes, no):
    total = (yes + no) * 100  # en %
    # precios están en 0-1, sum ideal = 1.0 (100%)
    if (yes + no) < 1.0:
        edge = (1.0 - (yes + no)) * 100
        return True, edge  # oportunidad
    return False, (yes + no - 1.0) * 100

# =========================
# MAIN
# =========================
markets = get_polymarket_markets()

results = []

for m in markets:
    q = m["question"]
    yes_p = m["yes"] * 100
    no_p  = m["no"] * 100

    city, threshold = parse_question(q)
    if not city or not threshold:
        continue

    coords = get_coordinates(city)
    if not coords:
        continue

    icao = get_station(*coords)
    if not icao:
        continue

    metar = get_metar(icao)
    if not metar:
        continue

    real = model_prob(metar, threshold)
    if real is None:
        continue

    # EDGE (modelo vs mercado)
    edge_model = real - yes_p

    # ARBITRAJE (YES+NO)
    is_arb, arb_edge = arb_intra(m["yes"], m["no"])

    results.append({
        "q": q,
        "city": city,
        "thr": threshold,
        "icao": icao,
        "temp": metar["temp"],
        "real": real,
        "yes": yes_p,
        "no": no_p,
        "edge_model": edge_model,
        "is_arb": is_arb,
        "arb_edge": arb_edge
    })

# =========================
# UI
# =========================
st.subheader("🏆 Top oportunidades (ordenadas)")

# orden: primero arbitraje, luego mayor edge de modelo
results = sorted(results, key=lambda x: (not x["is_arb"], -abs(x["edge_model"])))

for r in results[:20]:
    st.markdown("---")
    st.write(f"📍 **{r['city']}** | Umbral: **{r['thr']}°C** | ICAO: {r['icao']}")
    st.write(f"🌡️ Temp actual: {r['temp']}°C")

    c1, c2, c3 = st.columns(3)
    c1.metric("🧠 Prob REAL", f"{round(r['real'],1)}%")
    c2.metric("📈 YES mercado", f"{round(r['yes'],1)}%")
    c3.metric("📉 NO mercado", f"{round(r['no'],1)}%")

    # Señal modelo
    if r["edge_model"] > 10:
        st.success(f"🟢 EDGE MODELO → BUY YES | +{round(r['edge_model'],1)}%")
    elif r["edge_model"] < -10:
        st.error(f"🔴 EDGE MODELO → BUY NO | {round(r['edge_model'],1)}%")
    else:
        st.warning(f"⚪ Sin edge claro | {round(r['edge_model'],1)}%")

    # Señal arbitraje
    if r["is_arb"]:
        st.info(f"💰 ARBITRAJE → YES+NO < 100% | Edge ≈ +{round(r['arb_edge'],2)}% (casi seguro)")

st.caption("Fuente de precios: Polymarket (gamma-api). Datos clima: NOAA METAR + OpenWeather (geo).")
