"""
DASHBOARD - PAPER TRADING
==========================

Interfaz Streamlit con 3 secciones:

1. 💰 Paper Trading
   - Resumen de cartera (cash, valor, P&L, régimen actual)
   - Gestión de la watchlist (añadir/quitar tickers)
   - Botones: "Escanear" (modo auto) e "Invertir ahora" (modo invest_now)
   - Tabla de posiciones abiertas
   - Histórico de operaciones

2. 📊 Análisis Fundamental
   - Pedir análisis de un ticker nuevo
   - Listado de tickers ya analizados (score, fecha, antigüedad)
   - Ver informe completo + botón "Renovar"

3. 📰 Análisis de Sentimiento
   - Igual que el fundamental, pero para sentimiento de mercado

Ejecutar con:  streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from paper_trading_engine import (
    PaperTradingEngine,
    FUNDAMENTAL_CACHE_DAYS,
    SENTIMENT_CACHE_HOURS,
)

st.set_page_config(page_title="Investment Swarm - Paper Trading", page_icon="📈", layout="wide")

# ── Inicialización del motor (persistente entre recargas) ──
if "engine" not in st.session_state:
    st.session_state.engine = PaperTradingEngine(initial_capital=5000.0)

engine: PaperTradingEngine = st.session_state.engine


# ═══════════════════════════════════════════════════════════════
# HELPERS DE FORMATO
# ═══════════════════════════════════════════════════════════════

def fmt_money(x: float) -> str:
    return f"${x:,.2f}"


def fmt_pct(x: float) -> str:
    sign = "+" if x >= 0 else ""
    return f"{sign}{x:.2f}%"


def fmt_ago(timestamp_iso: str) -> str:
    """Devuelve un texto legible de antigüedad ('hace 2h', 'hace 3 días')."""
    ts = datetime.fromisoformat(timestamp_iso)
    delta = datetime.now() - ts
    if delta.days > 0:
        return f"hace {delta.days}d"
    hours = delta.seconds // 3600
    if hours > 0:
        return f"hace {hours}h"
    minutes = (delta.seconds % 3600) // 60
    return f"hace {minutes}min"


def regime_badge(regime: str) -> str:
    icons = {
        "BULLISH": "🟢 ALCISTA",
        "NEUTRAL": "🟡 NEUTRAL",
        "BEAR_RALLY": "🟠 REBOTE BAJISTA",
        "BEARISH": "🔴 BAJISTA",
    }
    return icons.get(regime, regime)


# ═══════════════════════════════════════════════════════════════
# SIDEBAR: resumen rápido siempre visible
# ═══════════════════════════════════════════════════════════════

with st.sidebar:
    st.header("📈 Investment Swarm")
    st.caption("Paper Trading Dashboard")

    summary = engine.get_portfolio_summary()
    regime = engine.get_regime()

    st.metric("Valor total", fmt_money(summary["total_value"]), fmt_pct(summary["return_pct"]))
    st.metric("Cash disponible", fmt_money(summary["cash"]))
    st.metric("En posiciones", fmt_money(summary["positions_value"]))

    st.markdown(f"**Régimen actual:** {regime_badge(regime)}")

    if summary["trading_paused"]:
        st.error("🛑 Circuit breaker activo: compras pausadas")

    if summary["last_scan_at"]:
        st.caption(f"Último escaneo: {fmt_ago(summary['last_scan_at'])}")

    st.divider()

    if st.button("⚠️ Reiniciar paper trading", use_container_width=True):
        st.session_state["confirm_reset"] = True

    if st.session_state.get("confirm_reset"):
        st.warning("Esto borra cash, posiciones e histórico (mantiene los análisis cacheados).")
        col_a, col_b = st.columns(2)
        if col_a.button("Sí, reiniciar", type="primary", use_container_width=True):
            engine.reset()
            st.session_state["confirm_reset"] = False
            st.rerun()
        if col_b.button("Cancelar", use_container_width=True):
            st.session_state["confirm_reset"] = False


# ═══════════════════════════════════════════════════════════════
# TABS PRINCIPALES
# ═══════════════════════════════════════════════════════════════

tab_trading, tab_fundamental, tab_sentiment = st.tabs([
    "💰 Paper Trading",
    "📊 Análisis Fundamental",
    "📰 Análisis de Sentimiento",
])


# ─────────────────────────────────────────────────────────────
# TAB 1: PAPER TRADING
# ─────────────────────────────────────────────────────────────

with tab_trading:
    st.subheader("Watchlist")

    col_add1, col_add2 = st.columns([3, 1])
    with col_add1:
        new_ticker = st.text_input("Añadir ticker a la watchlist", key="new_ticker_input", label_visibility="collapsed", placeholder="Ej: MSFT")
    with col_add2:
        if st.button("➕ Añadir", use_container_width=True):
            if new_ticker.strip():
                engine.add_ticker(new_ticker)
                st.rerun()

    watchlist = engine.state["watchlist"]

    if not watchlist:
        st.info("Tu watchlist está vacía. Añade tickers arriba para empezar.")
    else:
        # Mostrar watchlist con estado de análisis y opción de quitar
        rows = []
        for t in watchlist:
            fund = engine.get_fundamental(t)
            sent = engine.get_sentiment(t)
            rows.append({
                "Ticker": t,
                "Fundamental": f"{fund['score']:.1f}/10" if fund else "—",
                "Sentimiento": sent["data"]["sentimiento"] if sent else "—",
                "En cartera": "✅" if t in engine.state["positions"] else "",
            })

        df_watch = pd.DataFrame(rows)
        st.dataframe(df_watch, use_container_width=True, hide_index=True)

        remove_col1, remove_col2 = st.columns([3, 1])
        with remove_col1:
            ticker_to_remove = st.selectbox("Quitar de la watchlist", options=["—"] + watchlist, label_visibility="collapsed")
        with remove_col2:
            if st.button("🗑️ Quitar", use_container_width=True):
                if ticker_to_remove != "—":
                    engine.remove_ticker(ticker_to_remove)
                    st.rerun()

    st.divider()

    # ── Acciones de trading ──
    st.subheader("Acciones")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**🔍 Escanear (modo automático)**")
        st.caption(
            "Revisa stop loss / take profit en posiciones abiertas y solo "
            "abre nuevas posiciones si hay señal técnica + fundamental + "
            "sentimiento favorable (igual que en producción)."
        )
        if st.button("Escanear ahora", use_container_width=True, disabled=not watchlist):
            with st.spinner("Analizando watchlist..."):
                actions = engine.scan(mode="auto")
            st.session_state["last_actions"] = actions
            st.rerun()

    with col2:
        st.markdown("**🚀 Invertir ahora**")
        st.caption(
            "Revisa salidas igual que el modo automático, pero además "
            "reparte el cash disponible AHORA entre los tickers de la "
            "watchlist sin posición abierta, a precio de mercado, sin "
            "esperar una señal técnica de entrada óptima."
        )
        if st.button("Invertir ahora", type="primary", use_container_width=True, disabled=not watchlist):
            with st.spinner("Ejecutando..."):
                actions = engine.scan(mode="invest_now")
            st.session_state["last_actions"] = actions
            st.rerun()

    # ── Resultado del último escaneo ──
    if "last_actions" in st.session_state:
        actions = st.session_state["last_actions"]
        with st.expander(f"📋 Resultado del último escaneo (régimen: {regime_badge(actions['regime'])})", expanded=True):
            for note in actions.get("notes", []):
                st.write(note)

            if actions["buys"]:
                st.markdown("**Compras ejecutadas:**")
                for b in actions["buys"]:
                    extra = " (invertir ahora)" if b.get("note") == "invertir_ahora" else ""
                    st.write(f"🟢 {b['ticker']}: {b['quantity']} @ {fmt_money(b['price'])} "
                             f"({fmt_money(b['amount'])}, convicción {b['conviction']}){extra}")

            if actions["sells"]:
                st.markdown("**Ventas ejecutadas:**")
                for s in actions["sells"]:
                    st.write(f"🔴 {s['ticker']}: {s['quantity']} @ {fmt_money(s['price'])} "
                             f"— {s['reason']} (P&L: {fmt_money(s['pnl'])}, {fmt_pct(s['pnl_pct'])})")

            if actions["skipped"]:
                with st.expander(f"Tickers descartados ({len(actions['skipped'])})"):
                    for sk in actions["skipped"]:
                        st.write(f"⊘ {sk['ticker']}: {sk['reason']}")

            if not actions["buys"] and not actions["sells"]:
                st.write("Sin operaciones en este escaneo.")

    st.divider()

    # ── Posiciones abiertas ──
    st.subheader("Posiciones abiertas")

    if not summary["positions"]:
        st.info("No hay posiciones abiertas.")
    else:
        pos_rows = []
        for p in summary["positions"]:
            pos_rows.append({
                "Ticker": p["ticker"] + (" 🛡️" if p["is_hedge"] else ""),
                "Cantidad": p["qty"],
                "Precio entrada": fmt_money(p["entry_price"]),
                "Precio actual": fmt_money(p["current_price"]) if p["current_price"] else "—",
                "Valor": fmt_money(p["value"]),
                "P&L": fmt_money(p["pnl"]),
                "P&L %": fmt_pct(p["pnl_pct"]),
                "Convicción": p["conviction"],
                "Régimen entrada": p["entry_regime"],
            })
        st.dataframe(pd.DataFrame(pos_rows), use_container_width=True, hide_index=True)

    st.divider()

    # ── Histórico de operaciones ──
    st.subheader("Histórico de operaciones")

    history = engine.state["trade_history"]
    if not history:
        st.info("Sin operaciones todavía.")
    else:
        hist_rows = []
        for t in reversed(history[-50:]):  # últimas 50, más recientes primero
            hist_rows.append({
                "Fecha": datetime.fromisoformat(t["date"]).strftime("%Y-%m-%d %H:%M"),
                "Ticker": t["ticker"],
                "Acción": t["action"],
                "Cantidad": t["quantity"],
                "Precio": fmt_money(t["price"]),
                "Importe": fmt_money(t["amount"]),
                "Comisión": fmt_money(t.get("fee", 0)),
                "P&L": fmt_money(t["pnl"]) if "pnl" in t else "—",
                "Motivo / Convicción": t.get("reason") or t.get("conviction", "—"),
                "Régimen": t.get("regime", "—"),
            })
        st.dataframe(pd.DataFrame(hist_rows), use_container_width=True, hide_index=True)

        total_costs = summary["total_transaction_costs"]
        st.caption(f"💸 Comisiones totales pagadas: {fmt_money(total_costs)}")


# ─────────────────────────────────────────────────────────────
# TAB 2: ANÁLISIS FUNDAMENTAL
# ─────────────────────────────────────────────────────────────

with tab_fundamental:
    st.subheader("Solicitar nuevo análisis")

    col1, col2 = st.columns([3, 1])
    with col1:
        fund_ticker_input = st.text_input(
            "Ticker", key="fund_ticker_input", label_visibility="collapsed",
            placeholder="Ej: NVDA",
        )
    with col2:
        fund_analyze_clicked = st.button("📊 Analizar", use_container_width=True, key="fund_analyze_btn")

    if fund_analyze_clicked and fund_ticker_input.strip():
        with st.spinner(f"Ejecutando análisis fundamental de {fund_ticker_input.upper()}... (puede tardar 1-2 min)"):
            engine.run_fundamental_analysis(fund_ticker_input, force=False)
        st.rerun()

    st.divider()
    st.subheader("Análisis disponibles")

    fundamentals = engine.state["fundamental_analyses"]

    if not fundamentals:
        st.info("Todavía no se ha analizado ningún ticker.")
    else:
        for ticker, entry in sorted(fundamentals.items()):
            data = entry["data"]
            stale = engine.is_fundamental_stale(ticker)
            score = entry.get("score", data.get("score"))

            header = f"{ticker} — Score: {score}/10 — {fmt_ago(entry['timestamp'])}"
            if stale:
                header += f" ⚠️ (caché > {FUNDAMENTAL_CACHE_DAYS} días)"

            with st.expander(header):
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Score", f"{score}/10")
                col_b.metric("Confianza", f"{data.get('confidence', '?')}%")
                col_c.metric("Recomendación", data.get("recommendation", "—"))

                if data.get("risk_level"):
                    st.write(f"**Nivel de riesgo:** {data['risk_level']}")

                st.write(f"**Resumen:** {data.get('summary', '—')}")

                if data.get("error"):
                    st.error(f"Error en el análisis: {data['error']}")

                st.caption(f"Analizado el {datetime.fromisoformat(entry['timestamp']).strftime('%Y-%m-%d %H:%M')}")

                if st.button("🔄 Renovar análisis", key=f"renew_fund_{ticker}"):
                    with st.spinner(f"Renovando análisis fundamental de {ticker}..."):
                        engine.run_fundamental_analysis(ticker, force=True)
                    st.rerun()


# ─────────────────────────────────────────────────────────────
# TAB 3: ANÁLISIS DE SENTIMIENTO
# ─────────────────────────────────────────────────────────────

with tab_sentiment:
    st.subheader("Solicitar nuevo análisis")

    col1, col2 = st.columns([3, 1])
    with col1:
        sent_ticker_input = st.text_input(
            "Ticker", key="sent_ticker_input", label_visibility="collapsed",
            placeholder="Ej: NVDA",
        )
    with col2:
        sent_analyze_clicked = st.button("📰 Analizar", use_container_width=True, key="sent_analyze_btn")

    if sent_analyze_clicked and sent_ticker_input.strip():
        with st.spinner(f"Ejecutando análisis de sentimiento de {sent_ticker_input.upper()}... (puede tardar 1-2 min)"):
            result = engine.run_sentiment_analysis(sent_ticker_input, force=False)
        if result["data"].get("error") == "module_not_found":
            st.error(result["data"]["resumen"])
        else:
            st.rerun()

    st.divider()
    st.subheader("Análisis disponibles")

    sentiments = engine.state["sentiment_analyses"]

    if not sentiments:
        st.info("Todavía no se ha analizado ningún ticker.")
    else:
        sentiment_icons = {"POSITIVO": "🟢", "NEUTRO": "🟡", "NEGATIVO": "🔴"}

        for ticker, entry in sorted(sentiments.items()):
            data = entry["data"]
            stale = engine.is_sentiment_stale(ticker)
            icon = sentiment_icons.get(data.get("sentimiento"), "⚪")

            header = f"{ticker} — {icon} {data.get('sentimiento', '—')} — {fmt_ago(entry['timestamp'])}"
            if stale:
                header += f" ⚠️ (caché > {SENTIMENT_CACHE_HOURS}h)"

            with st.expander(header):
                st.metric("Confianza", f"{data.get('confianza', '?')}%")

                if data.get("catalizadores_positivos"):
                    st.markdown("**Catalizadores positivos:**")
                    for c in data["catalizadores_positivos"]:
                        st.write(f"- {c}")

                if data.get("catalizadores_negativos"):
                    st.markdown("**Catalizadores negativos:**")
                    for c in data["catalizadores_negativos"]:
                        st.write(f"- {c}")

                if data.get("red_flags"):
                    st.markdown("**🚩 Red flags:**")
                    for f in data["red_flags"]:
                        st.write(f"- {f}")

                if data.get("noticias_clave"):
                    st.markdown("**Noticias clave:**")
                    for n in data["noticias_clave"]:
                        st.write(f"- {n}")

                st.write(f"**Resumen:** {data.get('resumen', '—')}")

                if data.get("error"):
                    st.error(f"Error en el análisis: {data['error']}")

                st.caption(f"Analizado el {datetime.fromisoformat(entry['timestamp']).strftime('%Y-%m-%d %H:%M')}")

                if st.button("🔄 Renovar análisis", key=f"renew_sent_{ticker}"):
                    with st.spinner(f"Renovando análisis de sentimiento de {ticker}..."):
                        engine.run_sentiment_analysis(ticker, force=True)
                    st.rerun()