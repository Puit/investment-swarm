"""
TELEGRAM BOT v2 - MÁQUINA DE ESTADOS
=====================================

Versión mejorada con soporte para dual-mode (paper + live trading).

Estados:
- NO_TRADING: Visualización únicamente (ambos entornos)
- PAPER_TRADING: Operaciones en paper trading
- LIVE_TRADING: Operaciones en live trading (dinero real)
"""

import logging
from enum import Enum
from typing import Dict, Optional
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, ConversationHandler
)

logger = logging.getLogger(__name__)


class TradingMode(Enum):
    """Estados posibles del bot."""
    NO_TRADING = "no_trading"
    PAPER_TRADING = "paper_trading"
    LIVE_TRADING = "live_trading"


class TelegramTradingBotV2:
    """Bot de Telegram con máquina de estados para dual-mode trading."""
    
    def __init__(self, paper_engine, live_broker=None, chat_id: str = None):
        """
        Inicializa el bot.
        
        Args:
            paper_engine: PaperTradingEngine (paper trading)
            live_broker: InteractiveBrokersBroker (live trading)
            chat_id: Chat ID del usuario (para notificaciones)
        """
        self.paper_engine = paper_engine
        self.live_broker = live_broker
        self.chat_id = chat_id
        self.app = None
        
        # Estado de usuarios (dict: user_id → TradingMode)
        self.user_modes: Dict[int, TradingMode] = {}
        
        # Operaciones pendientes (dict: user_id → lista de operaciones)
        self.pending_operations: Dict[int, list] = {}
        
        logger.info("TelegramTradingBotV2 inicializado")
    
    async def setup(self, token: str) -> None:
        """Configura el bot con el token."""
        self.app = Application.builder().token(token).build()
        self._register_handlers()
        logger.info("Bot configurado con handlers")
    
    def _register_handlers(self) -> None:
        """Registra todos los handlers del bot."""
        
        # Comandos principales
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        
        # Cambio de modo
        self.app.add_handler(CommandHandler("no_trading", self.cmd_no_trading))
        self.app.add_handler(CommandHandler("paper_trading", self.cmd_paper_trading))
        self.app.add_handler(CommandHandler("live_trading", self.cmd_live_trading))
        
        # Comandos específicos del modo
        self.app.add_handler(CommandHandler("positions", self.cmd_positions))
        self.app.add_handler(CommandHandler("portfolio", self.cmd_portfolio))
        self.app.add_handler(CommandHandler("buy", self.cmd_buy))
        self.app.add_handler(CommandHandler("sell", self.cmd_sell))
        self.app.add_handler(CommandHandler("back", self.cmd_back))
        
        # Análisis
        self.app.add_handler(CommandHandler("fundamental", self.cmd_fundamental))
        self.app.add_handler(CommandHandler("sentiment", self.cmd_sentiment))
        self.app.add_handler(CommandHandler("technical", self.cmd_technical))
        
        # Callbacks
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
        
        logger.info("Handlers registrados")
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /start - Mostrar estado actual."""
        logger.info(f"✓ /start comando recibido de usuario {update.effective_user.id}")
        user_id = update.effective_user.id
        mode = self.user_modes.get(user_id, TradingMode.NO_TRADING)
        logger.info(f"  Modo actual: {mode}")

        # Obtener datos
        logger.info("  Obteniendo portfolio paper...")
        paper_portfolio = self.paper_engine.get_portfolio_summary()
        live_portfolio = None
        if self.live_broker and self.live_broker.connected:
            try:
                live_portfolio = self.live_broker.get_portfolio_summary()
            except:
                pass
        
        # Mensaje en HTML (más robusto que Markdown)
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

        logger.info(f"  Enviando respuesta al usuario...")
        await update.message.reply_text(text, parse_mode="HTML")
        logger.info(f"✓ Respuesta enviada exitosamente")
    
    async def cmd_no_trading(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /no_trading - Cambiar a modo visualización."""
        user_id = update.effective_user.id
        self.user_modes[user_id] = TradingMode.NO_TRADING
        
        text = """👁️ <b>Modo Visualización Activado</b>

Puedes ver posiciones y portfolio de ambos entornos.
No puedes hacer operaciones.

Comandos disponibles:
/positions - Ver posiciones (ambos)
/portfolio - Ver cartera (ambos)
/fundamental - Análisis fundamental (compartido)
/sentiment - Análisis sentimiento (compartido)
/help - Comandos disponibles

Para operar:
/paper_trading - Cambiar a paper trading
/live_trading - Cambiar a live trading
"""
        
        await update.message.reply_text(text, parse_mode="HTML")
    
    async def cmd_paper_trading(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /paper_trading - Cambiar a modo paper."""
        user_id = update.effective_user.id
        self.user_modes[user_id] = TradingMode.PAPER_TRADING
        
        portfolio = self.paper_engine.get_portfolio_summary()
        
        text = f"""📚 <b>Modo Paper Trading Activado</b>

📊 Estado actual:
  💰 Cash: ${portfolio['cash']:,.2f}
  📈 Total: ${portfolio['total_value']:,.2f}
  📍 Posiciones: {len(portfolio['positions'])}

Comandos disponibles:
/buy TICKER QTY - Comprar
/sell TICKER QTY - Vender
/positions - Ver posiciones
/portfolio - Ver cartera
/technical - Análisis técnico
/fundamental - Análisis fundamental (compartido)
/sentiment - Análisis sentimiento (compartido)
/back - Volver a visualización

⚠️ Paper trading: sin dinero real
"""
        
        await update.message.reply_text(text, parse_mode="HTML")
    
    async def cmd_live_trading(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /live_trading - Cambiar a modo live."""
        user_id = update.effective_user.id
        
        if not self.live_broker or not self.live_broker.connected:
            text = "❌ Live Trading no disponible.\n\nInteractive Brokers no está conectado."
            await update.message.reply_text(text, parse_mode="HTML")
            return
        
        self.user_modes[user_id] = TradingMode.LIVE_TRADING
        
        portfolio = self.live_broker.get_portfolio_summary()
        
        text = f"""🔴 <b>Modo Live Trading Activado</b>

<b>OPERANDO CON DINERO REAL</b>

📊 Estado actual:
  💰 Cash: ${portfolio['cash']:,.2f}
  📈 Total: ${portfolio['total_value']:,.2f}
  📍 Posiciones: {len(portfolio['positions'])}

Comandos disponibles:
/buy TICKER QTY - Comprar
/sell TICKER QTY - Vender
/positions - Ver posiciones
/portfolio - Ver cartera
/technical - Análisis técnico
/back - Volver a visualización

<b>⚠️ ADVERTENCIA: Operando con dinero real</b>
"""
        
        await update.message.reply_text(text, parse_mode="HTML")
    
    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /positions - Ver posiciones actuales."""
        user_id = update.effective_user.id
        mode = self.user_modes.get(user_id, TradingMode.NO_TRADING)
        
        text = "<b>📍 Posiciones</b>\n\n"
        
        # Paper Trading
        try:
            positions = self.paper_engine.get_positions()
            if positions:
                text += "<b>📚 Paper Trading:</b>\n"
                for ticker, qty in positions.items():
                    text += f"  {ticker}: {qty} shares\n"
            else:
                text += "<b>📚 Paper Trading:</b> Sin posiciones\n"
        except Exception as e:
            text += f"<b>📚 Paper Trading:</b> Error ({e})\n"
        
        # Live Trading
        if self.live_broker and self.live_broker.connected:
            try:
                positions = self.live_broker.get_positions()
                if positions:
                    text += "\n<b>🔴 Live Trading:</b>\n"
                    for ticker, qty in positions.items():
                        text += f"  {ticker}: {qty} shares\n"
                else:
                    text += "\n<b>🔴 Live Trading:</b> Sin posiciones\n"
            except Exception as e:
                text += f"\n<b>🔴 Live Trading:</b> Error ({e})\n"
        
        await update.message.reply_text(text, parse_mode="HTML")
    
    async def cmd_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /portfolio - Ver cartera."""
        user_id = update.effective_user.id
        
        text = "<b>💼 Cartera</b>\n\n"
        
        # Paper Trading
        try:
            portfolio = self.paper_engine.get_portfolio_summary()
            text += f"""<b>📚 Paper Trading:</b>
  💰 Cash: ${portfolio['cash']:,.2f}
  📈 Total: ${portfolio['total_value']:,.2f}
  📊 Posiciones: {len(portfolio['positions'])}
"""
        except Exception as e:
            text += f"<b>📚 Paper Trading:</b> Error ({e})\n"
        
        # Live Trading
        if self.live_broker and self.live_broker.connected:
            try:
                portfolio = self.live_broker.get_portfolio_summary()
                text += f"""
<b>🔴 Live Trading:</b>
  💰 Cash: ${portfolio['cash']:,.2f}
  📈 Total: ${portfolio['total_value']:,.2f}
  📊 Posiciones: {len(portfolio['positions'])}
"""
            except Exception as e:
                text += f"\n<b>🔴 Live Trading:</b> Error ({e})\n"
        
        await update.message.reply_text(text, parse_mode="HTML")
    
    def _format_mode(self, mode: TradingMode) -> str:
        """Formatea el modo de trading."""
        if mode == TradingMode.NO_TRADING:
            return "👁️ Visualización"
        elif mode == TradingMode.PAPER_TRADING:
            return "📚 Paper Trading"
        elif mode == TradingMode.LIVE_TRADING:
            return "🔴 Live Trading"
        return "❓ Desconocido"
    
    async def cmd_buy(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Placeholder para buy."""
        await update.message.reply_text("Comando /buy en desarrollo", parse_mode="HTML")
    
    async def cmd_sell(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Placeholder para sell."""
        await update.message.reply_text("Comando /sell en desarrollo", parse_mode="HTML")
    
    async def cmd_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Volver a visualización."""
        await self.cmd_no_trading(update, context)
    
    async def cmd_fundamental(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Placeholder para análisis fundamental."""
        await update.message.reply_text("Análisis fundamental en desarrollo", parse_mode="HTML")
    
    async def cmd_sentiment(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Placeholder para análisis de sentimiento."""
        await update.message.reply_text("Análisis de sentimiento en desarrollo", parse_mode="HTML")
    
    async def cmd_technical(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Placeholder para análisis técnico."""
        await update.message.reply_text("Análisis técnico en desarrollo", parse_mode="HTML")
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /help - Mostrar comandos disponibles."""
        text = """<b>📚 Comandos Disponibles</b>

<b>Modo:</b>
/no_trading - Visualización únicamente
/paper_trading - Operar en simulado
/live_trading - Operar con dinero real

<b>Posiciones y cartera:</b>
/positions - Ver posiciones (ambos)
/portfolio - Ver cartera (ambos)

<b>Operaciones (paper/live):</b>
/buy - Comprar
/sell - Vender
/back - Volver a visualización

<b>Análisis:</b>
/fundamental - Análisis fundamental (compartido)
/sentiment - Análisis sentimiento (compartido)
/technical - Análisis técnico

<b>Otros:</b>
/help - Este mensaje
"""
        await update.message.reply_text(text, parse_mode="HTML")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja callbacks de botones."""
        await update.callback_query.answer()
