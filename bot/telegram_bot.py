"""
TELEGRAM BOT v2 - MÁQUINA DE ESTADOS
=====================================
Versión mejorada con análisis fundamental, sentimiento y técnico.
"""

import logging
from enum import Enum
from typing import Dict, Optional
import sys
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import re

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)

# Agregar el directorio padre al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.fundamental_agent import create_fundamental_agent
from agents.sentiment_agent import create_sentiment_agent
from agents.technical_agent import create_technical_agent
from core.analysis_storage import AnalysisStorage
from crewai import Task, Crew, Process

logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=2)


class TradingMode(Enum):
    NO_TRADING = "no_trading"
    PAPER_TRADING = "paper_trading"
    LIVE_TRADING = "live_trading"


class TelegramTradingBotV2:
    def __init__(self, paper_engine, live_broker=None, chat_id: str = None):
        self.paper_engine = paper_engine
        self.live_broker = live_broker
        self.chat_id = chat_id
        self.app = None
        self.user_modes: Dict[int, TradingMode] = {}
        self.pending_operations: Dict[int, list] = {}
        logger.info("TelegramTradingBotV2 inicializado")
    
    async def setup(self, token: str) -> None:
        self.app = Application.builder().token(token).build()
        self._register_handlers()
        logger.info("Bot configurado con handlers")
    
    def _register_handlers(self) -> None:
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("no_trading", self.cmd_no_trading))
        self.app.add_handler(CommandHandler("paper_trading", self.cmd_paper_trading))
        self.app.add_handler(CommandHandler("live_trading", self.cmd_live_trading))
        self.app.add_handler(CommandHandler("positions", self.cmd_positions))
        self.app.add_handler(CommandHandler("portfolio", self.cmd_portfolio))
        self.app.add_handler(CommandHandler("buy", self.cmd_buy))
        self.app.add_handler(CommandHandler("sell", self.cmd_sell))
        self.app.add_handler(CommandHandler("back", self.cmd_back))
        self.app.add_handler(CommandHandler("fundamental", self.cmd_fundamental))
        self.app.add_handler(CommandHandler("sentiment", self.cmd_sentiment))
        self.app.add_handler(CommandHandler("technical", self.cmd_technical))
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
        logger.info("Handlers registrados")
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        mode = self.user_modes.get(user_id, TradingMode.NO_TRADING)
        
        paper_portfolio = self.paper_engine.get_portfolio_summary()
        live_portfolio = None
        if self.live_broker and self.live_broker.connected:
            try:
                live_portfolio = self.live_broker.get_portfolio_summary()
            except:
                pass
        
        text = f"""🤖 <b>Investment Swarm Bot</b>

<b>Estado actual:</b> {self._format_mode(mode)}

📊 <b>Paper Trading</b>
  💰 Cash: ${paper_portfolio['cash']:,.2f}
  📈 Total: ${paper_portfolio['total_value']:,.2f}
  📍 Posiciones: {len(paper_portfolio['positions'])}
"""
        if live_portfolio:
            text += f"""
🔴 <b>Live Trading</b>
  💰 Cash: ${live_portfolio['cash']:,.2f}
  📈 Total: ${live_portfolio['total_value']:,.2f}
  📍 Posiciones: {len(live_portfolio['positions'])}
"""
        text += """
<b>Opciones:</b>
/paper_trading - Operar en paper
/live_trading - Operar en vivo
/no_trading - Solo visualizar
/help - Mostrar comandos
"""
        await update.message.reply_text(text, parse_mode="HTML")
    
    async def cmd_no_trading(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        self.user_modes[user_id] = TradingMode.NO_TRADING
        text = """👁️ <b>Modo Visualización Activado</b>

Comandos disponibles:
/positions - Ver posiciones
/portfolio - Ver cartera
/fundamental TICKER - Análisis fundamental
/sentiment TICKER - Análisis sentimiento
/technical TICKER - Análisis técnico
/help - Comandos disponibles
"""
        await update.message.reply_text(text, parse_mode="HTML")
    
    async def cmd_paper_trading(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        self.user_modes[user_id] = TradingMode.PAPER_TRADING
        portfolio = self.paper_engine.get_portfolio_summary()
        text = f"""📚 <b>Modo Paper Trading Activado</b>

📊 Estado: ${portfolio['cash']:,.2f} cash, ${portfolio['total_value']:,.2f} total

/buy TICKER QTY - Comprar
/sell TICKER QTY - Vender
/fundamental TICKER - Análisis
/back - Volver
"""
        await update.message.reply_text(text, parse_mode="HTML")
    
    async def cmd_live_trading(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.live_broker or not self.live_broker.connected:
            await update.message.reply_text("❌ Live Trading no disponible", parse_mode="HTML")
            return
        
        user_id = update.effective_user.id
        self.user_modes[user_id] = TradingMode.LIVE_TRADING
        portfolio = self.live_broker.get_portfolio_summary()
        text = f"""🔴 <b>Modo Live Trading - DINERO REAL</b>

${portfolio['cash']:,.2f} disponible

⚠️ Operarás con dinero real
"""
        await update.message.reply_text(text, parse_mode="HTML")
    
    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        positions = self.paper_engine.get_positions()
        text = "<b>📍 Posiciones (Paper)</b>\n\n"
        if positions:
            for ticker, qty in positions.items():
                text += f"  {ticker}: {qty}\n"
        else:
            text += "Sin posiciones"
        await update.message.reply_text(text, parse_mode="HTML")
    
    async def cmd_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        portfolio = self.paper_engine.get_portfolio_summary()
        text = f"""<b>💼 Cartera (Paper)</b>

💰 Cash: ${portfolio['cash']:,.2f}
📈 Total: ${portfolio['total_value']:,.2f}
📍 Posiciones: {len(portfolio['positions'])}
"""
        await update.message.reply_text(text, parse_mode="HTML")
    
    def _format_mode(self, mode: TradingMode) -> str:
        modes = {
            TradingMode.NO_TRADING: "👁️ Visualización",
            TradingMode.PAPER_TRADING: "📚 Paper Trading",
            TradingMode.LIVE_TRADING: "🔴 Live Trading"
        }
        return modes.get(mode, "❓ Desconocido")
    
    async def cmd_buy(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("Comando /buy en desarrollo", parse_mode="HTML")
    
    async def cmd_sell(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("Comando /sell en desarrollo", parse_mode="HTML")
    
    async def cmd_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self.cmd_no_trading(update, context)
    
    async def cmd_fundamental(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args:
            await update.message.reply_text("Uso: /fundamental TICKER\nEjemplo: /fundamental AAPL", parse_mode="HTML")
            return

        ticker = context.args[0].upper()
        msg = await update.message.reply_text(f"📊 Analizando {ticker}...\n⏳ 1-2 minutos", parse_mode="HTML")

        try:
            def run_analysis():
                agent = create_fundamental_agent()
                task = Task(
                    description=f"""Analiza los fundamentos de {ticker} y responde SOLO en este JSON:
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
                crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
                result = crew.kickoff()
                output_str = str(result) if hasattr(result, 'output') else str(result)

                logger.info(f"CrewAI raw output: {output_str[:500]}")

                try:
                    # Intenta parsear directamente
                    data = json.loads(output_str)
                    if isinstance(data, dict):
                        return data
                except:
                    pass

                # Extrae JSON del texto
                json_match = re.search(r'\{[^{}]*"score"[^{}]*\}', output_str, re.DOTALL)
                if json_match:
                    try:
                        return json.loads(json_match.group(0))
                    except:
                        logger.warning(f"JSON extraction failed: {json_match.group(0)[:100]}")

                # Fallback: retorna datos por defecto
                logger.warning(f"No se pudo parsear JSON para {ticker}")
                return {
                    "score": 5,
                    "confidence": 50,
                    "risk_level": "MEDIUM",
                    "recommendation": "HOLD",
                    "summary": "Error en análisis - intenta de nuevo"
                }

            loop = asyncio.get_event_loop()
            analysis = await loop.run_in_executor(executor, run_analysis)

            # Guardar análisis para sincronizar con dashboard
            AnalysisStorage.save_analysis(ticker, "fundamental", analysis)

            if isinstance(analysis, dict) and "error" not in analysis:
                text = f"""📊 <b>Análisis Fundamental: {ticker}</b>

<b>Score:</b> {analysis.get('score', 'N/A')}/10
<b>Confianza:</b> {analysis.get('confidence', 'N/A')}%
<b>Riesgo:</b> {analysis.get('risk_level', 'N/A')}
<b>Recomendación:</b> {analysis.get('recommendation', 'N/A')}

<b>Resumen:</b> {analysis.get('summary', 'N/A')[:200]}

/sentiment {ticker} - Ver sentimiento
/technical {ticker} - Ver análisis técnico
"""
            else:
                text = f"❌ Error en análisis de {ticker}"

            await msg.edit_text(text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            await msg.edit_text(f"❌ Error: {str(e)}", parse_mode="HTML")
    
    async def cmd_sentiment(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args:
            await update.message.reply_text("Uso: /sentiment TICKER", parse_mode="HTML")
            return

        ticker = context.args[0].upper()
        msg = await update.message.reply_text(f"📰 Analizando sentimiento de {ticker}...\n⏳ 1-2 minutos", parse_mode="HTML")

        try:
            def run_analysis():
                agent = create_sentiment_agent()
                task = Task(
                    description=f"""Analiza el sentimiento de mercado para {ticker}.
                    Responde en JSON con: sentiment (POSITIVO/NEUTRO/NEGATIVO),
                    confidence (0-100), catalysts, summary""",
                    agent=agent,
                    expected_output="JSON con análisis de sentimiento"
                )
                crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
                result = crew.kickoff()
                output_str = str(result.raw) if hasattr(result, 'raw') else str(result)
                
                try:
                    return json.loads(output_str)
                except:
                    json_matches = list(re.finditer(r'\{[^{}]*\}', output_str))
                    if json_matches:
                        for match in reversed(json_matches):
                            try:
                                return json.loads(match.group(0))
                            except:
                                continue
                    return {"sentiment": "NEUTRO", "confidence": 50, "summary": output_str[:200]}

            loop = asyncio.get_event_loop()
            analysis = await loop.run_in_executor(executor, run_analysis)

            # Guardar análisis para sincronizar con dashboard
            AnalysisStorage.save_analysis(ticker, "sentiment", analysis)

            text = f"""📰 <b>Sentimiento: {ticker}</b>

<b>Sentimiento:</b> {analysis.get('sentiment', 'N/A')}
<b>Confianza:</b> {analysis.get('confidence', 'N/A')}%

<b>Catalizadores:</b> {analysis.get('catalysts', 'N/A')[:150]}

/technical {ticker} - Ver análisis técnico
/fundamental {ticker} - Ver análisis fundamental
"""
            await msg.edit_text(text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            await msg.edit_text(f"❌ Error: {str(e)}", parse_mode="HTML")
    
    async def cmd_technical(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args:
            await update.message.reply_text("Uso: /technical TICKER", parse_mode="HTML")
            return

        ticker = context.args[0].upper()
        msg = await update.message.reply_text(f"📈 Analizando {ticker}...\n⏳ 1-2 minutos", parse_mode="HTML")

        try:
            def run_analysis():
                agent = create_technical_agent()
                task = Task(
                    description=f"""Analiza el análisis técnico de {ticker} y responde SOLO en JSON:
                    {{
                        "signal": "BUY/HOLD/SELL",
                        "confidence": 0-100,
                        "support": "número",
                        "resistance": "número",
                        "summary": "análisis breve"
                    }}""",
                    agent=agent,
                    expected_output="JSON válido sin texto adicional"
                )
                crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
                result = crew.kickoff()
                output_str = str(result) if hasattr(result, 'output') else str(result)

                logger.info(f"Technical analysis output: {output_str[:500]}")

                try:
                    data = json.loads(output_str)
                    if isinstance(data, dict):
                        return data
                except:
                    pass

                json_match = re.search(r'\{[^{}]*"signal"[^{}]*\}', output_str, re.DOTALL)
                if json_match:
                    try:
                        return json.loads(json_match.group(0))
                    except:
                        logger.warning(f"JSON extraction failed for technical")

                return {
                    "signal": "HOLD",
                    "confidence": 50,
                    "support": "N/A",
                    "resistance": "N/A",
                    "summary": "Error - intenta de nuevo"
                }

            loop = asyncio.get_event_loop()
            analysis = await loop.run_in_executor(executor, run_analysis)

            # Guardar análisis para sincronizar con dashboard
            AnalysisStorage.save_analysis(ticker, "technical", analysis)

            text = f"""📈 <b>Análisis Técnico: {ticker}</b>

<b>Signal:</b> {analysis.get('signal', 'HOLD')}
<b>Confianza:</b> {analysis.get('confidence', 50)}%
<b>Soporte:</b> {analysis.get('support', 'N/A')}
<b>Resistencia:</b> {analysis.get('resistance', 'N/A')}

<b>Resumen:</b> {str(analysis.get('summary', 'N/A'))[:150]}
"""
            await msg.edit_text(text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            await msg.edit_text(f"❌ Error: {str(e)}", parse_mode="HTML")
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = """<b>📚 Comandos Disponibles</b>

<b>Análisis:</b>
/fundamental TICKER - Análisis fundamental
/sentiment TICKER - Sentimiento del mercado
/technical TICKER - Análisis técnico

<b>Cartera:</b>
/portfolio - Ver cartera
/positions - Ver posiciones

<b>Modo:</b>
/no_trading - Visualización
/paper_trading - Simulado
/live_trading - Dinero real

/help - Este mensaje
"""
        await update.message.reply_text(text, parse_mode="HTML")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.callback_query.answer()
