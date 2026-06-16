"""
DASHBOARD v2 - DUAL MODE (PAPER + LIVE TRADING)
================================================

Tabs:
1. 💰 Paper Trading     - Operaciones en simulado
2. 🔴 Live Trading      - Operaciones con dinero real
3. 📊 Fundamental       - Análisis compartido
4. 📰 Sentimiento       - Análisis compartido
5. ⚙️ Técnico           - Específico del entorno

Ejecutar con:  streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env
load_dotenv()

# Agregar el directorio padre al path para imports relativos
sys.path.insert(0, str(Path(__file__).parent.parent))

# Imports
from trading.paper_trading_engine import (
    PaperTradingEngine,
    OPERATION_ORIGIN_MANUAL_DASHBOARD,
)

try:
    from brokers.interactive_brokers_broker import InteractiveBrokersBroker
    IB_AVAILABLE = True
except:
    IB_AVAILABLE = False

st.set_page_config(
    page_title="Investment Swarm - Dual Trading",
    page_icon="📈",
    layout="wide"
)

# ═══════════════════════════════════════════════════════════════
# INICIALIZACIÓN
# ═══════════════════════════════════════════════════════════════

if "paper_engine" not in st.session_state:
    st.session_state.paper_engine = PaperTradingEngine(initial_capital=5000.0)

if "live_broker" not in st.session_state and IB_AVAILABLE:
    st.session_state.live_broker = InteractiveBrokersBroker()
    try:
        st.session_state.live_broker.connect()
        st.session_state.live_connected = True
    except:
        st.session_state.live_connected = False
else:
    st.session_state.live_broker = None
    st.session_state.live_connected = False

paper_engine = st.session_state.paper_engine
live_broker = st.session_state.live_broker
live_connected = st.session_state.live_connected

# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def fmt_money(x: float) -> str:
    return f"${x:,.2f}"

def fmt_pct(x: float) -> str:
    sign = "+" if x >= 0 else ""
    return f"{sign}{x:.2f}%"

def pnl_color(x: float) -> str:
    """Devuelve color para P&L."""
    return "🟢" if x >= 0 else "🔴"

# ═══════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════

st.markdown("# 📈 Investment Swarm - Dual Trading Dashboard")
st.markdown("### Paper Trading + Live Trading (Interactive Brokers)")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "📚 Paper Trading",
        "Active",
        delta="Simulado" if paper_engine else "Offline"
    )

with col2:
    status = "Active 🟢" if live_connected else "Offline ⚫"
    st.metric(
        "🔴 Live Trading",
        status,
        delta="Dinero real" if live_connected else "No disponible"
    )

with col3:
    st.metric(
        "⏱️ Última sincronización",
        datetime.now().strftime("%H:%M:%S"),
        delta="Ahora"
    )

st.divider()

# ═══════════════════════════════════════════════════════════════
# TABS PRINCIPALES
# ═══════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "💰 Paper Trading",
    "🔴 Live Trading",
    "📊 Fundamental",
    "📰 Sentimiento",
    "⚙️ Técnico"
])

# ─────────────────────────────────────────────────────────────
# TAB 1: PAPER TRADING
# ─────────────────────────────────────────────────────────────

with tab1:
    st.header("📚 Paper Trading")
    
    summary = paper_engine.get_portfolio_summary()
    regime = paper_engine.get_regime()
    
    # Resumen rápido
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("💰 Cash", fmt_money(summary['cash']))
    
    with col2:
        st.metric("📈 Posiciones", fmt_money(summary['positions_value']))
    
    with col3:
        st.metric("💵 Total", fmt_money(summary['total_value']))
    
    with col4:
        st.metric("📊 Return", fmt_pct(summary['return_pct']))
    
    st.divider()
    
    # Posiciones abiertas
    st.subheader("📍 Posiciones Abiertas")
    
    if summary['positions']:
        positions_data = []
        for pos in summary['positions']:
            positions_data.append({
                'Ticker': pos['ticker'],
                'Qty': pos['qty'],
                'Entry': fmt_money(pos['entry_price']),
                'Current': fmt_money(pos['current_price']),
                'P&L': f"{pnl_color(pos['pnl'])} {fmt_money(pos['pnl'])}",
                'Return': fmt_pct(pos['pnl_pct']),
            })
        
        df = pd.DataFrame(positions_data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Sin posiciones abiertas")
    
    st.divider()
    
    # Operaciones manuales
    st.subheader("🛒 Operaciones manuales")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        ticker = st.text_input("Ticker", value="MSFT", key="paper_ticker")
    
    with col2:
        action = st.selectbox("Acción", ["BUY", "SELL"], key="paper_action")
    
    with col3:
        quantity = st.number_input("Cantidad", min_value=1, value=1, key="paper_qty")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🛒 Comprar (Paper)", key="btn_buy_paper"):
            price = paper_engine.get_current_price(ticker)
            if price:
                result = paper_engine.execute_operation_manual(
                    ticker=ticker,
                    action="BUY",
                    quantity=quantity,
                    price=price,
                    origin=OPERATION_ORIGIN_MANUAL_DASHBOARD,
                    note="Compra vía Dashboard"
                )
                if result['success']:
                    st.success(result['message'])
                    st.rerun()
                else:
                    st.error(result['message'])
    
    with col2:
        if st.button("📊 Vender (Paper)", key="btn_sell_paper"):
            price = paper_engine.get_current_price(ticker)
            if price:
                result = paper_engine.execute_operation_manual(
                    ticker=ticker,
                    action="SELL",
                    quantity=quantity,
                    price=price,
                    origin=OPERATION_ORIGIN_MANUAL_DASHBOARD,
                    note="Venta vía Dashboard"
                )
                if result['success']:
                    st.success(result['message'])
                    st.rerun()
                else:
                    st.error(result['message'])
    
    st.divider()
    
    # Histórico
    st.subheader("📋 Histórico de operaciones")
    
    if paper_engine.state['trade_history']:
        history_data = []
        for trade in paper_engine.state['trade_history'][-10:]:  # Últimas 10
            history_data.append({
                'Fecha': trade['date'][-5:],  # HH:MM
                'Ticker': trade['ticker'],
                'Acción': trade['action'],
                'Qty': trade['quantity'],
                'Precio': fmt_money(trade['price']),
                'Total': fmt_money(trade['amount']),
                'Origin': trade['origin'],
                'Opinion': trade['bot_opinion'],
            })
        
        df = pd.DataFrame(history_data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Sin operaciones")

# ─────────────────────────────────────────────────────────────
# TAB 2: LIVE TRADING
# ─────────────────────────────────────────────────────────────

with tab2:
    st.header("🔴 Live Trading (Interactive Brokers)")
    
    if not live_connected:
        st.warning("""
        ⚠️ Live Trading no disponible
        
        Para habilitar:
        1. Instala: pip install ib-insync
        2. Abre IB Gateway (puerto 4002)
        3. Recarga esta página
        """)
    else:
        try:
            summary = live_broker.get_portfolio_summary()
            
            # Resumen rápido
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("💰 Cash", fmt_money(summary['cash']))
            
            with col2:
                st.metric("📈 Posiciones", fmt_money(summary['positions_value']))
            
            with col3:
                st.metric("💵 Total", fmt_money(summary['total_value']))
            
            with col4:
                st.metric("📊 Return", fmt_pct(summary['return_pct']))
            
            st.divider()
            
            # Posiciones
            st.subheader("📍 Posiciones Abiertas (DINERO REAL)")
            
            if summary['positions']:
                positions_data = []
                for pos in summary['positions']:
                    positions_data.append({
                        'Ticker': pos['ticker'],
                        'Qty': pos['qty'],
                        'Entry': fmt_money(pos['entry_price']),
                        'Current': fmt_money(pos['current_price']),
                        'P&L': f"{pnl_color(pos['pnl'])} {fmt_money(pos['pnl'])}",
                        'Return': fmt_pct(pos['pnl_pct']),
                    })
                
                df = pd.DataFrame(positions_data)
                st.dataframe(df, use_container_width=True)
            else:
                st.info("Sin posiciones abiertas")
            
            st.divider()
            
            # Operaciones (con advertencia)
            st.subheader("🛒 Operaciones manuales (DINERO REAL)")
            st.error("⚠️ TODAS LAS OPERACIONES USAN DINERO REAL")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                ticker = st.text_input("Ticker", value="MSFT", key="live_ticker")
            
            with col2:
                action = st.selectbox("Acción", ["BUY", "SELL"], key="live_action")
            
            with col3:
                quantity = st.number_input("Cantidad", min_value=1, value=1, key="live_qty")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🛒 COMPRAR REAL", key="btn_buy_live"):
                    st.warning("Confirmación requerida en Telegram para operar")
            
            with col2:
                if st.button("📊 VENDER REAL", key="btn_sell_live"):
                    st.warning("Confirmación requerida en Telegram para operar")
            
            st.divider()
            
            # Histórico
            st.subheader("📋 Histórico de operaciones")
            
            if live_broker.state.get('trade_history'):
                history_data = []
                for trade in live_broker.state['trade_history'][-10:]:
                    history_data.append({
                        'Fecha': trade['date'][-5:],
                        'Ticker': trade['ticker'],
                        'Acción': trade['action'],
                        'Qty': trade['quantity'],
                        'Precio': fmt_money(trade['price']),
                        'Total': fmt_money(trade['amount']),
                        'Origin': trade['origin'],
                    })
                
                df = pd.DataFrame(history_data)
                st.dataframe(df, use_container_width=True)
            else:
                st.info("Sin operaciones")
        
        except Exception as e:
            st.error(f"Error: {str(e)}")

# ─────────────────────────────────────────────────────────────
# TAB 3: FUNDAMENTAL (COMPARTIDO)
# ─────────────────────────────────────────────────────────────

with tab3:
    st.header("📊 Análisis Fundamental")
    st.info("✅ Este análisis es compartido para Paper + Live Trading")
    
    col1, col2 = st.columns(2)
    
    with col1:
        ticker = st.text_input("Ingresa ticker", value="AAPL", key="fund_ticker")
    
    with col2:
        if st.button("🔍 Analizar", key="btn_analyze_fundamental"):
            st.info("Análisis fundamental - en desarrollo")
    
    st.divider()
    st.markdown("""
    El análisis fundamental evalúa:
    - Crecimiento de ingresos
    - Rentabilidad
    - Deuda
    - Valoración (P/E, PEG)
    
    Resultado: Score 0-10 (igual para paper y live)
    """)

# ─────────────────────────────────────────────────────────────
# TAB 4: SENTIMIENTO (COMPARTIDO)
# ─────────────────────────────────────────────────────────────

with tab4:
    st.header("📰 Análisis de Sentimiento")
    st.info("✅ Este análisis es compartido para Paper + Live Trading")
    
    col1, col2 = st.columns(2)
    
    with col1:
        ticker = st.text_input("Ingresa ticker", value="TSLA", key="sent_ticker")
    
    with col2:
        if st.button("🔍 Analizar", key="btn_analyze_sentiment"):
            st.info("Análisis sentimiento - en desarrollo")
    
    st.divider()
    st.markdown("""
    El análisis sentimiento evalúa:
    - News sentiment
    - Social media (Reddit, Twitter)
    - Insider trading
    - Analyst ratings
    
    Resultado: Score 0-10 (igual para paper y live)
    """)

# ─────────────────────────────────────────────────────────────
# TAB 5: TÉCNICO (ESPECÍFICO DEL ENTORNO)
# ─────────────────────────────────────────────────────────────

with tab5:
    st.header("⚙️ Análisis Técnico")
    st.info("⚠️ Este análisis es específico del entorno seleccionado")
    
    # Selector de entorno
    environment = st.radio(
        "Selecciona entorno:",
        ["📚 Paper Trading", "🔴 Live Trading"],
        horizontal=True,
        key="tech_env"
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        ticker = st.text_input("Ingresa ticker", value="SPY", key="tech_ticker")
    
    with col2:
        if st.button("🔍 Analizar", key="btn_analyze_technical"):
            st.info("Análisis técnico - en desarrollo")
    
    st.divider()
    st.markdown(f"""
    Analizando: **{environment}**
    
    El análisis técnico evalúa:
    - SMA / EMA (medias móviles)
    - RSI (Relative Strength Index)
    - MACD (Moving Average Convergence Divergence)
    - Bollinger Bands
    - Volumen
    
    Resultado: BUY / HOLD / SELL
    (Según señales técnicas del entorno seleccionado)
    """)

# ═══════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════

st.divider()
st.markdown("""
---
**Investment Swarm Dashboard v2** | Paper + Live Trading |
Powered by CrewAI + Ollama + Interactive Brokers
""")