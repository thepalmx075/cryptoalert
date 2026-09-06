import streamlit as st
import pandas as pd
import numpy as np
import pickle
import yfinance as yf

st.set_page_config(page_title="CryptoAlert", page_icon="📉", layout="centered")

# ---------- cargar el modelo entrenado ----------
@st.cache_resource
def cargar_modelo():
    with open("cryptoalert_modelo.pkl", "rb") as f:
        return pickle.load(f)

paquete = cargar_modelo()
modelo = paquete["modelo"]
scaler = paquete["scaler"]
umbral = paquete["umbral"]
variables = paquete["variables"]

# ---------- calcular variables a partir del historial ----------
def calcular_variables(precios_df):
    df = precios_df.copy()
    df["cambio_%"] = df["precio"].pct_change() * 100
    df["media_7"] = df["precio"].rolling(7).mean()
    df["media_30"] = df["precio"].rolling(30).mean()
    df["dist_media_7"] = (df["precio"] - df["media_7"]) / df["media_7"] * 100
    df["dist_media_30"] = (df["precio"] - df["media_30"]) / df["media_30"] * 100
    df["volatilidad_7"] = df["precio"].pct_change().rolling(7).std() * 100

    delta = df["precio"].diff()
    ganancia = delta.where(delta > 0, 0).rolling(14).mean()
    perdida = -delta.where(delta < 0, 0).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + ganancia / perdida))

    df["volumen_media_7"] = df["volumen"].rolling(7).mean()
    df["volumen_relativo"] = df["volumen"] / df["volumen_media_7"]

    return df.dropna().reset_index(drop=True)

@st.cache_data(ttl=60)  # vuelve a traer datos frescos cada 60 segundos
def traer_datos(simbolo):
    datos = yf.download(simbolo, period="6mo", interval="1d", progress=False)
    datos = datos.reset_index()[["Date", "Close", "Volume"]]
    datos.columns = ["fecha", "precio", "volumen"]
    return datos

# ---------- interfaz ----------
st.title("📉 CryptoAlert")
st.caption("Sistema de alerta estadística basado en Machine Learning. No constituye asesoría financiera.")

monedas = {"Bitcoin": "BTC-USD", "Ethereum": "ETH-USD", "Solana": "SOL-USD", "BNB": "BNB-USD"}
nombre_moneda = st.selectbox("Elige una criptomoneda", list(monedas.keys()))
simbolo = monedas[nombre_moneda]

with st.spinner("Consultando precios actuales..."):
    datos_crudos = traer_datos(simbolo)
    datos = calcular_variables(datos_crudos)

if len(datos) == 0:
    st.error("No hay suficientes datos para calcular las variables todavía.")
    st.stop()

ultimo = datos.iloc[-1]
X_actual = ultimo[variables].values.reshape(1, -1)
X_actual_esc = scaler.transform(X_actual)
probabilidad = modelo.predict_proba(X_actual_esc)[0][1]

# ---------- nivel de riesgo ----------
if probabilidad >= 0.30:
    nivel, color, emoji = "RIESGO ALTO", "red", "🔴"
elif probabilidad >= umbral:
    nivel, color, emoji = "RIESGO MEDIO", "orange", "🟡"
else:
    nivel, color, emoji = "RIESGO BAJO", "green", "🟢"

st.markdown(f"### {emoji} :{color}[{nivel}]")

col1, col2, col3 = st.columns(3)
col1.metric("Precio actual", f"${ultimo['precio']:,.2f}", f"{ultimo['cambio_%']:.2f}%")
col2.metric("Confianza del modelo", f"{probabilidad*100:.1f}%")
col3.metric("Umbral de alerta", f"{umbral*100:.0f}%")

st.line_chart(datos.set_index("fecha")["precio"])

with st.expander("Ver variables técnicas usadas por el modelo"):
    st.dataframe(ultimo[variables].to_frame(name="valor"))

st.caption(f"Datos actualizados vía Yahoo Finance · última fecha disponible: {ultimo['fecha'].date()}")
st.caption("Modelo: Random Forest entrenado con datos de BTC, ETH, SOL y BNB (2 años) · validación cruzada temporal")
