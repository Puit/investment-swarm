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

# Setup
load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))

from trading.paper_trading_engine import PaperTradingEngine, OPERATION_ORIGIN_MANUAL_DASHBOARD
from core.analysis_storage import AnalysisStorage
from agents.fundamental_agent import create_fundamental_agent
from agents.sentiment_agent import create_sentiment_agent
from agents.technical_agent import create_technical_agent
from crewai import Task, Crew, Process
import re

try:
    from brokers.freedom24_broker import Freedom24Broker
    LIVE_BROKER_AVAILABLE = True
except:
    LIVE_BROKER_AVAILABLE = False

st.set_page_config(page_title="Investment Swarm", page_icon="📈", layout="wide")

# ═══════════════════════════════════════════════════════════════
# INICIALIZACIÓN
# ═══════════════════════════════════════════════════════════════

if "paper_engine" not in st.session_state:
    st.session_state.paper_engine = PaperTradingEngine(initial_capital=5000.0)

if "live_broker" not in st.session_state and LIVE_BROKER_AVAILABLE:
    st.session_state.live_broker = Freedom24Broker()
    st.session_state.live_connected = st.session_state.live_broker.connect()
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

def pnl_color(x: float) -> str:
    return "🟢" if x >= 0 else "🔴"

def run_analysis_sync(ticker: str, analysis_type: str):
    """Ejecuta análisis de forma síncrona"""
    try:
        if analysis_type == "fundamental":
            agent = create_fundamental_agent()
            task = Task(
                description=f"""Analiza los fundamentos de {ticker} y responde SOLO en JSON:
                {{
                    "score": 0-10,
                    "confidence": 0-100,
                    "risk_level": "LOW/MEDIUM/HIGH",
                    "recommendation": "BUY/HOLD/SELL",
                    "summary": "análisis breve"
                }}""",
                agent=agent,
                expected_output="JSON válido sin texto adicional"
            )
        elif analysis_type == "sentiment":
            agent = create_sentiment_agent()
            task = Task(
                description=f"Analiza sentimiento de {ticker}",
                agent=agent,
                expected_output="JSON con sentimiento"
            )
        else:  # technical
            agent = create_technical_agent()
            task = Task(
                description=f"Analiza técnico de {ticker}",
                agent=agent,
                expected_output="JSON con signal"
            )

        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
        result = crew.kickoff()
        output_str = str(result)

        # Intenta parsear directamente
        try:
            data = json.loads(output_str)

            # Si es fundamental, busca dentro de la estructura anidada
            if analysis_type == "fundamental":
                if isinstance(data, dict) and "output" in data:
                    output_data = data["output"]
                    if isinstance(output_data, list) and len(output_data) > 0:
                        output_data = output_data[0].get("output", {})

                    # Normalizar a formato simple
                    return {
                        "score": output_data.get("score", 5),
                        "confidence": 80,
                        "risk_level": "MEDIUM",
                        "recommendation": "HOLD",
                        "summary": f"Score: {output_data.get('score', 'N/A')}/10. " +
                                 f"Ratios: P/E {output_data.get('ratiosFinancieros', {}).get('P/E', 'N/A')}, " +
                                 f"Debt/Equity {output_data.get('ratiosFinancieros', {}).get('deuda/equity', 'N/A')}"
                    }

            # Para sentiment y technical
            if isinstance(data, dict) and ("score" in data or "sentiment" in data or "signal" in data):
                return data

        except:
            pass

        # Fallback: busca JSONs en el texto
        json_matches = list(re.finditer(r'\{[^{}]*"score"[^{}]*\}|\{[^{}]*"sentiment"[^{}]*\}|\{[^{}]*"signal"[^{}]*\}', output_str, re.DOTALL))

        if json_matches:
            for match in reversed(json_matches):
                try:
                    data = json.loads(match.group(0))
                    if isinstance(data, dict):
                        return data
                except:
                    continue

        # Último fallback
        return {
            "score": 5 if analysis_type == "fundamental" else None,
            "sentiment": "NEUTRO" if analysis_type == "sentiment" else None,
            "signal": "HOLD" if analysis_type == "technical" else None,
            "confidence": 50,
            "summary": "Error en análisis - intenta de nuevo"
        }

    except Exception as e:
        st.error(f"Error: {e}")
        return None

# ═══════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════

st.markdown("# 📈 Investment Swarm Dashboard")

col1, col2, col3 = st.columns(3)
with col1:
    paper_portfolio = paper_engine.get_portfolio_summary()
    st.metric("📚 Paper Trading", fmt_money(paper_portfolio["total_value"]))

with col2:
    if live_connected:
        live_portfolio = live_broker.get_portfolio_summary()
        st.metric("🔴 Live Trading", fmt_money(live_portfolio["total_value"]))
    else:
        st.metric("🔴 Live Trading", "No disponible")

st.divider()

# ═══════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4 = st.tabs([
    "💰 Paper Trading",
    "🔴 Live Trading",
    "📊 Análisis",
    "🧪 Tests & Simulation"
])

# ─────────────────────────────────────────────────────────────
# TAB 1: PAPER TRADING
# ─────────────────────────────────────────────────────────────

with tab1:
    st.header("📚 Paper Trading")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Cartera")
        portfolio = paper_engine.get_portfolio_summary()
        st.metric("Total", fmt_money(portfolio["total_value"]))
        st.metric("Cash", fmt_money(portfolio["cash"]))

    with col2:
        st.subheader("Posiciones")
        portfolio = paper_engine.get_portfolio_summary()
        positions = portfolio.get("positions", [])
        if positions:
            df = pd.DataFrame([
                {
                    "Ticker": p["ticker"],
                    "Qty": p["qty"],
                    "Entrada": f"${p['entry_price']:.2f}",
                    "Actual": f"${p['current_price']:.2f}" if p['current_price'] else "N/A",
                    "PnL": f"${p['pnl']:.2f}",
                    "PnL%": f"{p['pnl_pct']:.2f}%"
                }
                for p in positions
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Sin posiciones")

# ─────────────────────────────────────────────────────────────
# TAB 2: LIVE TRADING
# ─────────────────────────────────────────────────────────────

with tab2:
    st.header("🔴 Live Trading")
    if live_connected:
        st.success("✓ Conectado a Freedom24")
        portfolio = live_broker.get_portfolio_summary()
        st.metric("Total", fmt_money(portfolio["total_value"]))

        # Mostrar posiciones
        positions = portfolio.get("positions", [])
        if positions:
            st.subheader("Posiciones")
            df = pd.DataFrame([
                {
                    "Ticker": p["ticker"],
                    "Qty": p["qty"],
                    "Entrada": f"${p['entry_price']:.2f}",
                    "Actual": f"${p['current_price']:.2f}",
                    "PnL": f"${p['pnl']:.2f}",
                    "PnL%": f"{p['pnl_pct']:.2f}%"
                }
                for p in positions
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ No disponible - Configura Freedom24 en .env (FREEDOM24_API_KEY, etc.)")

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
                            st.write(fund_data.get("summary", "Sin información"))

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

        # Botones de acción
        col_btn_execute, col_btn_clear = st.columns([0.7, 0.3])

        with col_btn_execute:
            btn_execute = st.button("▶️ EJECUTAR SIMULACIÓN", width="stretch", key="btn_run_backtest")

        with col_btn_clear:
            btn_clear = st.button("🗑️ Limpiar Caché", width="stretch", key="btn_clear_cache", help="Elimina todos los datos históricos guardados")

        # Mostrar info del caché
        cached_tickers = BacktestRunner.get_cached_tickers()
        cache_size = BacktestRunner.get_cache_size()

        if cached_tickers or cache_size != "0 B":
            st.caption(f"📊 Caché: {len(cached_tickers)} tickers • {cache_size}")

        # Manejo del botón de limpiar
        if btn_clear:
            st.warning("⚠️ ¿Estás seguro de que quieres eliminar TODO el histórico de datos?")

            col_confirm_yes, col_confirm_no = st.columns(2)

            with col_confirm_yes:
                if st.button("✅ Sí, eliminar todo", width="stretch", key="btn_confirm_clear"):
                    success, message = BacktestRunner.clear_all_cache()
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

            with col_confirm_no:
                if st.button("❌ Cancelar", width="stretch", key="btn_cancel_clear"):
                    st.rerun()

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
