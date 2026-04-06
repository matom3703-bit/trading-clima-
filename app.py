import streamlit as st
import requests

st.set_page_config(page_title="Trading Climático PRO", layout="wide")

st.title("📊 Trading Climático PRO (METAR + NOAA)")

# --- INPUT ---
airport = st.text_input("Código aeropuerto (ej: MMMX CDMX)", "MMMX")

# --- FUNCION METAR (NOAA) ---
def get_metar(airport):
    url = f"https://aviationweather.gov/api/data/metar?ids={airport}&format=json"
    try:
        data = requests.get(url).json()
        if len(data) == 0:
            return None
        
        metar = data[0]
        
        return {
            "temp": metar.get("temp"),
            "dewpoint": metar.get("dewp"),
            "humidity": calc_humidity(metar.get("temp"), metar.get("dewp")),
            "pressure": metar.get("altim"),
            "raw": metar.get("rawOb")
        }
    except:
        return None

# --- CALCULAR HUMEDAD ---
def calc_humidity(temp, dew):
    if temp is None or dew is None:
        return None
    return round(100 - 5 * (temp - dew), 2)

# --- SEÑALES ---
def generate_signal(data):
    if data["humidity"] and data["pressure"]:
        if data["humidity"] > 75 and data["pressure"] < 1010:
            return "🔴 SHORT LLUVIA"
        elif data["temp"] > 25:
            return "🟢 LONG CALOR"
        else:
            return "⚪ NEUTRAL"
    return "Sin datos"

# --- PROBABILIDAD LLUVIA ---
def rain_probability(humidity):
    if humidity:
        return min(int(humidity * 0.8), 100)
    return 0

# --- MAIN ---
data = get_metar(airport)

if data:
    col1, col2, col3 = st.columns(3)

    col1.metric("🌡️ Temperatura", f"{data['temp']} °C")
    col2.metric("💧 Humedad", f"{data['humidity']} %")
    col3.metric("📉 Presión", f"{data['pressure']} hPa")

    st.subheader("⚡ Señal de Trading")
    signal = generate_signal(data)
    st.success(signal)

    st.subheader("🌧️ Probabilidad de lluvia")
    prob = rain_probability(data["humidity"])
    st.progress(prob)
    st.write(f"{prob}%")

    st.subheader("📡 METAR crudo")
    st.code(data["raw"])

else:
    st.error("No se pudieron obtener datos. Verifica el código del aeropuerto.")