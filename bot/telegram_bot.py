"""
TELEGRAM BOT v2 - MÁQUINA DE ESTADOS
=====================================

Versión mejorada con soporte para dual-mode (paper + live trading).

Estados:
- NO_TRADING: Visualización únicamente (ambos entornos)
- PAPER_TRADING: Operaciones en paper trading
- LIVE_TRADING: Operaciones en live trading (dinero real)

Uso:
    bot = TelegramTradingBot(
        paper_engine=engine,
        live_broker=broker,
        chat_id="123456789"
    )
    await bot.start_polling()
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
        user_id = update.effective_user.id
        mode = self.user_modes.get(user_id, TradingMode.NO_TRADING)
        
        # Obtener datos
        paper_portfolio = self.paper_engine.get_portfolio_summary()
        live_portfolio = None
        if self.live_broker and self.live_broker.connected:
            try:
                live_portfolio = self.live_broker.get_portfolio_summary()
            except:
                pass
        
        # Mensaje
        text = f"""
🤖 *Investment Swarm Bot*

*Estado actual:* {self._format_mode(mode)}

📊 *Paper Trading*
  💰 Cash: ${paper_portfolio['cash']:,.2f}
  📈 Total: ${paper_portfolio['total_value']:,.2f}
  📍 Posiciones: {len(paper_portfolio['positions'])}
"""
        
        if live_portfolio:
            text += f"""
🔴 *Live Trading*
  💰 Cash: ${live_portfolio['cash']:,.2f}
  📈 Total: ${live_portfolio['total_value']:,.2f}
  📍 Posiciones: {len(live_portfolio['positions'])}
"""
        
        text += """
*Opciones:*
/paper_trading - Operar en paper
/live_trading - Operar en vivo
/no_trading - Solo visualizar
/help - Mostrar comandos
"""
        
        await update.message.reply_text(text, parse_mode="Markdown")
    
    async def cmd_no_trading(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /no_trading - Cambiar a modo visualización."""
        user_id = update.effective_user.id
        self.user_modes[user_id] = TradingMode.NO_TRADING
        
        text = """
👁️ *Modo Visualización Activado*

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
        
        await update.message.reply_text(text, parse_mode="Markdown")
    
    async def cmd_paper_trading(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /paper_trading - Cambiar a modo paper."""
        user_id = update.effective_user.id
        self.user_modes[user_id] = TradingMode.PAPER_TRADING
        
        portfolio = self.paper_engine.get_portfolio_summary()
        
        text = f"""
📚 *Modo Paper Trading Activado*

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
        
        await update.message.reply_text(text, parse_mode="Markdown")
    
    async def cmd_live_trading(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /live_trading - Cambiar a modo live."""
        user_id = update.effective_user.id
        
        if not self.live_broker or not self.live_broker.connected:
            await update.message.reply_text(
                "❌ Live trading no disponible\n"
                "Interactive Brokers no está conectado.",
                parse_mode="Markdown"
            )
            return
        
        self.user_modes[user_id] = TradingMode.LIVE_TRADING
        
        try:
            portfolio = self.live_broker.get_portfolio_summary()
            
            text = f"""
🔴 *Modo Live Trading Activado*

⚠️ *DINERO REAL - CUIDADO*

📊 Estado actual:
  💰 Cash: ${portfolio['cash']:,.2f}
  📈 Total: ${portfolio['total_value']:,.2f}
  📍 Posiciones: {len(portfolio['positions'])}

Comandos disponibles:
/buy TICKER QTY - Comprar (DINERO REAL)
/sell TICKER QTY - Vender (DINERO REAL)
/positions - Ver posiciones
/portfolio - Ver cartera
/technical - Análisis técnico
/fundamental - Análisis fundamental (compartido)
/sentiment - Análisis sentimiento (compartido)
/back - Volver a visualización

⚠️ TODAS LAS OPERACIONES SON CON DINERO REAL
"""
            
            await update.message.reply_text(text, parse_mode="Markdown")
        
        except Exception as e:
            logger.error(f"Error en live trading: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /positions - Ver posiciones."""
        user_id = update.effective_user.id
        mode = self.user_modes.get(user_id, TradingMode.NO_TRADING)
        
        text = "📍 *Open positions*\n\n"
        
        # Paper trading
        paper_portfolio = self.paper_engine.get_portfolio_summary()
        if paper_portfolio['positions']:
            text += "📚 *Paper Trading*\n"
            for pos in paper_portfolio['positions']:
                pnl_emoji = "📈" if pos['pnl'] >= 0 else "📉"
                text += f"\n{pos['ticker']}\n"
                text += f"  Qty: {pos['qty']}\n"
                text += f"  Entry: ${pos['entry_price']:.2f}\n"
                text += f"  Current: ${pos['current_price']:.2f}\n"
                text += f"  {pnl_emoji} P&L: ${pos['pnl']:.2f} ({pos['pnl_pct']:.2f}%)\n"
        else:
            text += "📚 *Paper Trading*\n  Sin posiciones\n"
        
        # Live trading
        if mode in [TradingMode.LIVE_TRADING, TradingMode.NO_TRADING]:
            if self.live_broker and self.live_broker.connected:
                try:
                    live_portfolio = self.live_broker.get_portfolio_summary()
                    if live_portfolio['positions']:
                        text += "\n🔴 *Live Trading*\n"
                        for pos in live_portfolio['positions']:
                            pnl_emoji = "📈" if pos['pnl'] >= 0 else "📉"
                            text += f"\n{pos['ticker']}\n"
                            text += f"  Qty: {pos['qty']}\n"
                            text += f"  Entry: ${pos['entry_price']:.2f}\n"
                            text += f"  Current: ${pos['current_price']:.2f}\n"
                            text += f"  {pnl_emoji} P&L: ${pos['pnl']:.2f} ({pos['pnl_pct']:.2f}%)\n"
                    else:
                        text += "\n🔴 *Live Trading*\n  Sin posiciones\n"
                except:
                    pass
        
        await update.message.reply_text(text, parse_mode="Markdown")
    
    async def cmd_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /portfolio - Ver cartera."""
        user_id = update.effective_user.id
        mode = self.user_modes.get(user_id, TradingMode.NO_TRADING)
        
        text = "📊 *Portfolio Summary*\n\n"
        
        # Paper
        paper = self.paper_engine.get_portfolio_summary()
        text += f"📚 *Paper Trading*\n"
        text += f"  💰 Cash: ${paper['cash']:,.2f}\n"
        text += f"  📈 Posiciones: ${paper['positions_value']:,.2f}\n"
        text += f"  💵 Total: ${paper['total_value']:,.2f}\n"
        text += f"  📊 Return: {paper['return_pct']:.2f}%\n"
        
        # Live
        if mode in [TradingMode.LIVE_TRADING, TradingMode.NO_TRADING]:
            if self.live_broker and self.live_broker.connected:
                try:
                    live = self.live_broker.get_portfolio_summary()
                    text += f"\n🔴 *Live Trading*\n"
                    text += f"  💰 Cash: ${live['cash']:,.2f}\n"
                    text += f"  📈 Posiciones: ${live['positions_value']:,.2f}\n"
                    text += f"  💵 Total: ${live['total_value']:,.2f}\n"
                except:
                    pass
        
        await update.message.reply_text(text, parse_mode="Markdown")
    
    async def cmd_buy(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /buy TICKER QTY - Comprar."""
        user_id = update.effective_user.id
        mode = self.user_modes.get(user_id, TradingMode.NO_TRADING)
        
        if mode == TradingMode.NO_TRADING:
            await update.message.reply_text(
                "❌ Primero selecciona modo:\n/paper_trading o /live_trading"
            )
            return
        
        try:
            args = context.args
            if len(args) < 2:
                await update.message.reply_text("Uso: /buy TICKER CANTIDAD")
                return
            
            ticker = args[0].upper()
            quantity = int(args[1])
            
            if mode == TradingMode.PAPER_TRADING:
                price = self.paper_engine.get_current_price(ticker)
                if price:
                    text = f"🛒 *Confirmar compra*\n\n"
                    text += f"Ticker: {ticker}\n"
                    text += f"Cantidad: {quantity}\n"
                    text += f"Precio: ${price:.2f}\n"
                    text += f"Total: ${price * quantity:,.2f}\n\n"
                    text += "¿Confirmar?"
                    
                    # Botones de confirmación
                    keyboard = [
                        [
                            InlineKeyboardButton("✅ Confirmar", callback_data=f"buy_paper_{ticker}_{quantity}"),
                            InlineKeyboardButton("❌ Cancelar", callback_data="cancel")
                        ]
                    ]
                    
                    await update.message.reply_text(
                        text,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode="Markdown"
                    )
            
            elif mode == TradingMode.LIVE_TRADING:
                price = self.live_broker.get_current_price(ticker)
                if price:
                    text = f"🔴 *COMPRA EN VIVO - DINERO REAL*\n\n"
                    text += f"Ticker: {ticker}\n"
                    text += f"Cantidad: {quantity}\n"
                    text += f"Precio: ${price:.2f}\n"
                    text += f"Total: ${price * quantity:,.2f}\n\n"
                    text += "⚠️ ESTA OPERACIÓN USARÁ DINERO REAL\n"
                    text += "¿Confirmar?"
                    
                    keyboard = [
                        [
                            InlineKeyboardButton("✅ CONFIRMAR", callback_data=f"buy_live_{ticker}_{quantity}"),
                            InlineKeyboardButton("❌ Cancelar", callback_data="cancel")
                        ]
                    ]
                    
                    await update.message.reply_text(
                        text,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode="Markdown"
                    )
        
        except Exception as e:
            logger.error(f"Error en /buy: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def cmd_sell(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /sell TICKER QTY - Vender."""
        user_id = update.effective_user.id
        mode = self.user_modes.get(user_id, TradingMode.NO_TRADING)
        
        if mode == TradingMode.NO_TRADING:
            await update.message.reply_text(
                "❌ Primero selecciona modo:\n/paper_trading o /live_trading"
            )
            return
        
        # Implementación similar a /buy pero para SELL
        await update.message.reply_text("Comando /sell - en desarrollo")
    
    async def cmd_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /back - Volver a /no_trading."""
        await self.cmd_no_trading(update, context)
    
    async def cmd_fundamental(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /fundamental - Análisis fundamental (compartido)."""
        await update.message.reply_text("Análisis fundamental - en desarrollo")
    
    async def cmd_sentiment(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /sentiment - Análisis sentimiento (compartido)."""
        await update.message.reply_text("Análisis sentimiento - en desarrollo")
    
    async def cmd_technical(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /technical - Análisis técnico (específico del modo)."""
        await update.message.reply_text("Análisis técnico - en desarrollo")
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /help - Mostrar ayuda."""
        text = """
🤖 *Investment Swarm Bot - Comandos*

*Modo:*
/start - Estado actual
/paper_trading - Cambiar a paper trading
/live_trading - Cambiar a live trading
/no_trading - Solo visualizar
/back - Volver

*Posiciones (todos los modos):*
/positions - Ver posiciones abiertas
/portfolio - Ver cartera completa

*Operaciones (paper/live):*
/buy TICKER QTY - Comprar
/sell TICKER QTY - Vender

*Análisis:*
/fundamental - Análisis fundamental (compartido)
/sentiment - Análisis sentimiento (compartido)
/technical - Análisis técnico (específico del modo)

*Otros:*
/help - Este mensaje
"""
        
        await update.message.reply_text(text, parse_mode="Markdown")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Callback para botones inline."""
        query = update.callback_query
        data = query.data
        
        await query.answer()
        
        if data == "cancel":
            await query.edit_message_text("❌ Operación cancelada")
        
        elif data.startswith("buy_paper_"):
            # Parsear: buy_paper_MSFT_10
            parts = data.split("_")
            ticker = parts[2]
            quantity = int(parts[3])
            
            # Ejecutar compra
            price = self.paper_engine.get_current_price(ticker)
            result = self.paper_engine.execute_operation_manual(
                ticker=ticker,
                action="BUY",
                quantity=quantity,
                price=price,
                origin="MANUAL_TELEGRAM",
                note=f"Compra vía Telegram: {quantity} {ticker}"
            )
            
            if result["success"]:
                await query.edit_message_text(f"✅ {result['message']}")
            else:
                await query.edit_message_text(f"❌ {result['message']}")
        
        elif data.startswith("buy_live_"):
            # Parsear: buy_live_MSFT_10
            parts = data.split("_")
            ticker = parts[2]
            quantity = int(parts[3])
            
            # Ejecutar compra en live
            result = self.live_broker.place_order(
                ticker=ticker,
                action="BUY",
                quantity=quantity,
                order_type="MARKET"
            )
            
            if result["success"]:
                await query.edit_message_text(f"✅ 🔴 ORDEN EJECUTADA\n\n{result['message']}")
            else:
                await query.edit_message_text(f"❌ {result['message']}")
    
    def _format_mode(self, mode: TradingMode) -> str:
        """Formatea el modo para mostrar."""
        modes = {
            TradingMode.NO_TRADING: "👁️ Visualización",
            TradingMode.PAPER_TRADING: "📚 Paper Trading",
            TradingMode.LIVE_TRADING: "🔴 Live Trading",
        }
        return modes.get(mode, "Desconocido")
    
    async def start_polling(self) -> None:
        """Inicia el bot en polling mode."""
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        logger.info("Bot iniciado en polling mode")
    
    async def stop(self) -> None:
        """Detiene el bot."""
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
        logger.info("Bot detenido")