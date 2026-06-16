"""
DASHBOARD - PAPER TRADING (MEJORADO - PASO 3)
==============================================

Mejoras agregadas:
1. Operaciones manuales (compra/venta con inputs de cantidad)
2. Columnas de origin (AUTO / MANUAL_TELEGRAM / MANUAL_DASHBOARD)
3. Columnas de bot_opinion (SÍ / NO)
4. Coloreo visual según tipo de operación

Ejecutar con:  streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from paper_trading_engine import (
    PaperTradingEngine,
    OPERATION_ORIGIN_AUTO,
    OPERATION_ORIGIN_MANUAL_DASHBOARD,
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


def origin_badge(origin: str) -> str:
    """Muestra badge con icono según origen de operación."""
    badges = {
        OPERATION_ORIGIN_AUTO: "🤖 AUTO",
        OPERATION_ORIGIN_MANUAL_DASHBOARD: "👤 DASHBOARD",
        "MANUAL_TELEGRAM": "💬 TELEGRAM",
    }
    return badges.get(origin, origin)


def bot_opinion_badge(opinion: str) -> str:
    """Muestra badge con color según opinión del bot."""
    if opinion == "SÍ":
        return "✅ SÍ"
    elif opinion == "NO":
        return "❌ NO"
    return opinion


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

    # ── Acciones de trading automático ──
    st.subheader("Acciones automáticas")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**🔍 Escanear (modo automático)**")
        st.caption(
            "Revisa stop loss / take profit en posiciones abiertas y solo "
            "abre nuevas posiciones si hay señal técnica + fundamental + "
            "sentimiento favorable."
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
            "watchlist sin posición abierta."
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

    # ── OPERACIONES MANUALES (NUEVO - PASO 3) ──
    st.subheader("Operaciones manuales")

    col_buy, col_sell = st.columns(2)

    # Compra manual
    with col_buy:
        st.markdown("#### 🛒 Compra manual")
        buy_ticker = st.selectbox("Ticker a comprar", options=watchlist if watchlist else ["—"], key="buy_ticker", label_visibility="collapsed")
        buy_qty = st.number_input("Cantidad", min_value=1, value=10, step=1, key="buy_qty")

        if st.button("💰 Comprar", type="primary", use_container_width=True, disabled=(buy_ticker == "—")):
            try:
                price = engine.get_current_price(buy_ticker)
                if not price:
                    st.error(f"No se pudo obtener precio para {buy_ticker}")
                else:
                    result = engine.execute_operation_manual(
                        ticker=buy_ticker,
                        action="BUY",
                        quantity=buy_qty,
                        price=price,
                        origin=OPERATION_ORIGIN_MANUAL_DASHBOARD,
                        note=f"Compra manual desde dashboard: {buy_qty} acciones"
                    )

                    if result["success"]:
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(result["message"])
            except Exception as e:
                st.error(f"Error: {e}")

    # Venta manual
    with col_sell:
        st.markdown("#### 📊 Venta manual")
        positions = list(engine.state["positions"].keys())
        sell_ticker = st.selectbox("Ticker a vender", options=positions if positions else ["—"], key="sell_ticker", label_visibility="collapsed")

        max_qty = 0
        if sell_ticker != "—" and sell_ticker in engine.state["positions"]:
            max_qty = sum(lot["qty"] for lot in engine.state["positions"][sell_ticker])

        sell_qty = st.number_input("Cantidad", min_value=1, max_value=max(1, max_qty), value=min(10, max_qty) if max_qty > 0 else 1, step=1, key="sell_qty")

        if st.button("💵 Vender", type="primary", use_container_width=True, disabled=(sell_ticker == "—")):
            try:
                price = engine.get_current_price(sell_ticker)
                if not price:
                    st.error(f"No se pudo obtener precio para {sell_ticker}")
                else:
                    result = engine.execute_operation_manual(
                        ticker=sell_ticker,
                        action="SELL",
                        quantity=sell_qty,
                        price=price,
                        origin=OPERATION_ORIGIN_MANUAL_DASHBOARD,
                        note=f"Venta manual desde dashboard: {sell_qty} acciones"
                    )

                    if result["success"]:
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(result["message"])
            except Exception as e:
                st.error(f"Error: {e}")

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
                "P&L": fmt_money(p["pnl"]) if "pnl" in p else "—",
                "% P&L": fmt_pct(p["pnl_pct"]) if "pnl_pct" in p else "—",
            })

        df_pos = pd.DataFrame(pos_rows)
        st.dataframe(df_pos, use_container_width=True, hide_index=True)

    st.divider()

    # ── Histórico de operaciones (MEJORADO - PASO 3) ──
    st.subheader("Histórico de operaciones")

    if not engine.state["trade_history"]:
        st.info("Sin operaciones aún.")
    else:
        # Preparar datos del histórico con NUEVAS columnas
        history_rows = []
        for trade in engine.state["trade_history"][-50:]:  # Últimas 50
            action = trade.get("action", "?")
            action_icon = "🟢" if action == "BUY" else "🔴"

            origin = trade.get("origin", "?")
            bot_opinion = trade.get("bot_opinion", "?")

            history_rows.append({
                "Fecha": fmt_ago(trade.get("date", "")),
                "Acción": action_icon + " " + action,
                "Ticker": trade.get("ticker", "?"),
                "Cantidad": trade.get("quantity", 0),
                "Precio": fmt_money(trade.get("price", 0)),
                "Importe": fmt_money(trade.get("amount", 0)),
                "Comisión": fmt_money(trade.get("fee", 0)),
                "Origin": origin_badge(origin),
                "Bot Opinion": bot_opinion_badge(bot_opinion),
                "P&L": fmt_money(trade.get("pnl", 0)) if "pnl" in trade else "—",
                "Razón": trade.get("reason", "Manual") if action == "SELL" else trade.get("conviction", "—"),
            })

        df_history = pd.DataFrame(history_rows)
        st.dataframe(df_history, use_container_width=True, hide_index=True)

        # Resumen de operaciones por tipo
        st.markdown("#### 📊 Resumen por origen")
        origin_counts = {}
        for trade in engine.state["trade_history"]:
            origin = trade.get("origin", "UNKNOWN")
            origin_counts[origin] = origin_counts.get(origin, 0) + 1

        res_rows = []
        for origin, count in origin_counts.items():
            res_rows.append({"Origin": origin_badge(origin), "Cantidad": count})

        if res_rows:
            df_res = pd.DataFrame(res_rows)
            st.dataframe(df_res, use_container_width=True, hide_index=True)

        # Resumen de bot_opinion
        st.markdown("#### 🤖 Análisis: Bot opinion")
        opinion_counts = {}
        for trade in engine.state["trade_history"]:
            opinion = trade.get("bot_opinion", "?")
            opinion_counts[opinion] = opinion_counts.get(opinion, 0) + 1

        opinion_rows = []
        for opinion, count in opinion_counts.items():
            opinion_rows.append({"Opinion": bot_opinion_badge(opinion), "Cantidad": count})

        if opinion_rows:
            df_opinion = pd.DataFrame(opinion_rows)
            st.dataframe(df_opinion, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────
# TAB 2: ANÁLISIS FUNDAMENTAL
# ─────────────────────────────────────────────────────────────

with tab_fundamental:
    st.subheader("Análisis Fundamental (on-demand)")

    col_f1, col_f2 = st.columns([3, 1])
    with col_f1:
        fund_ticker = st.text_input("Ticker para análisis fundamental", placeholder="Ej: MSFT", label_visibility="collapsed", key="fund_ticker_input")
    with col_f2:
        if st.button("🔍 Analizar", use_container_width=True, key="btn_analyze_fundamental"):
            if fund_ticker.strip():
                with st.spinner(f"Analizando {fund_ticker}..."):
                    engine.run_fundamental_analysis(fund_ticker.upper(), force=False)
                st.rerun()

    # Listado de análisis disponibles
    if engine.state["fundamental_analyses"]:
        st.markdown("#### 📋 Análisis disponibles")

        fund_rows = []
        for ticker, entry in engine.state["fundamental_analyses"].items():
            data = entry.get("data", {})
            score = data.get("score", "?")
            timestamp = entry.get("timestamp", "")
            ago = fmt_ago(timestamp) if timestamp else "—"

            fund_rows.append({
                "Ticker": ticker,
                "Score": f"{score}/10",
                "Recomendación": data.get("recommendation", "?"),
                "Confianza": data.get("confidence", "?"),
                "Antigüedad": ago,
            })

        df_fund = pd.DataFrame(fund_rows)
        st.dataframe(df_fund, use_container_width=True, hide_index=True)

        # Expandibles con detalles
        for ticker, entry in engine.state["fundamental_analyses"].items():
            data = entry.get("data", {})
            with st.expander(f"📄 {ticker} - Detalles"):
                st.markdown(f"**Score:** {data.get('score', '?')}/10")
                st.markdown(f"**Recomendación:** {data.get('recommendation', '?')}")
                st.markdown(f"**Confianza:** {data.get('confidence', '?')}")
                st.markdown(f"**Risk Level:** {data.get('risk_level', '?')}")
                st.markdown(f"**Summary:**\n{data.get('summary', '?')}")

                col_refresh, col_force = st.columns(2)
                with col_refresh:
                    if st.button(f"🔄 Renovar {ticker}", use_container_width=True, key=f"btn_refresh_fund_{ticker}"):
                        with st.spinner(f"Renoando análisis de {ticker}..."):
                            engine.run_fundamental_analysis(ticker.upper(), force=True)
                        st.rerun()


# ─────────────────────────────────────────────────────────────
# TAB 3: ANÁLISIS DE SENTIMIENTO
# ─────────────────────────────────────────────────────────────

with tab_sentiment:
    st.subheader("Análisis de Sentimiento (on-demand)")

    col_s1, col_s2 = st.columns([3, 1])
    with col_s1:
        sent_ticker = st.text_input("Ticker para análisis de sentimiento", placeholder="Ej: MSFT", label_visibility="collapsed", key="sent_ticker_input")
    with col_s2:
        if st.button("🔍 Analizar", use_container_width=True, key="btn_analyze_sentiment"):
            if sent_ticker.strip():
                with st.spinner(f"Analizando {sent_ticker}..."):
                    engine.run_sentiment_analysis(sent_ticker.upper(), force=False)
                st.rerun()

    # Listado de análisis disponibles
    if engine.state["sentiment_analyses"]:
        st.markdown("#### 📋 Análisis disponibles")

        sent_rows = []
        for ticker, entry in engine.state["sentiment_analyses"].items():
            data = entry.get("data", {})
            sentimiento = data.get("sentimiento", "?")
            timestamp = entry.get("timestamp", "")
            ago = fmt_ago(timestamp) if timestamp else "—"

            sent_rows.append({
                "Ticker": ticker,
                "Sentimiento": sentimiento,
                "Confianza": data.get("confianza", "?"),
                "Antigüedad": ago,
            })

        df_sent = pd.DataFrame(sent_rows)
        st.dataframe(df_sent, use_container_width=True, hide_index=True)

        # Expandibles con detalles
        for ticker, entry in engine.state["sentiment_analyses"].items():
            data = entry.get("data", {})
            with st.expander(f"📄 {ticker} - Detalles"):
                st.markdown(f"**Sentimiento:** {data.get('sentimiento', '?')}")
                st.markdown(f"**Confianza:** {data.get('confianza', '?')}")
                st.markdown(f"**Catalizadores:** {data.get('catalizadores', '?')}")
                st.markdown(f"**Red Flags:** {data.get('red_flags', '?')}")
                st.markdown(f"**Noticias clave:**\n{data.get('noticias_clave', '?')}")

                col_refresh, col_force = st.columns(2)
                with col_refresh:
                    if st.button(f"🔄 Renovar {ticker}", use_container_width=True, key=f"btn_refresh_sent_{ticker}"):
                        with st.spinner(f"Renovando análisis de {ticker}..."):
                            engine.run_sentiment_analysis(ticker.upper(), force=True)
                        st.rerun()