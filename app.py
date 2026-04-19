import streamlit as st
import requests
import re

st.set_page_config(page_title="Scanner Climático PRO", layout="wide")

st.title("🚨 Scanner Climático (Polymarket + Clima REAL)")

API_KEY = "TU_API_KEY_OPENWEATHER"

# =========================
# 1. POLYMARKET
# =========================
@st.cache_data(ttl=60)
def get_markets():
    url = "https://gamma-api.polymarket.com/markets"
    try:
        data = requests.get(url, timeout=10).json()
    except:
        return []

    markets = []

    for m in data:
        q = m.get("question", "")
        outcomes = m.get("outcomes", [])

        if len(outcomes) >= 2:
            try:
                yes = float(outcomes[0])
                no = float(outcomes[1])
            except:
                continue

            markets.append({
                "question": q,
                "yes": yes,
                "no": no
            })

    return markets[:20]

# =========================
# 2. PARSEAR TEXTO
# =========================
def parse(q):
    city = None
    temp = None

    match_temp = re.search(r"(\d+)\s*°?\s*[CF]", q)
    if match_temp:
        temp = int(match_temp.group(1))

    match_city = re.search(r"in\s+([A-Za-z\s]+)", q)
    if match_city:
        city = match_city.group(1).strip()

    return city, temp

# =========================
# 3. GEO
# =========================
def get_coords(city):
    try:
        url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={API_KEY}"
        res = requests.get(url, timeout=10).json()
        if res:
            return res[0]["lat"], res[0]["lon"]
    except:
        return None
    return None

# =========================
# 4. ESTACIÓN
# =========================
def get_station(lat, lon):
    try:
        url = "https://aviationweather.gov/api/data/stationinfo?format=json"
        stations = requests.get(url, timeout=10).json()
    except:
        return None

    closest = None
    min_dist = 999999

    for s in stations:
        if "lat" in s and "lon" in s and "icaoId" in s:
            try:
                dist = (lat - float(s["lat"]))**2 + (lon - float(s["lon"]))**2
                if dist < min_dist:
                    min_dist = dist
                    closest = s["icaoId"]
            except:
                continue

    return closest

# =========================
# 5. METAR
# =========================
def get_metar(airport):
    try:
        url = f"https://aviationweather.gov/api/data/metar?ids={airport}&format=json"
        data = requests.get(url, timeout=10).json()

        if not data:
            return None

        m = data[0]
        temp = m.get("temp")
        dew = m.get("dewp")

        humidity = None
        if temp and dew:
            humidity = 100 - 5 * (temp - dew)

        return temp, humidity, m.get("altim")
    except:
        return None

# =========================
# 6. MODELO
# =========================
def model(temp, humidity, pressure, threshold):
    if temp is None or threshold is None:
        return None

    score = 0

    if temp > threshold:
        score += 60
    else:
        score += (temp / threshold) * 60

    if humidity:
        if humidity < 60:
            score += 20
        else:
            score -= 10

    if pressure:
        if pressure > 1015:
            score += 20
        else:
            score -= 10

    return max(0, min(100, score))

# =========================
# MAIN
# =========================
markets = get_markets()

if not markets:
    st.error("No se pudieron cargar mercados")
else:
    for m in markets:

        st.markdown("---")

        q = m["question"]
        yes = m["yes"] * 100
        no = m["no"] * 100

        st.write(f"🧾 {q}")
        st.write(f"📈 YES: {round(yes,2)}% | 📉 NO: {round(no,2)}%")

        city, threshold = parse(q)

        if not city or not threshold:
            st.warning("No se pudo detectar ciudad o temperatura")
            continue

        st.write(f"📍 Ciudad: {city} | Umbral: {threshold}")

        coords = get_coords(city)

        if not coords:
            st.warning("No coords")
            continue

        lat, lon = coords

        airport = get_station(lat, lon)

        if not airport:
            st.warning("No aeropuerto")
            continue

        st.write(f"✈️ Aeropuerto: {airport}")

        metar = get_metar(airport)

        if not metar:
            st.warning("No METAR")
            continue

        temp, humidity, pressure = metar

        real = model(temp, humidity, pressure, threshold)

        if real is None:
            st.warning("No modelo")
            continue

        edge = real - yes

        st.write(f"🌡️ Temp actual: {temp}")
        st.write(f"🧠 Prob real: {round(real,2)}%")
        st.write(f"⚡ Edge: {round(edge,2)}%")

        if edge > 10:
            st.success("🟢 BUY YES")
        elif edge < -10:
            st.error("🔴 BUY NO")
        else:
            st.info("⚪ Sin ventaja")

        if (m["yes"] + m["no"]) < 1:
            arb = (1 - (m["yes"] + m["no"])) * 100
            st.success(f"💰 ARBITRAJE: +{round(arb,2)}%")
