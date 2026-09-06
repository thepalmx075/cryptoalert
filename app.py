import streamlit as st
import pandas as pd
import numpy as np
import pickle
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import time

st.set_page_config(page_title="CryptoAlert", page_icon="📉", layout="centered")

# ============ PANTALLA DE BIENVENIDA (solo una vez por sesión) ============
if "splash_shown" not in st.session_state:
    splash = st.empty()
    with splash.container():
        st.markdown("""
        <style>
        @keyframes gradientMove {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        @keyframes fadeInUp {
            0% { opacity: 0; transform: translateY(16px); }
            100% { opacity: 1; transform: translateY(0); }
        }
        .splash-wrap {
            height: 70vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #041024, #0B3D91, #1E90FF, #7FC7FF);
            background-size: 300% 300%;
            animation: gradientMove 3s ease infinite;
            border-radius: 24px;
        }
        .splash-title {
            font-family: 'Inter', system-ui, sans-serif;
            font-size: 42px;
            font-weight: 800;
            color: white;
            letter-spacing: 1px;
            animation: fadeInUp 1s ease;
            text-shadow: 0 4px 24px rgba(0,0,0,0.35);
        }
        .splash-sub {
            font-family: monospace;
            color: rgba(255,255,255,0.85);
            font-size: 13px;
            margin-top: 8px;
            animation: fadeInUp 1.3s ease;
        }
        </style>
        <div class="splash-wrap">
            <div class="splash-title">📉 CryptoAlert</div>
            <div class="splash-sub">iniciando modelo de riesgo…</div>
        </div>
        """, unsafe_allow_html=True)
    time.sleep(1.7)
    splash.empty()
    st.session_state.splash_shown = True

# ============ ESTILO GLOBAL: vidrio esmerilado estilo iOS ============
st.markdown("""
<style>
.stApp {
    background: radial-gradient(circle at 15% 5%, #10233F 0%, #060A12 60%);
}
[data-testid="stMetric"], .glass-card, .stDataFrame, div[data-testid="stExpander"] {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.14) !important;
    border-radius: 18px !important;
    backdrop-filter: blur(18px) saturate(160%);
    -webkit-backdrop-filter: blur(18px) saturate(160%);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.10), 0 4px 18px rgba(0,0,0,0.25);
}
[data-testid="stMetric"] { padding: 14px 10px; }
[data-testid="stMetricLabel"] { color: #9AA5B1 !important; }
div[data-baseweb="select"] > div, .stRadio > div, .stButton > button, .stDownloadButton > button {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.16) !important;
    border-radius: 14px !important;
    backdrop-filter: blur(12px);
    color: #EDF1F4 !important;
}
.tech-title {
    font-family: monospace;
    letter-spacing: 1px;
    color: #8891A0;
    font-size: 12px;
    text-transform: uppercase;
}
.mini-coin-card {
    border-radius: 16px;
    padding: 12px 14px;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.14);
    backdrop-filter: blur(14px);
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

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

MONEDAS = {"Bitcoin": "BTC-USD", "Ethereum": "ETH-USD", "Solana": "SOL-USD", "BNB": "BNB-USD"}

# ---------- funciones de datos ----------
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

@st.cache_data(ttl=60)
def traer_datos(simbolo):
    datos = yf.download(simbolo, period="6mo", interval="1d", progress=False)
    datos = datos.reset_index()
    datos.columns = [c[0] if isinstance(c, tuple) else c for c in datos.columns]
    datos = datos[["Date", "Open", "High", "Low", "Close", "Volume"]]
    datos.columns = ["fecha", "apertura", "maximo", "minimo", "precio", "volumen"]
    return datos

@st.cache_data(ttl=300)
def traer_info_moneda(simbolo):
    try:
        info = yf.Ticker(simbolo).info
        return {
            "market_cap": info.get("marketCap"),
            "max_52sem": info.get("fiftyTwoWeekHigh"),
            "min_52sem": info.get("fiftyTwoWeekLow"),
        }
    except Exception:
        return {}

def fmt_grande(numero):
    if numero is None:
        return "N/D"
    for unidad, divisor in [("B", 1e9), ("M", 1e6), ("K", 1e3)]:
        if numero >= divisor:
            return f"${numero/divisor:,.2f}{unidad}"
    return f"${numero:,.2f}"

def calcular_probabilidades(df):
    X_esc = scaler.transform(df[variables].values)
    return modelo.predict_proba(X_esc)[:, 1]

def nivel_riesgo(prob):
    if prob >= 0.30:
        return "RIESGO ALTO", "#EF4444", "🔴"
    elif prob >= umbral:
        return "RIESGO MEDIO", "#F59E0B", "🟡"
    return "RIESGO BAJO", "#10B981", "🟢"

# ============ ENCABEZADO ============
st.title("📉 CryptoAlert")
st.caption("Sistema de alerta estadística basado en Machine Learning · datos reales en vivo")

# ============ ACCIÓN: comparar todas las monedas de un vistazo ============
with st.spinner("Cargando panorama general..."):
    resumen = {}
    for nombre, simb in MONEDAS.items():
        d = calcular_variables(traer_datos(simb))
        p = calcular_probabilidades(d)[-1]
        resumen[nombre] = {"precio": d.iloc[-1]["precio"], "cambio": d.iloc[-1]["cambio_%"], "riesgo": p}

st.markdown('<div class="tech-title">Panorama general — las 4 monedas</div>', unsafe_allow_html=True)
cols_resumen = st.columns(4)
for i, (nombre, r) in enumerate(resumen.items()):
    _, color_hex, emoji = nivel_riesgo(r["riesgo"])
    with cols_resumen[i]:
        st.markdown(f"""
        <div class="mini-coin-card">
            <div style="font-size:12px;color:#9AA5B1;">{nombre}</div>
            <div style="font-size:16px;font-weight:700;">${r['precio']:,.2f}</div>
            <div style="font-size:11px;color:{'#10B981' if r['cambio']>=0 else '#EF4444'};">{r['cambio']:+.2f}%</div>
            <div style="font-size:18px;margin-top:4px;">{emoji}</div>
        </div>
        """, unsafe_allow_html=True)

st.divider()

# ============ SELECCIÓN Y ACCIONES ============
col_sel, col_btn = st.columns([3, 1])
with col_sel:
    nombre_moneda = st.selectbox("Elige una criptomoneda para el detalle", list(MONEDAS.keys()))
with col_btn:
    st.write("")
    st.write("")
    if st.button("🔄 Actualizar"):
        st.cache_data.clear()
        st.rerun()

simbolo = MONEDAS[nombre_moneda]
datos = calcular_variables(traer_datos(simbolo))
info_extra = traer_info_moneda(simbolo)
ultimo = datos.iloc[-1]
probabilidades_historicas = calcular_probabilidades(datos)
probabilidad = probabilidades_historicas[-1]
cambio_7d = (ultimo["precio"] - datos.iloc[-8]["precio"]) / datos.iloc[-8]["precio"] * 100 if len(datos) > 8 else None
nivel, color_hex, emoji = nivel_riesgo(probabilidad)

st.markdown(f"""
<div class="glass-card" style="border-radius:18px;padding:18px 20px;margin:10px 0 18px 0; background:{color_hex}1F !important; border-color:{color_hex}55 !important;">
  <div class="tech-title">Nivel de riesgo detectado</div>
  <div style="font-size: 26px; font-weight: 800; color: {color_hex};">{emoji} {nivel}</div>
  <div style="color:#B7BCC4; font-size: 13px; margin-top:4px;">
    {nombre_moneda} · actualizado {datetime.now().strftime('%H:%M:%S')}
  </div>
</div>
""", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Precio actual", f"${ultimo['precio']:,.2f}", f"{ultimo['cambio_%']:.2f}% (24h)")
col2.metric("Variación 7 días", f"{cambio_7d:.2f}%" if cambio_7d is not None else "N/D")
col3.metric("Confianza del modelo", f"{probabilidad*100:.1f}%")
col4.metric("RSI actual", f"{ultimo['rsi']:.0f}")

col5, col6, col7 = st.columns(3)
col5.metric("Cap. de mercado", fmt_grande(info_extra.get("market_cap")))
col6.metric("Máximo 52 sem.", f"${info_extra['max_52sem']:,.2f}" if info_extra.get("max_52sem") else "N/D")
col7.metric("Mínimo 52 sem.", f"${info_extra['min_52sem']:,.2f}" if info_extra.get("min_52sem") else "N/D")

# ============ GRÁFICA ============
tipo_grafica = st.radio("Tipo de gráfica", ["Velas", "Línea"], horizontal=True)
fig = go.Figure()
if tipo_grafica == "Velas":
    fig.add_trace(go.Candlestick(
        x=datos["fecha"], open=datos["apertura"], high=datos["maximo"],
        low=datos["minimo"], close=datos["precio"],
        increasing_line_color="#10B981", decreasing_line_color="#EF4444", name=nombre_moneda
    ))
else:
    fig.add_trace(go.Scatter(x=datos["fecha"], y=datos["precio"], mode="lines",
                              line=dict(color="#2DD4BF", width=2), name=nombre_moneda))

alertas_idx = np.where(probabilidades_historicas >= umbral)[0]
if len(alertas_idx) > 0:
    fig.add_trace(go.Scatter(
        x=datos["fecha"].iloc[alertas_idx], y=datos["precio"].iloc[alertas_idx],
        mode="markers", marker=dict(color="#F59E0B", size=8, symbol="triangle-down"),
        name="Alerta del modelo"
    ))

fig.update_layout(
    template="plotly_dark", height=380, margin=dict(l=10, r=10, t=30, b=10),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    xaxis_rangeslider_visible=False, legend=dict(orientation="h", y=1.1)
)
st.plotly_chart(fig, use_container_width=True)
st.caption(f"🔺 {len(alertas_idx)} días de los últimos {len(datos)} donde el modelo hubiera emitido alerta (umbral {umbral*100:.0f}%)")

# ============ MÁS ACCIONES ============
with st.expander("📊 ¿Qué variables pesan más en la predicción del modelo?"):
    importancias = pd.Series(modelo.feature_importances_, index=variables).sort_values()
    fig_imp = go.Figure(go.Bar(x=importancias.values, y=importancias.index, orientation="h", marker_color="#38BDF8"))
    fig_imp.update_layout(template="plotly_dark", height=280, margin=dict(l=10, r=10, t=10, b=10),
                           paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_imp, use_container_width=True)
    st.caption("Mientras más larga la barra, más influye esa variable en la decisión del modelo.")

with st.expander("🔬 Ver variables técnicas del día actual"):
    st.dataframe(ultimo[variables].to_frame(name="valor"), use_container_width=True)

with st.expander("⬇️ Descargar historial de datos (CSV)"):
    csv = datos.to_csv(index=False).encode("utf-8")
    st.download_button("Descargar CSV", csv, file_name=f"{simbolo}_historial.csv", mime="text/csv")

with st.expander("📋 Resumen para compartir"):
    resumen_txt = (
        f"CryptoAlert — {nombre_moneda}\n"
        f"Precio: ${ultimo['precio']:,.2f} ({ultimo['cambio_%']:+.2f}% 24h)\n"
        f"Riesgo: {nivel} ({probabilidad*100:.1f}% de confianza)\n"
        f"RSI: {ultimo['rsi']:.0f} · Actualizado: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    st.code(resumen_txt, language=None)

st.divider()
st.caption(f"Datos vía Yahoo Finance · última fecha disponible: {ultimo['fecha'].date()}")
st.caption("Modelo: Random Forest entrenado con BTC, ETH, SOL y BNB (2 años) · validación cruzada temporal · umbral optimizado por F1-score")
st.caption("⚠️ Herramienta educativa. No constituye asesoría financiera.")
