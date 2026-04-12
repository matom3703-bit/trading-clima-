for m in markets:

    q = m["question"]
    yes_p = m["yes"] * 100
    no_p  = m["no"] * 100

    city, threshold = parse_question(q)

    st.markdown("---")
    st.write(f"🧾 Mercado: {q}")
    st.write(f"📈 YES: {round(yes_p,2)}% | 📉 NO: {round(no_p,2)}%")

    if not city or not threshold:
        st.warning("⚠️ No se pudo extraer ciudad o temperatura")
        continue

    st.write(f"📍 Ciudad detectada: {city} | Umbral: {threshold}°C")

    coords = get_coordinates(city)

    if not coords:
        st.warning("⚠️ No se encontraron coordenadas")
        continue

    lat, lon = coords

    airport = get_station(lat, lon)

    if not airport:
        st.warning("⚠️ No se encontró aeropuerto")
        continue

    st.write(f"✈️ Aeropuerto: {airport}")

    metar = get_metar(airport)

    if not metar:
        st.warning("⚠️ No hay datos METAR")
        continue

    real = model_prob(metar, threshold)

    if real is None:
        st.warning("⚠️ No se pudo calcular modelo")
        continue

    edge = real - yes_p

    st.write(f"🧠 Probabilidad real: {round(real,2)}%")
    st.write(f"⚡ Edge: {round(edge,2)}%")

    if edge > 10:
        st.success("🟢 BUY YES")
    elif edge < -10:
        st.error("🔴 BUY NO")
    else:
        st.info("⚪ Sin oportunidad clara")

    if (m["yes"] + m["no"]) < 1:
        arb = (1 - (m["yes"] + m["no"])) * 100
        st.success(f"💰 ARBITRAJE DETECTADO: +{round(arb,2)}%")
