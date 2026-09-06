import streamlit as st
import pandas as pd
import numpy as np
import pickle
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import time

st.set_page_config(page_title="CryptoAlert", page_icon=":material/monitoring:", layout="centered")

# ---------- sistema de iconos propio (sin emojis) ----------
def svg_logo(size=36):
    """Marca de CryptoAlert: línea de precio en zigzag + el mismo triángulo de alerta
    que se usa en la gráfica principal, para que el logo y los datos hablen el mismo idioma visual."""
    return f"""<svg width="{size}" height="{size}" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
<rect x="1" y="1" width="38" height="38" rx="11" fill="url(#logoGrad)"/>
<rect x="1" y="1" width="38" height="38" rx="11" stroke="rgba(255,255,255,0.16)"/>
<defs>
<linearGradient id="logoGrad" x1="2" y1="2" x2="38" y2="38" gradientUnits="userSpaceOnUse">
<stop stop-color="#123A6B"/><stop offset="1" stop-color="#1E63C9"/>
</linearGradient>
</defs>
<path d="M7 25 L13 15 L18 21 L23 11 L29 18 L34 9" stroke="#EAF2FF" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M19 5 L27 5 L23 11 Z" fill="#F59E0B"/>
</svg>"""

_GAUGE_ANGULOS = {"bajo": (5.5, 12.25), "medio": (12, 8.5), "alto": (18.5, 12.25)}

def risk_icon(riesgo_key, color, size=20):
    """Gauge de riesgo: la aguja apunta a la izquierda, arriba o a la derecha según la severidad,
    en vez de un punto de color plano — comunica la escala, no solo la categoría."""
    nx, ny = _GAUGE_ANGULOS[riesgo_key]
    return f"""<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
<path d="M4 16.5a8 8 0 0 1 16 0" stroke="{color}" stroke-width="2" stroke-linecap="round" opacity="0.30"/>
<line x1="12" y1="16.5" x2="{nx}" y2="{ny}" stroke="{color}" stroke-width="2.2" stroke-linecap="round"/>
<circle cx="12" cy="16.5" r="1.7" fill="{color}"/>
</svg>"""

_LINE_ICON_PATHS = {
    "target": '<circle cx="12" cy="12" r="7" stroke="{c}" stroke-width="1.8"/><circle cx="12" cy="12" r="3" stroke="{c}" stroke-width="1.8"/><circle cx="12" cy="12" r="0.9" fill="{c}"/>',
    "alert-triangle": '<path d="M12 4 L21 20 H3 Z" stroke="{c}" stroke-width="1.8" stroke-linejoin="round"/><line x1="12" y1="10" x2="12" y2="14.5" stroke="{c}" stroke-width="1.8" stroke-linecap="round"/><circle cx="12" cy="17" r="1" fill="{c}"/>',
    "info": '<circle cx="12" cy="12" r="8.5" stroke="{c}" stroke-width="1.8"/><line x1="12" y1="10.5" x2="12" y2="16" stroke="{c}" stroke-width="1.8" stroke-linecap="round"/><circle cx="12" cy="7.5" r="1" fill="{c}"/>',
}

def line_icon(nombre, size=15, color="#8891A0"):
    inner = _LINE_ICON_PATHS[nombre].format(c=color)
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'xmlns="http://www.w3.org/2000/svg" style="vertical-align:-3px;margin-right:6px;" aria-hidden="true">{inner}</svg>')

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
            <div style="margin-bottom:14px; animation: fadeInUp 0.8s ease;">""" + svg_logo(56) + """</div>
            <div class="splash-title">CryptoAlert</div>
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

try:
    paquete = cargar_modelo()
    modelo = paquete["modelo"]
    scaler = paquete["scaler"]
    umbral = paquete["umbral"]
    variables = paquete["variables"]
except Exception as e:
    st.error(f"No se pudo cargar el modelo entrenado (cryptoalert_modelo.pkl). Detalle: {e}", icon=":material/error:")
    st.stop()

MONEDAS = {"Bitcoin": "BTC-USD", "Ethereum": "ETH-USD", "Solana": "SOL-USD", "BNB": "BNB-USD"}
RANGOS = {"1 mes": 30, "3 meses": 90, "6 meses": 180, "1 año": 365}
CAIDA_UMBRAL = -3.0  # % de caída que el modelo intenta anticipar (debe coincidir con el entrenamiento)

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
def traer_datos(simbolo, period="2y"):
    try:
        datos = yf.download(simbolo, period=period, interval="1d", progress=False)
    except Exception:
        return pd.DataFrame(columns=["fecha", "apertura", "maximo", "minimo", "precio", "volumen"])
    if datos is None or datos.empty:
        return pd.DataFrame(columns=["fecha", "apertura", "maximo", "minimo", "precio", "volumen"])
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

def nivel_riesgo(prob, umbral_ref=umbral):
    if prob >= 0.30:
        return "RIESGO ALTO", "#EF4444", "alto"
    elif prob >= umbral_ref:
        return "RIESGO MEDIO", "#F59E0B", "medio"
    return "RIESGO BAJO", "#10B981", "bajo"

def backtest_precision_real(datos_completo, probabilidades_completo, umbral, caida_umbral=CAIDA_UMBRAL):
    """Compara cada alerta histórica del modelo contra lo que realmente pasó al día siguiente."""
    alertas = probabilidades_completo[:-1] >= umbral
    resultado_real = datos_completo["cambio_%"].values[1:] <= caida_umbral
    total_alertas = int(alertas.sum())
    if total_alertas == 0:
        return None
    aciertos = int((alertas & resultado_real).sum())
    return {
        "total_alertas": total_alertas,
        "aciertos": aciertos,
        "precision": aciertos / total_alertas * 100,
    }

def variable_mas_influyente(datos_completo, variables, modelo):
    """Aproximación simple (no SHAP real): combina qué tan atípico está el valor de hoy
    respecto a su historial, con la importancia global de esa variable en el modelo."""
    medias = datos_completo[variables].mean()
    stds = datos_completo[variables].std().replace(0, np.nan)
    hoy = datos_completo[variables].iloc[-1]
    z = ((hoy - medias) / stds).fillna(0)
    importancias = pd.Series(modelo.feature_importances_, index=variables)
    contribucion = (z.abs() * importancias).sort_values(ascending=False)
    top = contribucion.index[0]
    return top, z[top], contribucion

# ============ ENCABEZADO ============
st.markdown(f"""
<div style="display:flex;align-items:center;gap:14px;margin-bottom:2px;">
    {svg_logo(38)}
    <div style="font-size:32px;font-weight:800;color:#EDF1F4;letter-spacing:-0.5px;">CryptoAlert</div>
</div>
""", unsafe_allow_html=True)
st.caption("Sistema de alerta estadística basado en Machine Learning · datos reales en vivo")

# ============ ACCIÓN: comparar todas las monedas de un vistazo ============
with st.spinner("Cargando panorama general..."):
    resumen = {}
    monedas_con_error = []
    for nombre, simb in MONEDAS.items():
        try:
            d = calcular_variables(traer_datos(simb))
            if d.empty:
                raise ValueError("sin datos suficientes")
            p = calcular_probabilidades(d)[-1]
            resumen[nombre] = {"precio": d.iloc[-1]["precio"], "cambio": d.iloc[-1]["cambio_%"], "riesgo": p}
        except Exception:
            monedas_con_error.append(nombre)

if monedas_con_error:
    st.warning(f"No se pudo cargar en este momento: {', '.join(monedas_con_error)}. Intenta actualizar en unos segundos.")

st.markdown('<div class="tech-title">Panorama general — las 4 monedas</div>', unsafe_allow_html=True)
cols_resumen = st.columns(4)
for i, (nombre, simb) in enumerate(MONEDAS.items()):
    with cols_resumen[i]:
        if nombre not in resumen:
            st.markdown(f"""
            <div class="mini-coin-card">
                <div style="font-size:12px;color:#9AA5B1;">{nombre}</div>
                <div style="font-size:13px;color:#8891A0;margin-top:8px;">No disponible</div>
            </div>
            """, unsafe_allow_html=True)
            continue
        r = resumen[nombre]
        _, color_hex, riesgo_key = nivel_riesgo(r["riesgo"])
        st.markdown(f"""
        <div class="mini-coin-card">
            <div style="font-size:12px;color:#9AA5B1;">{nombre}</div>
            <div style="font-size:16px;font-weight:700;">${r['precio']:,.2f}</div>
            <div style="font-size:11px;color:{'#10B981' if r['cambio']>=0 else '#EF4444'};">{r['cambio']:+.2f}%</div>
            <div style="margin-top:6px;display:flex;justify-content:center;">{risk_icon(riesgo_key, color_hex, 20)}</div>
        </div>
        """, unsafe_allow_html=True)

st.divider()

# ============ SELECCIÓN Y ACCIONES ============
col_sel, col_rango, col_btn = st.columns([2.4, 1.6, 1])
with col_sel:
    nombre_moneda = st.selectbox("Elige una criptomoneda para el detalle", list(MONEDAS.keys()))
with col_rango:
    rango_sel = st.selectbox("Rango de tiempo", list(RANGOS.keys()), index=2)
with col_btn:
    st.write("")
    st.write("")
    if st.button("Actualizar", icon=":material/refresh:"):
        st.cache_data.clear()
        st.rerun()

simbolo = MONEDAS[nombre_moneda]
datos_completo = calcular_variables(traer_datos(simbolo))  # histórico amplio, para backtest y probabilidades
if datos_completo.empty or len(datos_completo) < 35:
    st.error(
        f"No hay suficientes datos históricos disponibles para {nombre_moneda} en este momento "
        "(puede ser una falla temporal de Yahoo Finance). Intenta con Actualizar en unos segundos.",
        icon=":material/error:"
    )
    st.stop()

info_extra = traer_info_moneda(simbolo)
ultimo = datos_completo.iloc[-1]
probabilidades_completo = calcular_probabilidades(datos_completo)
probabilidad = probabilidades_completo[-1]
cambio_7d = (ultimo["precio"] - datos_completo.iloc[-8]["precio"]) / datos_completo.iloc[-8]["precio"] * 100 if len(datos_completo) > 8 else None

# recorte según el rango elegido, solo para lo que se muestra en pantalla
dias_rango = RANGOS[rango_sel]
datos = datos_completo.tail(dias_rango).reset_index(drop=True)
probabilidades_historicas = probabilidades_completo[-dias_rango:]

st.markdown('<div class="tech-title">Ajusta el umbral de alerta</div>', unsafe_allow_html=True)
umbral_usuario = st.slider(
    "¿Qué tan sensible quieres que sea el modelo?",
    min_value=0.05, max_value=0.60, value=round(float(umbral), 2), step=0.01, format="%.2f",
    help="Probabilidad mínima para que el modelo marque una alerta. Más bajo = más alertas (y más falsas alarmas). Más alto = menos alertas, pero más selectivas."
)
st.caption(f"Umbral óptimo encontrado por el modelo (F1-score): **{umbral*100:.0f}%** · Estás usando: **{umbral_usuario*100:.0f}%**")

nivel, color_hex, riesgo_key = nivel_riesgo(probabilidad, umbral_usuario)

st.markdown(f"""
<div class="glass-card" style="border-radius:18px;padding:18px 20px;margin:10px 0 18px 0; background:{color_hex}1F !important; border-color:{color_hex}55 !important;">
  <div class="tech-title">Nivel de riesgo detectado</div>
  <div style="display:flex;align-items:center;gap:10px;margin-top:2px;">
    {risk_icon(riesgo_key, color_hex, 30)}
    <div style="font-size: 26px; font-weight: 800; color: {color_hex};">{nivel}</div>
  </div>
  <div style="color:#B7BCC4; font-size: 13px; margin-top:4px;">
    {nombre_moneda} · actualizado {datetime.now().strftime('%H:%M:%S')}
  </div>
</div>
""", unsafe_allow_html=True)

top_var, top_z, _ = variable_mas_influyente(datos_completo, variables, modelo)
direccion = "por encima" if top_z >= 0 else "por debajo"
st.markdown(
    f'<div style="font-size:13px;color:#B7BCC4;margin:-6px 0 14px 0;">'
    f'{line_icon("target", 14, "#7FC7FF")}'
    f'La señal que más influye hoy en {nombre_moneda} es <b>{top_var}</b> '
    f'({abs(top_z):.1f} desviaciones estándar {direccion} de su promedio histórico). '
    f'<span style="color:#6E7684;font-style:italic;">Aproximación simplificada, no un cálculo formal tipo SHAP.</span>'
    f'</div>',
    unsafe_allow_html=True
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Precio actual", f"${ultimo['precio']:,.2f}", f"{ultimo['cambio_%']:.2f}% (24h)")
col2.metric("Variación 7 días", f"{cambio_7d:.2f}%" if cambio_7d is not None else "N/D")
col3.metric("Confianza del modelo", f"{probabilidad*100:.1f}%")
col4.metric("RSI actual", f"{ultimo['rsi']:.0f}")

max_52 = info_extra.get("max_52sem")
min_52 = info_extra.get("min_52sem")
dist_max = (ultimo["precio"] - max_52) / max_52 * 100 if max_52 else None
dist_min = (ultimo["precio"] - min_52) / min_52 * 100 if min_52 else None

col5, col6, col7, col8 = st.columns(4)
col5.metric("Cap. de mercado", fmt_grande(info_extra.get("market_cap")))
col6.metric("Volumen 24h", fmt_grande(ultimo["volumen"]))
col7.metric("Máximo 52 sem.", f"${max_52:,.2f}" if max_52 else "N/D", f"{dist_max:.1f}%" if dist_max is not None else None)
col8.metric("Mínimo 52 sem.", f"${min_52:,.2f}" if min_52 else "N/D", f"{dist_min:.1f}%" if dist_min is not None else None)

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

alertas_idx = np.where(probabilidades_historicas >= umbral_usuario)[0]
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
st.markdown(
    f'<div style="font-size:13px;color:#B7BCC4;">'
    f'{line_icon("alert-triangle", 14, "#F59E0B")}'
    f'{len(alertas_idx)} días de los últimos {len(datos)} donde el modelo hubiera emitido alerta '
    f'(umbral {umbral_usuario*100:.0f}%)</div>',
    unsafe_allow_html=True
)

bt = backtest_precision_real(datos_completo, probabilidades_completo, umbral_usuario)
if bt:
    st.markdown(f"""
    <div class="glass-card" style="border-radius:16px;padding:14px 18px;margin:8px 0;">
      <div class="tech-title">Precisión real con umbral {umbral_usuario*100:.0f}% (backtest histórico)</div>
      <div style="font-size:15px;margin-top:4px;">
        De <b>{bt['total_alertas']}</b> alertas que se hubieran emitido en todo el historial disponible,
        <b>{bt['aciertos']}</b> fueron seguidas por una caída real ≥{abs(CAIDA_UMBRAL):.0f}% al día siguiente:
        <b style="color:{'#10B981' if bt['precision']>=50 else '#F59E0B'};">{bt['precision']:.1f}% de precisión real</b>.
      </div>
      <div style="font-size:12px;color:#8891A0;margin-top:6px;">
        Baja el umbral y verás más alertas (con menor precisión); súbelo y verás menos alertas, pero más certeras.
      </div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.caption("No hubo alertas suficientes en el historial disponible para calcular precisión real.")

# ============ MÁS ACCIONES ============
with st.expander("Comparar con otra moneda", icon=":material/compare_arrows:"):
    opciones_comparar = [m for m in MONEDAS if m != nombre_moneda]
    moneda_comparar = st.selectbox("Comparar rendimiento contra:", opciones_comparar, key="comparar_moneda")
    simbolo_comp = MONEDAS[moneda_comparar]
    datos_comp = calcular_variables(traer_datos(simbolo_comp)).tail(dias_rango).reset_index(drop=True)

    if datos_comp.empty:
        st.warning(f"No se pudieron cargar datos de {moneda_comparar} en este momento. Intenta actualizar en unos segundos.")
    else:
        base_actual = datos["precio"].iloc[0]
        base_comp = datos_comp["precio"].iloc[0]
        rendimiento_actual = (datos["precio"] / base_actual - 1) * 100
        rendimiento_comp = (datos_comp["precio"] / base_comp - 1) * 100

        fig_comp = go.Figure()
        fig_comp.add_trace(go.Scatter(x=datos["fecha"], y=rendimiento_actual, mode="lines",
                                       line=dict(color="#2DD4BF", width=2), name=nombre_moneda))
        fig_comp.add_trace(go.Scatter(x=datos_comp["fecha"], y=rendimiento_comp, mode="lines",
                                       line=dict(color="#F472B6", width=2), name=moneda_comparar))
        fig_comp.update_layout(
            template="plotly_dark", height=320, margin=dict(l=10, r=10, t=30, b=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", y=1.12), yaxis_title="% desde inicio del periodo"
        )
        st.plotly_chart(fig_comp, use_container_width=True)
        st.caption(f"Rendimiento normalizado (% desde el inicio del periodo de {rango_sel}) para comparar de forma justa, sin importar la escala de precio de cada moneda.")

with st.expander("¿Qué variables pesan más en la predicción del modelo?", icon=":material/bar_chart:"):
    importancias = pd.Series(modelo.feature_importances_, index=variables).sort_values()
    fig_imp = go.Figure(go.Bar(x=importancias.values, y=importancias.index, orientation="h", marker_color="#38BDF8"))
    fig_imp.update_layout(template="plotly_dark", height=280, margin=dict(l=10, r=10, t=10, b=10),
                           paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_imp, use_container_width=True)
    st.caption("Mientras más larga la barra, más influye esa variable en la decisión del modelo.")

with st.expander("Ver variables técnicas del día actual", icon=":material/biotech:"):
    st.dataframe(ultimo[variables].to_frame(name="valor"), use_container_width=True)

with st.expander("Descargar historial de datos (CSV)", icon=":material/download:"):
    csv = datos.to_csv(index=False).encode("utf-8")
    st.download_button("Descargar CSV", csv, file_name=f"{simbolo}_historial.csv", mime="text/csv")

with st.expander("Resumen para compartir", icon=":material/content_copy:"):
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
st.markdown(
    f'<div style="font-size:13px;color:#8891A0;">{line_icon("info", 14, "#8891A0")}'
    f'Herramienta educativa. No constituye asesoría financiera.</div>',
    unsafe_allow_html=True
)
