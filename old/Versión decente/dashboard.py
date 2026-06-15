import os
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import json
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from storage import AnalysisStorage
from config import STOCKS

st.set_page_config(
    page_title="Investment Swarm — Análisis IT",
    page_icon="📈",
    layout="wide",
)

st.markdown("""
<style>
.metric-card {
    background: #1e1e2e; border-radius: 12px;
    padding: 1rem; margin: 0.5rem 0;
}
.decision-COMPRAR { color: #50fa7b; font-weight: bold; font-size: 1.4rem; }
.decision-VENDER  { color: #ff5555; font-weight: bold; font-size: 1.4rem; }
.decision-MANTENER{ color: #f1fa8c; font-weight: bold; font-size: 1.4rem; }
.decision-EVITAR  { color: #ff79c6; font-weight: bold; font-size: 1.4rem; }
</style>
""", unsafe_allow_html=True)

storage = AnalysisStorage()

# ── Sidebar ──
with st.sidebar:
    st.title("⚙️ Investment Swarm")
    st.caption("Sistema multi-agente local con Mistral")
    st.divider()

    selected_stocks = st.multiselect(
        "Stocks a analizar",
        options=STOCKS,
        default=["AAPL", "MSFT", "NVDA"],
    )

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        run_button = st.button("🚀 Analizar", use_container_width=True, type="primary")
    with col2:
        force_button = st.checkbox("Forzar fundamental", value=False)
    
    st.divider()
    st.caption("ℹ️ El análisis técnico+sentimiento se ejecuta diariamente. El fundamental se cachea.")

# ── Estado ──
if "results" not in st.session_state:
    st.session_state.results = []
if "last_run" not in st.session_state:
    st.session_state.last_run = None

# ── Ejecución ──
if run_button and selected_stocks:
    from crew import run_analysis
    with st.spinner(f"🤖 Analizando {len(selected_stocks)} stocks..."):
        progress = st.progress(0)
        results = []
        for i, ticker in enumerate(selected_stocks):
            st.info(f"Procesando {ticker}... ({i+1}/{len(selected_stocks)})")
            result = run_analysis([ticker], force_fundamental=force_button)
            results.extend(result)
            progress.progress((i + 1) / len(selected_stocks))
        st.session_state.results = results
        st.session_state.last_run = datetime.now().strftime("%Y-%m-%d %H:%M")
    st.success("✅ Análisis completado")
    st.rerun()

# ── Dashboard principal ──
st.title("📈 Investment Swarm — IT/Tech Analysis")
if st.session_state.last_run:
    st.caption(f"Último análisis: {st.session_state.last_run}")

results = st.session_state.results

if not results:
    st.info("👈 Selecciona stocks en el sidebar y pulsa **Analizar** para empezar.")
    st.stop()

# ── Posiciones actuales ──
st.divider()
st.subheader("💼 Mis Posiciones")
positions = storage.load_positions()

if positions:
    col1, col2, col3, col4 = st.columns(4)
    total_pnl = sum(p.get("pnl", 0) for p in positions.values() if p.get("status") == "OPEN")
    with col1:
        st.metric("Posiciones abiertas", len([p for p in positions.values() if p.get("status") == "OPEN"]))
    with col2:
        st.metric("P&L Total", f"${total_pnl:.2f}", delta=f"{(total_pnl/1000)*100:.1f}%" if total_pnl != 0 else "")
    
    st.dataframe(
        pd.DataFrame([
            {
                "Ticker": k,
                "Entry": f"${v['entry_price']:.2f}",
                "Qty": v['quantity'],
                "P&L": f"${v.get('pnl', 0):.2f}",
                "Status": v['status'],
            }
            for k, v in positions.items()
        ]),
        use_container_width=True,
    )
else:
    st.info("📌 Sin posiciones abiertas. Abre una cuando encuentres una oportunidad de COMPRA.")

# ── Tabla resumen de análisis ──
st.divider()
st.subheader("📋 Análisis actuales")

valid = [r for r in results if "decision_final" in r]

if valid:
    cols = st.columns(len(valid))
    for i, r in enumerate(valid):
        with cols[i]:
            decision = r.get("decision_final", "N/A")
            score = r.get("score_global", "—")
            color = {"COMPRAR": "🟢", "MANTENER": "🟡", "VENDER": "🔴", "EVITAR": "🟣"}.get(decision, "⚪")
            st.metric(
                label=r["ticker"],
                value=f"{color} {decision}",
                delta=f"Score: {score}/10",
            )

    # Detalle por stock
    st.divider()
    st.subheader("🔎 Análisis detallado")
    for r in valid:
        with st.expander(f"**{r['ticker']}** — {r.get('decision_final','?')} · Score {r.get('score_global','?')}/10"):
            c1, c2, c3 = st.columns(3)
            
            with c1:
                st.markdown("**Fundamental**")
                if r.get("fundamental"):
                    st.markdown(f"Score: {r['fundamental'].get('score','—')}/10")
                    st.markdown(f"Rec: {r['fundamental'].get('recomendacion','—')}")
            
            with c2:
                st.markdown("**Técnico**")
                if r.get("technical"):
                    st.markdown(f"Señal: {r['technical'].get('señal','—')}")
                    st.markdown(f"RSI: {r['technical'].get('rsi_interpretacion','—')}")
            
            with c3:
                st.markdown("**Sentimiento**")
                if r.get("sentiment"):
                    st.markdown(f"Sentimiento: {r['sentiment'].get('sentimiento','—')}")
                    st.markdown(f"Confianza: {r['sentiment'].get('confianza','—')}/10")

import pandas as pd