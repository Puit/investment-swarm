"""
DASHBOARD v3 - DUAL MODE + ANÁLISIS INTEGRADO
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

# Setup
load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))

from trading.paper_trading_engine import PaperTradingEngine, OPERATION_ORIGIN_MANUAL_DASHBOARD
from core.analysis_storage import AnalysisStorage
from core.analysis_schemas import (
    parse_fundamental_analysis,
    parse_sentiment_analysis,
    parse_technical_analysis
)
from agents.fundamental_agent import create_fundamental_agent
from agents.sentiment_agent import create_sentiment_agent
from agents.technical_agent import create_technical_agent
from crewai import Task, Crew, Process
import re

from brokers.trading212_broker import Trading212Broker

st.set_page_config(page_title="Investment Swarm", page_icon="📈", layout="wide")

# ═══════════════════════════════════════════════════════════════
# INICIALIZACIÓN
# ═══════════════════════════════════════════════════════════════

if "paper_engine" not in st.session_state:
    st.session_state.paper_engine = PaperTradingEngine(initial_capital=5000.0)

# T212 Paper Trading (cuenta demo)
if "t212_paper_broker" not in st.session_state:
    _b = Trading212Broker(account_type="paper")
    _ok = _b.connect() if _b.api_secret else False
    st.session_state.t212_paper_broker    = _b
    st.session_state.t212_paper_connected = _ok

# T212 Live Trading (cuenta real)
if "t212_live_broker" not in st.session_state:
    _b = Trading212Broker(account_type="live")
    _ok = _b.connect() if _b.api_secret else False
    st.session_state.t212_live_broker    = _b
    st.session_state.t212_live_connected = _ok

paper_engine         = st.session_state.paper_engine
t212_paper_broker    = st.session_state.t212_paper_broker
t212_paper_connected = st.session_state.t212_paper_connected
t212_live_broker     = st.session_state.t212_live_broker
t212_live_connected  = st.session_state.t212_live_connected

# Compat aliases usados en código heredado
t212_broker    = t212_paper_broker
t212_connected = t212_paper_connected
live_broker    = t212_live_broker
live_connected = t212_live_connected

# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def fmt_money(x: float) -> str:
    return f"${x:,.2f}"

def pnl_color(x: float) -> str:
    return "🟢" if x >= 0 else "🔴"

def run_analysis_sync(ticker: str, analysis_type: str):
    """Ejecuta análisis de forma síncrona usando parsers estandarizados"""
    try:
        if analysis_type == "fundamental":
            agent = create_fundamental_agent()
            task = Task(
                description=f"Analiza los fundamentos de {ticker}",
                agent=agent,
                expected_output="JSON válido con análisis fundamental"
            )
        elif analysis_type == "sentiment":
            agent = create_sentiment_agent()
            task = Task(
                description=f"Analiza sentimiento de {ticker}",
                agent=agent,
                expected_output="JSON válido con análisis de sentimiento"
            )
        else:  # technical
            agent = create_technical_agent()
            task = Task(
                description=f"Analiza técnico de {ticker}",
                agent=agent,
                expected_output="JSON válido con análisis técnico"
            )

        print(f"\n{'='*60}")
        print(f"[DASHBOARD] Ejecutando análisis {analysis_type} para {ticker}")
        print(f"{'='*60}")

        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
        result = crew.kickoff()

        print(f"[DASHBOARD] Tipo de resultado: {type(result)}")
        print(f"[DASHBOARD] Tiene .raw? {hasattr(result, 'raw')}")

        # Obtener output correcto de CrewAI
        if hasattr(result, 'raw'):
            output_str = str(result.raw)
        else:
            output_str = str(result)

        print(f"[DASHBOARD] String conversion ({len(output_str)} chars)")
        print(f"[DASHBOARD] Primeros 500 chars: {output_str[:500]}")

        # Usa los parsers estandarizados
        if analysis_type == "fundamental":
            parsed = parse_fundamental_analysis(output_str)
            return asdict(parsed)
        elif analysis_type == "sentiment":
            parsed = parse_sentiment_analysis(output_str)
            return asdict(parsed)
        elif analysis_type == "technical":
            parsed = parse_technical_analysis(output_str)
            return asdict(parsed)

    except Exception as e:
        st.error(f"Error en análisis: {e}")
        import traceback
        print(f"[DASHBOARD ERROR] {e}")
        print(traceback.format_exc(), flush=True)
        return None

# ═══════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════

st.markdown("# 📈 Investment Swarm Dashboard")

col1, col2, col3 = st.columns(3)
with col1:
    if t212_paper_connected:
        _t212p = t212_paper_broker.get_portfolio_summary()
        st.metric("🟡 T212 Paper (Demo)", fmt_money(_t212p.get("total_value", 0)))
    else:
        _pe_sum = paper_engine.get_portfolio_summary()
        st.metric("📚 Paper Trading (local)", fmt_money(_pe_sum["total_value"]),
                  delta=f"{_pe_sum['return_pct']:+.2f}%")

with col2:
    if t212_live_connected:
        _t212l = t212_live_broker.get_portfolio_summary()
        st.metric("🔴 T212 Live", fmt_money(_t212l.get("total_value", 0)))
    else:
        st.metric("📈 T212 Live", "Sin conectar")

st.divider()

# ═══════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4 = st.tabs([
    "💰 Paper Trading",
    "📈 Trading 212",
    "📊 Análisis",
    "🧪 Tests & Simulation"
])

# ─────────────────────────────────────────────────────────────
# TAB 1: PAPER TRADING
# ─────────────────────────────────────────────────────────────

with tab1:
    st.header("💰 Paper Trading")

    # ── helpers locales ────────────────────────────────────────
    def _regime_badge(r: str) -> str:
        return {"BULLISH": "🟢 BULLISH", "NEUTRAL": "🟡 NEUTRAL",
                "BEARISH": "🔴 BEARISH", "BEAR_RALLY": "🟠 BEAR_RALLY"}.get(r, r)

    def _conv_badge(c: str) -> str:
        return {"VERY_HIGH": "⬆️ Muy Alta", "HIGH": "↑ Alta",
                "MEDIUM": "→ Media", "LOW": "↓ Baja", "MANUAL": "✋ Manual",
                "HEDGE": "🛡️ Hedge"}.get(c, c or "—")

    # ── Indicador de fuente de datos ───────────────────────────
    if t212_paper_connected:
        st.success("✓ **Trading 212 Demo conectado** — datos y operaciones en tiempo real sobre tu cuenta demo")
    else:
        _no_creds = not t212_paper_broker.api_secret
        _conn_col, _btn_col = st.columns([3, 1])
        with _conn_col:
            if _no_creds:
                st.info("ℹ️ T212 Demo no configurado — usando simulación local. "
                        "Añade `T212_API_SECRET_PAPER_TRADING` (o `T212_API_SECRET`) al `.env`.")
            else:
                st.error("❌ T212 Demo: credenciales encontradas pero la conexión falló. "
                         "Verifica que la API key sea la de la cuenta demo.")
        with _btn_col:
            if not _no_creds and st.button("🔄 Reconectar", key="paper_reconnect"):
                t212_paper_broker.connected = False
                _ok = t212_paper_broker.connect()
                st.session_state.t212_paper_connected = _ok
                st.rerun()

    # ── 1. KPIs ────────────────────────────────────────────────
    regime = paper_engine.get_regime()
    paused = paper_engine.state.get("trading_paused", False)

    if t212_paper_connected:
        _t212p_sum = t212_paper_broker.get_portfolio_summary()
        total    = _t212p_sum.get("total_value", 0.0)
        cash     = _t212p_sum.get("cash", 0.0)
        invested = _t212p_sum.get("positions_value", 0.0)
        ret_pct  = _t212p_sum.get("return_pct", 0.0)
        initial  = paper_engine.get_portfolio_summary().get("initial_capital", 5000.0)
    else:
        portfolio = paper_engine.get_portfolio_summary()
        total    = portfolio["total_value"]
        cash     = portfolio["cash"]
        invested = total - cash
        ret_pct  = portfolio["return_pct"]
        initial  = portfolio["initial_capital"]

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("💼 Total", fmt_money(total),
              delta=f"{ret_pct:+.2f}%")
    k2.metric("💵 Cash libre",  fmt_money(cash))
    k3.metric("📊 Invertido",   fmt_money(invested))
    k4.metric("🌍 Régimen",     _regime_badge(regime))
    k5.metric("🛡️ Circuit",     "⏸️ PAUSADO" if paused else "✅ Activo")

    st.divider()

    # ── 2. WATCHLIST + ACCIONES BOT ───────────────────────────
    wl_col, bot_col = st.columns([1, 1], gap="large")

    with wl_col:
        st.subheader("📋 Watchlist")
        watchlist = paper_engine.state.get("watchlist", [])

        # Mostrar tickers actuales con botón de quitar
        if watchlist:
            cols_wl = st.columns(min(len(watchlist), 5))
            for i, t in enumerate(watchlist):
                with cols_wl[i % 5]:
                    if st.button(f"❌ {t}", key=f"rm_{t}", use_container_width=True,
                                 help=f"Quitar {t} de la watchlist"):
                        paper_engine.remove_ticker(t)
                        st.rerun()
        else:
            st.info("Watchlist vacía — añade tickers abajo")

        # Añadir ticker
        add_c1, add_c2 = st.columns([3, 1])
        with add_c1:
            new_ticker = st.text_input("Añadir ticker", placeholder="Ej: AAPL",
                                       label_visibility="collapsed", key="wl_add_input").upper().strip()
        with add_c2:
            if st.button("➕ Añadir", key="wl_add_btn", use_container_width=True):
                if new_ticker:
                    paper_engine.add_ticker(new_ticker)
                    st.success(f"✓ {new_ticker} añadido")
                    st.rerun()
                else:
                    st.warning("Escribe un ticker")

    with bot_col:
        st.subheader("🤖 Acciones del Bot")

        def _execute_scan_on_t212(scan_result: dict) -> None:
            """Si T212 paper está conectado, replica las decisiones del bot en T212."""
            if not t212_paper_connected:
                return
            for b in scan_result.get("buys", []):
                res = t212_paper_broker.buy(b["ticker"], b["quantity"])
                if res.get("success"):
                    st.success(f"✅ T212 Demo: Comprado {b['quantity']} {b['ticker']}"
                               f" | Order {res.get('order_id','?')}")
                else:
                    st.warning(f"⚠️ T212 Demo (compra fallida): {res.get('message','?')}")
            for s in scan_result.get("sells", []):
                res = t212_paper_broker.sell(s["ticker"], s["quantity"])
                if res.get("success"):
                    st.success(f"✅ T212 Demo: Vendido {s['quantity']} {s['ticker']}"
                               f" | Order {res.get('order_id','?')}")
                else:
                    st.warning(f"⚠️ T212 Demo (venta fallida): {res.get('message','?')}")

        b1, b2 = st.columns(2)
        with b1:
            if st.button("🔍 Scan Automático", use_container_width=True, key="btn_scan",
                         help="El bot analiza la watchlist y compra solo si ve señal clara"):
                with st.spinner("Escaneando..."):
                    result = paper_engine.scan(mode="auto")
                buys   = result.get("buys", [])
                sells  = result.get("sells", [])
                skipped = result.get("skipped", [])
                notes  = result.get("notes", [])
                if buys:
                    for b in buys:
                        st.success(f"✅ Bot decide: {b['quantity']} {b['ticker']} @ ${b['price']:.2f}"
                                   f"  (conv: {b.get('conviction','?')})")
                if sells:
                    for s in sells:
                        st.warning(f"🔔 Bot decide vender: {s['quantity']} {s['ticker']}"
                                   f"  — {s.get('reason','?')}")
                if notes:
                    for n in notes: st.info(n)
                if not buys and not sells:
                    st.info(f"Sin operaciones. Saltados: {len(skipped)}")
                _execute_scan_on_t212(result)
                st.rerun()

        with b2:
            if st.button("💰 Invertir Ahora", use_container_width=True, key="btn_invest",
                         help="Fuerza la entrada en todos los tickers de la watchlist sin señal mínima"):
                with st.spinner("Invirtiendo..."):
                    result = paper_engine.scan(mode="invest_now")
                buys = result.get("buys", [])
                if buys:
                    for b in buys:
                        st.success(f"✅ Bot decide: {b['quantity']} {b['ticker']} @ ${b['price']:.2f}")
                else:
                    notes = result.get("notes", [])
                    st.info(notes[0] if notes else "Sin tickers disponibles")
                _execute_scan_on_t212(result)
                st.rerun()

        # Cooldowns activos
        cooldowns = paper_engine.state.get("stop_loss_cooldown", {})
        active_cd = {t: d for t, d in cooldowns.items()
                     if datetime.fromisoformat(d) > datetime.now()}
        if active_cd:
            st.markdown("**⏳ En cooldown:**")
            for t, until in active_cd.items():
                days_left = (datetime.fromisoformat(until) - datetime.now()).days
                st.caption(f"  {t} — {days_left}d restantes")

    st.divider()

    # ── 3. POSICIONES ABIERTAS ────────────────────────────────
    st.subheader("📌 Posiciones Abiertas")

    if t212_paper_connected:
        positions = t212_paper_broker.get_positions()
        if positions:
            for pos in positions:
                pnl_icon = "🟢" if pos["pnl_pct"] >= 0 else "🔴"
                with st.expander(
                    f"{pnl_icon} **{pos['ticker']}** — "
                    f"{pos['qty']:.4g} acc. | entrada ${pos['entry_price']:.2f} | "
                    f"actual ${pos['current_price']:.2f} | "
                    f"PnL {pos['pnl_pct']:+.2f}%",
                    expanded=False,
                ):
                    pc1, pc2, pc3, pc4 = st.columns(4)
                    pc1.metric("Cantidad",       f"{pos['qty']:.4g}")
                    pc2.metric("Precio entrada", f"${pos['entry_price']:.2f}")
                    pc3.metric("Precio actual",  f"${pos['current_price']:.2f}")
                    pc4.metric("PnL",
                               fmt_money(pos["pnl"]),
                               delta=f"{pos['pnl_pct']:+.2f}%")
                    st.caption(f"Valor total: {fmt_money(pos['value'])} | "
                               f"T212 ticker: `{pos.get('t212_ticker', pos['ticker'])}`")

                    sell_key = f"t212_sell_{pos['ticker']}"
                    if st.button(f"🔴 Vender {pos['qty']:.4g} {pos['ticker']} en T212 Demo",
                                 key=sell_key, type="secondary"):
                        with st.spinner("Enviando orden de venta..."):
                            r = t212_paper_broker.sell(pos["ticker"], pos["qty"])
                        if r.get("success"):
                            st.success(r["message"])
                        else:
                            st.error(r.get("message", "Error desconocido"))
                        st.rerun()
        else:
            st.info("No hay posiciones abiertas en T212 Demo.")
    else:
        # Fuente local: paper_engine
        _local_portfolio = paper_engine.get_portfolio_summary()
        positions = _local_portfolio.get("positions", [])
        if positions:
            for pos in positions:
                is_hedge = pos.get("is_hedge", False)
                pnl_icon = "🟢" if pos["pnl_pct"] >= 0 else "🔴"
                ticker_label = f"🛡️ {pos['ticker']}" if is_hedge else pos["ticker"]

                with st.expander(
                    f"{pnl_icon} **{ticker_label}** — "
                    f"{pos['qty']} acc. | entrada ${pos['entry_price']:.2f} | "
                    f"actual ${(pos['current_price'] or 0):.2f} | "
                    f"PnL {pos['pnl_pct']:+.2f}%",
                    expanded=False,
                ):
                    pc1, pc2, pc3, pc4 = st.columns(4)
                    pc1.metric("Cantidad",    pos["qty"])
                    pc2.metric("Precio entrada", f"${pos['entry_price']:.2f}")
                    pc3.metric("Precio actual",
                               f"${pos['current_price']:.2f}" if pos["current_price"] else "N/A")
                    pc4.metric("PnL",
                               f"${pos['pnl']:.2f}",
                               delta=f"{pos['pnl_pct']:+.2f}%")

                    st.caption(
                        f"Convicción: {_conv_badge(pos.get('conviction'))} | "
                        f"Régimen entrada: {pos.get('entry_regime','?')} | "
                        f"Fecha: {str(pos.get('entry_date','?'))[:10]}"
                    )

                    sell_key = f"sell_{pos['ticker']}_{pos['entry_date']}"
                    if st.button(f"🔴 Vender {pos['qty']} {pos['ticker']} (precio actual)",
                                 key=sell_key, type="secondary"):
                        price_now = paper_engine.get_current_price(pos["ticker"])
                        if price_now:
                            r = paper_engine.execute_operation_manual(
                                pos["ticker"], "SELL", pos["qty"], price_now,
                                note="Venta forzada desde dashboard",
                            )
                            if r["success"]:
                                st.success(r["message"])
                            else:
                                st.error(r["message"])
                            st.rerun()
                        else:
                            st.error("No se pudo obtener precio actual")
        else:
            st.info("No hay posiciones abiertas.")

    st.divider()

    # ── 4. OPERACIÓN MANUAL ────────────────────────────────────
    st.subheader("✍️ Operación Manual")
    if t212_paper_connected:
        st.caption("Las órdenes se enviarán a tu cuenta demo de Trading 212.")

    op_type = st.radio("Acción:", ["COMPRAR", "VENDER"], horizontal=True, key="op_type")

    mc1, mc2, mc3, mc4 = st.columns([2, 1, 1, 1])
    with mc1:
        op_ticker = st.text_input("Ticker", placeholder="Ej: MSFT",
                                  key="op_ticker").upper().strip()
        if op_ticker and t212_paper_connected:
            _resolved = t212_paper_broker.resolve_ticker(op_ticker)
            if _resolved:
                st.caption(f"T212: `{_resolved}`")
            else:
                _matches = t212_paper_broker.search_ticker(op_ticker)
                if _matches:
                    st.caption("Posibles: " + ", ".join(f"`{m['symbol']}`" for m in _matches[:3]))
                else:
                    st.caption(f"⚠️ '{op_ticker}' no encontrado en catálogo T212")
    with mc2:
        op_qty = st.number_input("Cantidad", min_value=0.01, value=1.0,
                                 step=0.01, format="%.4f", key="op_qty")
    with mc3:
        default_price = 0.0
        if op_ticker:
            try:
                p = paper_engine.get_current_price(op_ticker)
                default_price = float(p) if p else 0.0
            except Exception:
                pass
        op_price = st.number_input("Precio ref. ($)", min_value=0.0, value=default_price,
                                    step=0.01, format="%.2f", key="op_price",
                                    help="Solo referencial — T212 usa precio de mercado real")
    with mc4:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        confirm_key = f"confirm_op_{op_type}_{op_ticker}"
        execute_btn = st.button(
            f"{'🟢 COMPRAR' if op_type == 'COMPRAR' else '🔴 VENDER'}",
            key=confirm_key, use_container_width=True, type="primary",
        )

    if execute_btn:
        if not op_ticker:
            st.error("Escribe un ticker")
        else:
            action = "BUY" if op_type == "COMPRAR" else "SELL"
            if t212_paper_connected:
                with st.spinner("Enviando orden a T212 Demo..."):
                    if action == "BUY":
                        result = t212_paper_broker.buy(op_ticker, op_qty)
                    else:
                        result = t212_paper_broker.sell(op_ticker, op_qty)
                if result.get("success"):
                    st.success(f"{result['message']} | Order ID: {result.get('order_id','?')}")
                else:
                    st.error(result.get("message", "Error desconocido"))
            else:
                if op_price <= 0:
                    st.error("Precio debe ser > 0")
                else:
                    cost_preview = op_qty * op_price
                    st.info(f"Ejecutando {action} de {op_qty} {op_ticker} @ ${op_price:.2f}"
                            f" (total ≈ ${cost_preview:,.2f})")
                    result = paper_engine.execute_operation_manual(
                        op_ticker, action, int(op_qty), op_price,
                        note="Operación manual desde dashboard",
                    )
                    if result["success"]:
                        bot_op = result.get("trade", {}).get("bot_opinion", "?")
                        st.success(f"{result['message']} | Bot opinion: {bot_op}")
                    else:
                        st.error(result["message"])
            st.rerun()

    st.divider()

    # ── 5. HISTORIAL DE TRADES ─────────────────────────────────
    st.subheader("📜 Historial de Operaciones")

    if t212_paper_connected:
        t212_history = t212_paper_broker.get_order_history(limit=50)
        if t212_history:
            rows_th = []
            for o in t212_history:
                side = o.get("type", o.get("side", "?"))
                t212_tk = o.get("ticker", "?")
                symbol = t212_paper_broker._t212_to_symbol(t212_tk) or t212_tk
                filled_qty   = o.get("filledQuantity",  o.get("quantity", "?"))
                filled_price = o.get("filledPrice",     o.get("price", None))
                ts = o.get("dateCreated", o.get("dateModified", ""))
                rows_th.append({
                    "Fecha":   str(ts)[:16],
                    "Ticker":  symbol,
                    "Acción":  f"{'🟢 BUY' if 'BUY' in str(side).upper() else '🔴 SELL'}",
                    "Cantidad": filled_qty,
                    "Precio":  f"${float(filled_price):.2f}" if filled_price else "—",
                    "Estado":  o.get("status", "?"),
                })
            st.dataframe(pd.DataFrame(rows_th), use_container_width=True, hide_index=True)
        else:
            st.info("Sin historial de órdenes en T212 Demo.")
    else:
        trade_history = paper_engine.state.get("trade_history", [])
        if trade_history:
            trades_reversed = list(reversed(trade_history[-50:]))
            rows_th = []
            for t in trades_reversed:
                action = t.get("action", "?")
                pnl = t.get("pnl")
                rows_th.append({
                    "Fecha":    str(t.get("date",""))[:16],
                    "Ticker":   t.get("ticker","?"),
                    "Acción":   f"{'🟢 BUY' if action=='BUY' else '🔴 SELL'}",
                    "Precio":   f"${t.get('price',0):.2f}",
                    "Qty":      t.get("quantity","?"),
                    "Total":    f"${t.get('amount',0):.2f}",
                    "PnL":      f"${pnl:.2f}" if pnl is not None else "—",
                    "Razón":    t.get("reason", t.get("conviction", t.get("note","—"))),
                    "Origen":   t.get("origin", "AUTO"),
                    "Régimen":  t.get("regime","?"),
                })
            st.dataframe(pd.DataFrame(rows_th), use_container_width=True, hide_index=True)
        else:
            st.info("Sin operaciones todavía.")

    st.divider()

    # ── 6. CONTROL AVANZADO ────────────────────────────────────
    with st.expander("⚙️ Control avanzado"):
        adv1, adv2, adv3 = st.columns(3)

        with adv1:
            st.markdown("**🔄 Reset portfolio**")
            st.caption("Borra posiciones e historial. Mantiene análisis guardados.")
            if st.button("🗑️ Resetear Paper Trading", key="btn_reset", type="secondary"):
                if st.session_state.get("confirm_reset"):
                    paper_engine.reset()
                    st.session_state.confirm_reset = False
                    st.success("✓ Portfolio reseteado")
                    st.rerun()
                else:
                    st.session_state.confirm_reset = True
                    st.warning("Pulsa de nuevo para confirmar")

        with adv2:
            st.markdown("**🛡️ Circuit Breaker**")
            dd_pct = 0.0
            peak   = paper_engine.state.get("peak_portfolio_value", total)
            if peak > 0:
                dd_pct = (peak - total) / peak * 100
            st.caption(f"Drawdown actual: {dd_pct:.1f}% (umbral: 15%)")
            st.caption(f"Pico histórico: {fmt_money(peak)}")
            if paused:
                st.warning("⏸️ Trading pausado")
                if st.button("▶️ Reanudar manualmente", key="btn_resume"):
                    paper_engine.state["trading_paused"] = False
                    paper_engine.state["pause_started_at"] = None
                    paper_engine.state["peak_portfolio_value"] = total
                    paper_engine.save()
                    st.success("Trading reanudado")
                    st.rerun()
            else:
                st.success("✅ Trading activo")

        with adv3:
            st.markdown("**📊 Costes de transacción**")
            _local_p = paper_engine.get_portfolio_summary()
            total_costs = _local_p.get("total_transaction_costs", 0.0)
            cost_pct = (total_costs / initial * 100) if initial > 0 else 0
            st.metric("Total pagado (local)", fmt_money(total_costs))
            st.caption(f"{cost_pct:.2f}% del capital inicial")
            last_scan = _local_p.get("last_scan_at")
            if last_scan:
                st.caption(f"Último scan: {str(last_scan)[:16]}")

# ─────────────────────────────────────────────────────────────
# TAB 2: LIVE TRADING
# ─────────────────────────────────────────────────────────────

with tab2:
    st.header("📈 Trading 212 — Cuenta Real")

    if not t212_live_broker.api_secret:
        st.warning("⚠️ Añade las credenciales de la cuenta real de Trading 212 en el `.env`.")
        st.code(
            "T212_API_KEY_ID_LIVE_TRADING=id_visible_en_el_panel_t212_live\n"
            "T212_API_SECRET_LIVE_TRADING=clave_secreta_de_tu_cuenta_real",
            language="bash",
        )
    elif not t212_live_connected:
        st.error("❌ No se pudo conectar con Trading 212 Live. Verifica la API key.")
        if st.button("🔄 Reintentar conexión", key="t212_live_retry"):
            t212_live_broker.connected = False
            ok = t212_live_broker.connect()
            st.session_state.t212_live_connected = ok
            st.rerun()
    else:
        st.success("✓ Trading 212 Live conectado — 🔴 CUENTA REAL")

        t212_portfolio = t212_live_broker.get_portfolio_summary()
        free      = t212_portfolio.get("cash", 0.0)
        invested  = t212_portfolio.get("positions_value", 0.0)
        total_t   = t212_portfolio.get("total_value", 0.0)
        ppl       = t212_portfolio.get("unrealized_pnl", 0.0)

        # KPIs
        tc1, tc2, tc3, tc4 = st.columns(4)
        tc1.metric("💼 Total cuenta", fmt_money(total_t))
        tc2.metric("💵 Disponible",   fmt_money(free))
        tc3.metric("📊 Invertido",    fmt_money(invested))
        tc4.metric("📈 P&L no realiz.", fmt_money(ppl),
                   delta=f"{t212_portfolio.get('return_pct', 0):.2f}%")

        st.divider()

        # Posiciones
        t212_positions = t212_portfolio.get("positions", [])
        st.subheader(f"📌 Posiciones abiertas ({len(t212_positions)})")
        if t212_positions:
            df_pos = pd.DataFrame([
                {
                    "Ticker":        p["ticker"],
                    "Cantidad":      p["qty"],
                    "Precio medio":  f"${p['entry_price']:.2f}",
                    "Precio actual": f"${p['current_price']:.2f}",
                    "Valor":         fmt_money(p["value"]),
                    "PnL":           fmt_money(p["pnl"]),
                    "PnL%":          f"{p['pnl_pct']:+.2f}%",
                }
                for p in t212_positions
            ])
            st.dataframe(df_pos, use_container_width=True, hide_index=True)
        else:
            st.info("Sin posiciones abiertas en Trading 212 Live.")

        st.divider()

        # Operación manual T212 Live
        st.subheader("✍️ Operar en Trading 212 Live")
        st.caption("⚠️ Las órdenes se ejecutan con DINERO REAL.")

        t2_c1, t2_c2, t2_c3, t2_c4 = st.columns([2, 1, 1, 1])
        with t2_c1:
            t212_symbol = st.text_input("Ticker", placeholder="Ej: AAPL",
                                        key="t212_ticker_input").upper().strip()
        with t2_c2:
            t212_qty = st.number_input("Cantidad", min_value=0.01, value=1.0,
                                       step=0.01, format="%.4f", key="t212_qty")
        with t2_c3:
            t212_max_amt = st.number_input("Máx. importe ($)", min_value=0.0, value=0.0,
                                           step=10.0, format="%.2f", key="t212_max_amt",
                                           help="0 = sin límite")
        with t2_c4:
            t212_side = st.radio("", ["BUY", "SELL"], horizontal=True, key="t212_side")

        # Buscar instrumento
        if t212_symbol:
            t212_resolved = t212_live_broker.resolve_ticker(t212_symbol)
            if t212_resolved:
                st.caption(f"✓ Instrumento T212: `{t212_resolved}`")
            else:
                matches = t212_live_broker.search_ticker(t212_symbol)
                if matches:
                    st.caption("Posibles coincidencias: " +
                               ", ".join(f"`{m['symbol']}`" for m in matches[:5]))
                else:
                    st.warning(f"'{t212_symbol}' no encontrado en el catálogo T212 Live")

        if st.button(f"{'🟢 COMPRAR' if t212_side=='BUY' else '🔴 VENDER'} en T212 Live",
                     key="t212_execute", type="primary"):
            if not t212_symbol:
                st.error("Introduce un ticker")
            else:
                max_a = float(t212_max_amt) if t212_max_amt > 0 else None
                with st.spinner("Enviando orden..."):
                    if t212_side == "BUY":
                        res = t212_live_broker.buy(t212_symbol, t212_qty, max_amount=max_a)
                    else:
                        res = t212_live_broker.sell(t212_symbol, t212_qty)
                if res.get("success"):
                    st.success(res["message"] +
                               f" | Order ID: {res.get('order_id','?')}")
                else:
                    st.error(res.get("message", "Error desconocido"))

        st.divider()

        # Historial de órdenes T212 Live
        with st.expander("📜 Historial de órdenes (últimas 20)"):
            history = t212_live_broker.get_order_history(limit=20)
            if history:
                st.dataframe(pd.DataFrame(history), use_container_width=True,
                             hide_index=True)
            else:
                st.info("Sin historial disponible.")

# ─────────────────────────────────────────────────────────────
# TAB 3: ANÁLISIS INTEGRADO
# ─────────────────────────────────────────────────────────────

with tab3:
    st.header("📊 Análisis de Tickers")

    # Input y botones
    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])

    with col1:
        ticker_input = st.text_input("Ticker:", placeholder="Ej: AAPL").upper()

    with col2:
        if st.button("📊 Fundamental", key="btn_fund", use_container_width=True):
            if ticker_input:
                with st.spinner(f"Analizando {ticker_input}..."):
                    result = run_analysis_sync(ticker_input, "fundamental")
                    if result:
                        AnalysisStorage.save_analysis(ticker_input, "fundamental", result)
                        st.success("✓ Análisis guardado")
                        st.json(result)
            else:
                st.error("Ingresa un ticker")

    with col3:
        if st.button("📰 Sentimiento", key="btn_sent", use_container_width=True):
            if ticker_input:
                with st.spinner(f"Analizando {ticker_input}..."):
                    result = run_analysis_sync(ticker_input, "sentiment")
                    if result:
                        AnalysisStorage.save_analysis(ticker_input, "sentiment", result)
                        st.success("✓ Análisis guardado")
                        st.json(result)
            else:
                st.error("Ingresa un ticker")

    with col4:
        if st.button("📈 Técnico", key="btn_tech", use_container_width=True):
            if ticker_input:
                with st.spinner(f"Analizando {ticker_input}..."):
                    result = run_analysis_sync(ticker_input, "technical")
                    if result:
                        AnalysisStorage.save_analysis(ticker_input, "technical", result)
                        st.success("✓ Análisis guardado")
                        st.json(result)
            else:
                st.error("Ingresa un ticker")

    with col5:
        if st.button("🔄 Todos", key="btn_all", use_container_width=True):
            if ticker_input:
                for analysis_type in ["fundamental", "sentiment", "technical"]:
                    with st.spinner(f"Analizando {ticker_input} - {analysis_type}..."):
                        result = run_analysis_sync(ticker_input, analysis_type)
                        if result:
                            AnalysisStorage.save_analysis(ticker_input, analysis_type, result)
                st.success("✓ Todos los análisis guardados")
            else:
                st.error("Ingresa un ticker")

    st.divider()

    # Tabla de análisis
    st.subheader("📋 Últimos Análisis")

    all_analyses = AnalysisStorage.get_all_analyses()

    if all_analyses:
        rows = []
        for ticker, analyses in all_analyses.items():
            fundamental = analyses.get("fundamental", {}).get("data", {})
            sentiment = analyses.get("sentiment", {}).get("data", {})
            technical = analyses.get("technical", {}).get("data", {})

            # Usar timestamp más reciente
            timestamps = [
                analyses.get("fundamental", {}).get("timestamp", ""),
                analyses.get("sentiment", {}).get("timestamp", ""),
                analyses.get("technical", {}).get("timestamp", ""),
            ]
            latest = max([t for t in timestamps if t], default="N/A")

            rows.append({
                "Ticker": ticker,
                "Fundamental": f"📊 {fundamental.get('score', 'N/A')}/10",
                "Sentimiento": f"📰 {sentiment.get('sentiment', 'N/A')}",
                "Técnico": f"📈 {technical.get('signal', 'N/A')}",
                "Última actualización": latest[:10] if latest != "N/A" else "N/A"
            })

        df = pd.DataFrame(rows)

        # Mostrar tabla
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Hacer tabla interactiva - Detalles del Análisis
        st.subheader("📌 Detalles del Análisis")
        selected_ticker = st.selectbox("Selecciona un ticker:", [r["Ticker"] for r in rows], key="ticker_select")

        if selected_ticker:
            ticker_data = all_analyses[selected_ticker]

            col1, col2, col3 = st.columns(3, gap="medium")

            # FUNDAMENTAL
            with col1:
                if "fundamental" in ticker_data:
                    fund_data = ticker_data["fundamental"]["data"]
                    with st.container():
                        st.markdown(f"### 📊 Fundamental")

                        # Score con barra de progreso
                        score = fund_data.get("score", 0)
                        st.metric("Score", f"{score}/10", delta=None)

                        # Progress bar
                        progress_val = min(score / 10, 1.0)
                        st.progress(progress_val)

                        # Detalles
                        st.markdown(f"**Confianza:** {fund_data.get('confidence', 'N/A')}%")
                        st.markdown(f"**Riesgo:** {fund_data.get('risk_level', 'N/A')}")
                        st.markdown(f"**Recomendación:** {fund_data.get('recommendation', 'N/A')}")

                        with st.expander("📝 Análisis Completo"):
                            # Resumen
                            st.write(fund_data.get("summary", "Sin información"))

                            # Ratios
                            ratios = fund_data.get("ratios", {})
                            if ratios:
                                st.markdown("**Ratios Financieros:**")
                                for ratio_name, ratio_value in ratios.items():
                                    st.write(f"  • {ratio_name}: {ratio_value}")

                            # Growth Metrics
                            growth = fund_data.get("growth_metrics", {})
                            if growth:
                                st.markdown("**Métricas de Crecimiento:**")
                                for metric_name, metric_value in growth.items():
                                    st.write(f"  • {metric_name}: {metric_value}")

                            # Red Flags
                            red_flags = fund_data.get("red_flags", [])
                            if red_flags:
                                st.markdown("**⚠️ Red Flags:**")
                                for flag in red_flags:
                                    st.write(f"  • {flag}")

            # SENTIMIENTO
            with col2:
                if "sentiment" in ticker_data:
                    sent_data = ticker_data["sentiment"]["data"]
                    with st.container():
                        st.markdown(f"### 📰 Sentimiento")

                        sentiment = sent_data.get("sentiment", "N/A")

                        # Color según sentimiento
                        if sentiment == "POSITIVO":
                            color = "🟢"
                        elif sentiment == "NEGATIVO":
                            color = "🔴"
                        else:
                            color = "🟡"

                        st.metric("Sentimiento", f"{color} {sentiment}", delta=None)
                        st.markdown(f"**Confianza:** {sent_data.get('confidence', 'N/A')}%")

                        # Catalizadores
                        catalysts = sent_data.get("catalysts", "")
                        if catalysts:
                            st.markdown("**Catalizadores:**")
                            st.write(catalysts if isinstance(catalysts, str) else ", ".join(catalysts))

                        with st.expander("📝 Resumen"):
                            st.write(sent_data.get("summary", "Sin información"))

            # TÉCNICO
            with col3:
                if "technical" in ticker_data:
                    tech_data = ticker_data["technical"]["data"]
                    with st.container():
                        st.markdown(f"### 📈 Técnico")

                        signal = tech_data.get("signal", "HOLD")

                        # Color según signal
                        if signal == "BUY":
                            color = "🟢"
                        elif signal == "SELL":
                            color = "🔴"
                        else:
                            color = "🟡"

                        st.metric("Signal", f"{color} {signal}", delta=None)
                        st.markdown(f"**Confianza:** {tech_data.get('confidence', 'N/A')}%")
                        st.markdown(f"**Soporte:** ${tech_data.get('support', 'N/A')}")
                        st.markdown(f"**Resistencia:** ${tech_data.get('resistance', 'N/A')}")

                        with st.expander("📝 Análisis"):
                            st.write(tech_data.get("summary", "Sin información"))

            # ── PANEL 4: RESUMEN Y RECOMENDACIÓN ──────────────────────────
            st.divider()
            st.markdown(f"### 🎯 Resumen y Recomendación — {selected_ticker}")

            fund_d = ticker_data.get("fundamental", {}).get("data", {})
            sent_d = ticker_data.get("sentiment",  {}).get("data", {})
            tech_d = ticker_data.get("technical",  {}).get("data", {})

            # Normaliza claves (inglés o español según origen)
            f_score = float(fund_d.get("score", 5)) / 10.0
            f_conf  = float(fund_d.get("confidence", 50)) / 100.0

            _sig_map = {"ALCISTA": 0.8, "BUY": 0.8, "LATERAL": 0.5,
                        "HOLD": 0.5, "BAJISTA": 0.2, "SELL": 0.2}
            t_signal = tech_d.get("señal", tech_d.get("signal", "LATERAL"))
            t_score  = _sig_map.get(t_signal, 0.5)
            t_conf   = float(tech_d.get("confianza", tech_d.get("confidence", 50))) / 100.0

            _sent_map = {"POSITIVO": 0.8, "NEUTRO": 0.5, "NEGATIVO": 0.2}
            s_value  = sent_d.get("sentimiento", sent_d.get("sentiment", "NEUTRO"))
            s_score  = _sent_map.get(s_value, 0.5)
            s_conf   = float(sent_d.get("confianza", sent_d.get("confidence", 50))) / 100.0

            combined = f_score * 0.40 + t_score * 0.35 + s_score * 0.25
            avg_conf = (f_conf + t_conf + s_conf) / 3

            # Conviction + recomendación (mismos umbrales que InvestmentDecisionEngine)
            if combined >= 0.74 and avg_conf >= 0.62:
                conviction, final_rec = "VERY_HIGH", "BUY"
            elif combined >= 0.63 and avg_conf >= 0.52:
                conviction, final_rec = "HIGH", "BUY"
            elif combined >= 0.53 and avg_conf >= 0.44:
                conviction, final_rec = "MEDIUM", "HOLD"
            else:
                conviction, final_rec = "LOW", "AVOID"

            # El fundamental puede forzar SELL/AVOID independientemente
            if fund_d.get("recommendation") in ("SELL", "AVOID"):
                final_rec = fund_d["recommendation"]
                conviction = "LOW"

            # Red flags de las 3 fuentes
            all_red_flags = list(fund_d.get("red_flags", []))
            all_red_flags += list(sent_d.get("red_flags", []))
            if float(tech_d.get("confianza", tech_d.get("confidence", 50))) < 40:
                all_red_flags.append("Señal técnica débil (confianza baja)")
            all_red_flags = all_red_flags[:5]

            # Paleta de colores por recomendación
            _bg   = {"BUY": "#1a472a", "HOLD": "#3d3000", "SELL": "#5c1010", "AVOID": "#5c1010"}
            _tc   = {"BUY": "#4caf50", "HOLD": "#ffc107", "SELL": "#f44336", "AVOID": "#f44336"}
            _icon = {"BUY": "🟢", "HOLD": "🟡", "SELL": "🔴", "AVOID": "🔴"}
            _conv_label = {"VERY_HIGH": "Muy Alta ⬆️", "HIGH": "Alta ↑",
                           "MEDIUM": "Media →",       "LOW": "Baja ↓"}

            sum_c1, sum_c2, sum_c3 = st.columns([1, 1, 2])

            with sum_c1:
                st.markdown(
                    f"""<div style="background:{_bg.get(final_rec,'#333')};
                        border-radius:14px; padding:28px 16px; text-align:center;
                        border:1px solid {_tc.get(final_rec,'#888')}40">
                      <div style="font-size:2.6rem; font-weight:900;
                                  color:{_tc.get(final_rec,'#ccc')};
                                  letter-spacing:2px">
                        {_icon.get(final_rec,'')} {final_rec}
                      </div>
                      <div style="font-size:0.85rem; color:#aaa; margin-top:8px">
                        Recomendación final
                      </div>
                    </div>""",
                    unsafe_allow_html=True,
                )

            with sum_c2:
                st.metric("Score combinado", f"{combined:.0%}")
                st.progress(float(combined))
                st.markdown(f"**Convicción:** {_conv_label.get(conviction, conviction)}")
                st.markdown(f"**Confianza media:** {avg_conf:.0%}")

            with sum_c3:
                st.markdown("**Desglose por análisis** *(peso en el score)*")
                st.markdown(f"📊 Fundamental &nbsp;&nbsp;`{f_score:.0%}` &nbsp;*(40%)*")
                st.progress(float(f_score))
                st.markdown(f"📈 Técnico &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`{t_score:.0%}` &nbsp;*(35%)*")
                st.progress(float(t_score))
                st.markdown(f"📰 Sentimiento &nbsp;`{s_score:.0%}` &nbsp;*(25%)*")
                st.progress(float(s_score))

            if all_red_flags:
                st.warning("⚠️ **Red Flags:**  " + "  •  ".join(all_red_flags))

            # Resúmenes de texto
            summaries = []
            if fund_d.get("summary"):
                summaries.append(("📊 Fundamental", fund_d["summary"]))
            sent_summary = sent_d.get("summary") or sent_d.get("resumen")
            if sent_summary:
                summaries.append(("📰 Sentimiento", sent_summary))
            if tech_d.get("summary"):
                summaries.append(("📈 Técnico", tech_d["summary"]))

            if summaries:
                with st.expander("📋 Ver resúmenes de los análisis"):
                    for label, text in summaries:
                        st.markdown(f"**{label}:**")
                        st.write(text)
                        st.markdown("")

    else:
        st.info("No hay análisis aún. Realiza algunos análisis para verlos aquí.")


# ─────────────────────────────────────────────────────────────
# TAB 4: TESTS & SIMULATION
# ─────────────────────────────────────────────────────────────

with tab4:
    st.header("🧪 Tests & Simulation")

    # Import backtest runner
    from trading.backtest_runner import BacktestRunner
    import subprocess

    # Crear dos columnas principales
    col_tests, col_backtest = st.columns(2)

    # TESTS
    with col_tests:
        st.subheader("🧪 Ejecutar Tests")

        st.markdown("""
        Ejecuta la suite de tests para validar:
        - Paper Trading Engine
        - Telegram Bot
        - Scheduler
        - Integraciones
        """)

        col_test_buttons = st.columns(3)

        with col_test_buttons[0]:
            if st.button("▶️ Diagnóstico", width="stretch", key="btn_test_diagnose"):
                st.info("Ejecutando diagnóstico...")
                try:
                    result = subprocess.run(
                        ["python", "tests/diagnose_telegram.py"],
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    st.code(result.stdout, language="text")
                except Exception as e:
                    st.error(f"Error: {e}")

        with col_test_buttons[1]:
            if st.button("▶️ Suite", width="stretch", key="btn_test_suite"):
                st.info("Ejecutando tests...")
                try:
                    result = subprocess.run(
                        ["python", "tests/test_suite.py"],
                        capture_output=True,
                        text=True,
                        timeout=120
                    )
                    st.code(result.stdout, language="text")
                except Exception as e:
                    st.error(f"Error: {e}")

        with col_test_buttons[2]:
            if st.button("▶️ Pytest", width="stretch", key="btn_test_pytest"):
                st.info("Ejecutando pytest...")
                try:
                    result = subprocess.run(
                        ["python", "-m", "pytest", "tests/", "-v"],
                        capture_output=True,
                        text=True,
                        timeout=120
                    )
                    st.code(result.stdout, language="text")
                except Exception as e:
                    st.warning(f"Pytest no disponible: {e}")

    # BACKTEST
    with col_backtest:
        st.subheader("📊 Ejecutar Backtest Automático")

        st.markdown("""
        🤖 **El bot opera completamente automático:**
        - Analiza múltiples tickers en paralelo
        - Distribuye capital inteligentemente entre oportunidades
        - Compra/vende según análisis técnico, fundamental y sentimental
        - Toma decisiones de forma independiente cada día
        """)

        # TICKERS
        st.markdown("**📊 Tickers a simular:**")
        col_ticker_input = st.columns([3, 1])

        with col_ticker_input[0]:
            ticker_input = st.text_input(
                "Ingresa tickers separados por comas",
                placeholder="AAPL,MSFT,TSLA,GOOGL",
                key="backtest_ticker_input"
            )

        with col_ticker_input[1]:
            st.write("")
            st.write("")
            use_predefined = st.checkbox("O usar predefinidos", key="use_predefined_tickers")

        # Parsear tickers
        if use_predefined:
            tickers_to_use = None
            st.info("ℹ️ Usando tickers predefinidos del sistema")
        elif ticker_input:
            tickers_to_use = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]
            if tickers_to_use:
                st.success(f"✅ Usando: {', '.join(tickers_to_use)}")
            else:
                tickers_to_use = None
        else:
            tickers_to_use = None

        st.divider()

        # FECHAS
        date_range = st.selectbox(
            "📅 Rango de fechas",
            options=list(BacktestRunner.PREDEFINED_RANGES.keys()) + ["Custom"],
            key="backtest_date_range"
        )

        custom_start = None
        custom_end = None

        if date_range == "Custom":
            col_custom_dates = st.columns(2)
            with col_custom_dates[0]:
                custom_start = st.date_input("Inicio", value=datetime(2023, 1, 1).date())
            with col_custom_dates[1]:
                custom_end = st.date_input("Fin", value=datetime.now().date())

        # CAPITAL
        initial_capital = st.number_input(
            "💰 Capital Inicial",
            min_value=1000.0,
            max_value=1000000.0,
            value=5000.0,
            step=1000.0,
            key="backtest_capital"
        )

        # COSTO
        col_cost = st.columns([2, 1])
        with col_cost[0]:
            cost_input = st.slider("Costo Transacción (%)", 0.0, 1.0, 0.1, 0.01, key="backtest_cost")
        with col_cost[1]:
            transaction_cost_pct = cost_input / 100.0

        st.divider()

        # ── Botón Backtest Completo ──────────────────────────────────────
        btn_full_report = st.button(
            "📊 EJECUTAR BACKTEST COMPLETO",
            width="stretch",
            key="btn_full_report",
            help=(
                "Ejecuta todos los periodos (MAX 2020→2026 + años individuales) "
                "para 6 categorías de stocks y genera un informe XLSX descargable."
            ),
        )

        st.divider()

        # Botones de acción
        col_btn_execute, col_btn_clear = st.columns([0.7, 0.3])

        with col_btn_execute:
            btn_execute = st.button("▶️ EJECUTAR SIMULACIÓN", width="stretch", key="btn_run_backtest")

        with col_btn_clear:
            btn_clear = st.button("🗑️ Limpiar Caché", width="stretch", key="btn_clear_cache",
                                  help="Elimina precios históricos y análisis fundamentales guardados")

        # Mostrar info del caché
        cached_tickers = BacktestRunner.get_cached_tickers()
        cache_size = BacktestRunner.get_cache_size()
        fundamental_cache_path = Path(__file__).parent.parent / "data" / "fundamental_cache.json"
        has_fundamental_cache = fundamental_cache_path.exists()

        cache_parts = []
        if cached_tickers:
            cache_parts.append(f"{len(cached_tickers)} tickers ({cache_size})")
        if has_fundamental_cache:
            cache_parts.append("análisis fundamental")

        if cache_parts:
            st.caption(f"📦 Caché: {' + '.join(cache_parts)}")

        # Manejo del botón de limpiar — usa session_state para evitar el bug
        # de Streamlit donde los botones anidados no se ejecutan nunca
        # (al hacer rerun, btn_clear vuelve a False y el hijo no se renderiza)
        if "confirm_clear_cache" not in st.session_state:
            st.session_state.confirm_clear_cache = False

        if btn_clear:
            st.session_state.confirm_clear_cache = True

        if st.session_state.confirm_clear_cache:
            st.warning("⚠️ ¿Eliminar TODO el caché? (precios + análisis LLM)")
            col_confirm_yes, col_confirm_no = st.columns(2)

            with col_confirm_yes:
                if st.button("✅ Sí, eliminar", width="stretch", key="btn_confirm_clear"):
                    st.session_state.confirm_clear_cache = False
                    success, message = BacktestRunner.clear_all_cache()
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
                    st.rerun()

            with col_confirm_no:
                if st.button("❌ Cancelar", width="stretch", key="btn_cancel_clear"):
                    st.session_state.confirm_clear_cache = False
                    st.rerun()

        # ── Manejador Backtest Completo ──────────────────────────────────
        if btn_full_report:
            from trading.full_backtest_report import run_full_report, generate_xlsx, CATEGORIES, PERIODS

            st.markdown("---")
            st.markdown("## 📊 BACKTEST COMPLETO — Todas las categorías")
            st.info(
                f"Ejecutando **{len(PERIODS)} periodos × {len(CATEGORIES)} categorías** "
                f"con capital **${initial_capital:,.0f}** y comisión **{cost_input:.2f}%**. "
                "Esto puede tardar varios minutos…"
            )

            progress_bar  = st.progress(0, text="Iniciando…")
            status_text   = st.empty()
            total_runs    = len(PERIODS) * len(CATEGORIES)
            run_counter   = [0]

            def _progress_cb(msg: str):
                run_counter[0] += 1
                pct = min(int(run_counter[0] / total_runs * 100), 99)
                progress_bar.progress(pct, text=msg)
                status_text.caption(msg)

            with st.spinner("Descargando datos y ejecutando backtests…"):
                all_results = run_full_report(
                    capital=initial_capital,
                    cost_pct=transaction_cost_pct,
                    progress_callback=_progress_cb,
                )

            progress_bar.progress(100, text="¡Completado!")
            status_text.empty()
            st.success("✅ Backtest completo finalizado. Generando XLSX…")

            xlsx_bytes = generate_xlsx(all_results, capital=initial_capital, cost_pct=transaction_cost_pct)

            from datetime import datetime as _dt
            filename = f"backtest_completo_{_dt.now().strftime('%Y%m%d_%H%M')}.xlsx"

            st.download_button(
                label="⬇️ Descargar Informe XLSX",
                data=xlsx_bytes,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

            # Vista previa por periodo
            st.markdown("### Vista previa de resultados")
            for period in PERIODS:
                pname   = period["name"]
                p_res   = all_results.get(pname, {})
                preview = []
                for cat, meta in CATEGORIES.items():
                    m = p_res.get(cat, {})
                    if "error" not in m:
                        preview.append({
                            "Categoría":   cat,
                            "Tickers":     ", ".join(meta["tickers"]),
                            "Capital final": f"${m['capital_final']:,.2f}",
                            "Retorno %":   f"{m['return_pct']:+.2f}%",
                            "Max DD":      f"{m['max_dd']:.1f}%",
                            "Sharpe":      f"{m['sharpe']:.2f}",
                            "Compras":     m["buys"],
                            "Ventas":      m["sells"],
                            "Win Rate":    f"{m['win_rate']:.1f}%",
                            "Bot":         f"{m['bot_pct']:+.2f}%",
                            "B&H":         f"{m['bnh_pct']:+.2f}%",
                            "SPY":         f"{m['spy_pct']:+.2f}%",
                        })
                if preview:
                    label = (
                        f"**{pname}** — "
                        f"{period['start'].strftime('%d/%m/%Y')} → "
                        f"{period['end'].strftime('%d/%m/%Y')}"
                    )
                    with st.expander(label, expanded=(pname == "MAX")):
                        st.dataframe(
                            pd.DataFrame(preview),
                            use_container_width=True,
                            hide_index=True,
                        )

        # ── Manejador Simulación Normal ───────────────────────────────────
        if btn_execute:
            if not tickers_to_use and not use_predefined:
                st.error("❌ Ingresa tickers o selecciona 'usar predefinidos'")
            else:
                st.info("⏳ Ejecutando backtest automático...")

                with st.spinner("Descargando datos históricos y analizando..."):
                    result = BacktestRunner.run_backtest(
                        date_range=date_range,
                        initial_capital=initial_capital,
                        transaction_cost_pct=transaction_cost_pct,
                        custom_start=custom_start,
                        custom_end=custom_end,
                        tickers=tickers_to_use
                    )

                if result['success']:
                    metrics = result['metrics']
                    formatted = BacktestRunner.format_metrics_for_display(metrics)

                    st.success("✅ ¡Simulación completada!")

                    st.markdown("## 📊 RESUMEN DE RESULTADOS")
                    col_main = st.columns(4)
                    perf = formatted['Performance']

                    with col_main[0]:
                        st.metric("💰 Capital Final", perf['Capital Final'], delta=perf['Return %'])
                    with col_main[1]:
                        st.metric("📈 Retorno %", perf['Return %'])
                    with col_main[2]:
                        st.metric("📉 Max Drawdown", perf['Max Drawdown'])
                    with col_main[3]:
                        st.metric("⚖️ Sharpe Ratio", perf['Sharpe Ratio'])

                    st.divider()

                    st.markdown("## 🤖 ACTIVIDAD DEL BOT")
                    col_activity = st.columns(5)
                    trading = formatted['Trading']

                    with col_activity[0]:
                        st.metric("🟢 Compras", trading['Total Compras'])
                    with col_activity[1]:
                        st.metric("🔴 Ventas", trading['Total Ventas'])
                    with col_activity[2]:
                        st.metric("📍 Posiciones", trading['Posiciones Abiertas'])
                    with col_activity[3]:
                        st.metric("✅ Win Rate", trading['Win Rate'])
                    with col_activity[4]:
                        st.metric("🛑 Stop Loss", trading['Stop Loss'])

                    st.divider()

                    st.markdown("## 📊 COMPARACIÓN CON BENCHMARKS")
                    comp = formatted['Comparación']
                    col_comp = st.columns(3)

                    with col_comp[0]:
                        st.metric("🤖 Bot", comp['Bot Return'])
                    with col_comp[1]:
                        st.metric("📈 Buy & Hold", comp['Buy & Hold'])
                    with col_comp[2]:
                        st.metric("🎯 SPY", comp['SPY Return'])

                    st.info(f"""
                    **Bot vs Estrategias:**
                    - vs Buy&Hold: {comp['Bot vs Buy&Hold']}
                    - vs Perfect Timing: {comp['Bot vs Perfect Timing']}
                    - vs SPY: {comp['Bot vs SPY']}
                    """)

                    st.divider()

                    st.markdown("## 📑 HISTORIAL DE TRADES")

                    trades_df = BacktestRunner.get_trades_dataframe(metrics.get('trades', []))

                    if not trades_df.empty:
                        st.markdown("### Resumen por Ticker:")

                        col_left, col_right = st.columns([1, 2])

                        with col_left:
                            ticker_summary = {}
                            for _, trade in trades_df.iterrows():
                                ticker = trade.get('Ticker', 'N/A')
                                if ticker not in ticker_summary:
                                    ticker_summary[ticker] = {'buys': 0, 'sells': 0}

                                if 'BUY' in str(trade.get('Acción', '')):
                                    ticker_summary[ticker]['buys'] += 1
                                elif 'SELL' in str(trade.get('Acción', '')):
                                    ticker_summary[ticker]['sells'] += 1

                            for ticker, data in sorted(ticker_summary.items()):
                                st.write(f"**{ticker}**: {data['buys']} compras, {data['sells']} ventas")

                        with col_right:
                            st.markdown("### Últimos 15 Trades:")
                            st.dataframe(trades_df.tail(15), use_container_width=True, hide_index=True)

                        with st.expander("📥 Descargar todos los trades"):
                            csv = trades_df.to_csv(index=False)
                            st.download_button(
                                "⬇️ Descargar CSV",
                                data=csv,
                                file_name=f"backtest_trades_{date_range}.csv",
                                mime="text/csv"
                            )
                    else:
                        st.warning("⚠️ No hay trades en este período (bot no encontró oportunidades)")

                    st.divider()

                    st.markdown("## 💸 COSTOS DE OPERACIÓN")

                    col_costs = st.columns(3)
                    costs = formatted['Costos']

                    with col_costs[0]:
                        st.metric("% por Transacción", costs['% Transacción'])
                    with col_costs[1]:
                        st.metric("Total Pagado", costs['Total Pagado'])
                    with col_costs[2]:
                        st.metric("% del Capital", costs['% del Capital'])

                else:
                    st.error(f"❌ Error en simulación: {result['error']}")

# ═══════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════

st.divider()
st.markdown("""
**Investment Swarm Dashboard v3** | Paper + Live Trading
Powered by CrewAI + Ollama + Interactive Brokers
""")
