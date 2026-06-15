"""
TELEGRAM BOT - INVESTMENT SWARM
================================

Bot de Telegram para:
1. Ejecutar operaciones manuales (/compra, /vende, /posiciones, etc.)
2. Recibir notificaciones de operaciones automáticas del scheduler
3. Confirmar/rechazar operaciones con timeout de 2h
4. Reportar estado del paper trading

Instalación:
    pip install python-telegram-bot

Configuración:
    1. Crear bot con BotFather en Telegram
    2. Obtener TELEGRAM_BOT_TOKEN
    3. Guardar en archivo .env o como variable de entorno

Uso:
    python telegram_bot.py
"""

import logging
import os
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict
import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler
from dotenv import load_dotenv

from paper_trading_engine import (
    PaperTradingEngine,
    OPERATION_ORIGIN_MANUAL_TELEGRAM,
)

# Cargar variables de entorno
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # Chat ID del usuario

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN no configurado. Añade en .env o como variable de entorno.")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Estados para conversaciones
AWAITING_BUY_TICKER, AWAITING_BUY_QUANTITY = range(2)
AWAITING_SELL_TICKER, AWAITING_SELL_QUANTITY = range(2, 4)

# Timeouts y pendientes
OPERATION_TIMEOUT_SECONDS = 2 * 3600  # 2 horas en segundos
PENDING_OPERATIONS_FILE = Path("data/pending_operations.json")


class TelegramTradingBot:
    """Bot de Telegram integrado con PaperTradingEngine."""

    def __init__(self, engine: PaperTradingEngine, chat_id: Optional[str] = None):
        self.engine = engine
        self.chat_id = chat_id or TELEGRAM_CHAT_ID
        self.pending_operations = self._load_pending_operations()
        self.app = None

    # ── Persistencia de operaciones pendientes ───────────────────

    def _load_pending_operations(self) -> Dict:
        """Carga operaciones pendientes desde disco."""
        if PENDING_OPERATIONS_FILE.exists():
            try:
                with open(PENDING_OPERATIONS_FILE, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_pending_operations(self) -> None:
        """Guarda operaciones pendientes en disco."""
        PENDING_OPERATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PENDING_OPERATIONS_FILE, "w") as f:
            json.dump(self.pending_operations, f, indent=2, default=str)

    # ── Comandos del usuario ─────────────────────────────────────

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /start - welcome."""
        welcome = """
🤖 Investment Swarm - Telegram Trading Bot

Available commands:
/buy - Buy stocks
/sell - Sell stocks
/positions - View open positions
/portfolio - View portfolio summary
/analysis - View available analysis
/preferences - Configure daily analysis
/help - View this help

Examples:
/buy MSFT 100  → Buy 100 MSFT
/sell GOOG 50   → Sell 50 GOOG
        """
        await update.message.reply_text(welcome)

    async def cmd_buy(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /buy TICKER QUANTITY."""
        try:
            if len(context.args) < 2:
                await update.message.reply_text(
                    "Usage: /buy TICKER QUANTITY\nExample: /buy MSFT 100"
                )
                return

            ticker = context.args[0].upper()
            try:
                quantity = int(context.args[1])
            except ValueError:
                await update.message.reply_text("Quantity must be a number")
                return

            if quantity <= 0:
                await update.message.reply_text("Quantity must be positive")
                return

            # Obtener precio actual
            price = self.engine.get_current_price(ticker)
            if not price:
                await update.message.reply_text(f"❌ Could not get price for {ticker}")
                return

            # Mostrar confirmación
            cost = quantity * price
            cash_after = self.engine.state["cash"] - cost
            keyboard = [
                [
                    InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_buy_{ticker}_{quantity}_{price}"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            message = f"""
🛒 Buy confirmation:

Ticker: {ticker}
Quantity: {quantity}
Price: ${price:.2f}
Amount: ${cost:,.2f}

Available cash: ${self.engine.state["cash"]:,.2f}
Cash after: ${cash_after:,.2f}

Confirm?
            """
            await update.message.reply_text(message, reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Error in /buy: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_sell(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /sell TICKER QUANTITY."""
        try:
            if len(context.args) < 2:
                await update.message.reply_text(
                    "Usage: /sell TICKER QUANTITY\nExample: /sell GOOG 50"
                )
                return

            ticker = context.args[0].upper()
            try:
                quantity = int(context.args[1])
            except ValueError:
                await update.message.reply_text("Quantity must be a number")
                return

            if quantity <= 0:
                await update.message.reply_text("Quantity must be positive")
                return

            # Verificar que tiene la posición
            if ticker not in self.engine.state["positions"]:
                await update.message.reply_text(f"❌ You don't have an open position in {ticker}")
                return

            total_qty = sum(lot["qty"] for lot in self.engine.state["positions"][ticker])
            if quantity > total_qty:
                await update.message.reply_text(
                    f"❌ You want to sell {quantity}, but you only have {total_qty}"
                )
                return

            # Obtener precio actual
            price = self.engine.get_current_price(ticker)
            if not price:
                await update.message.reply_text(f"❌ Could not get price for {ticker}")
                return

            # Mostrar confirmación
            value = quantity * price
            keyboard = [
                [
                    InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_sell_{ticker}_{quantity}_{price}"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            message = f"""
📊 Sell confirmation:

Ticker: {ticker}
Quantity: {quantity}
Price: ${price:.2f}
Amount: ${value:,.2f}

Confirm?
            """
            await update.message.reply_text(message, reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Error in /sell: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /positions - View open positions."""
        try:
            summary = self.engine.get_portfolio_summary()

            if not summary["positions"]:
                await update.message.reply_text("📭 No open positions")
                return

            message = "📊 Open positions:\n\n"
            for p in summary["positions"]:
                message += (
                    f"📌 {p['ticker']}\n"
                    f"   Qty: {p['qty']}\n"
                    f"   Entry: ${p['entry_price']:.2f}\n"
                    f"   Current: ${p['current_price']:.2f}\n"
                    f"   P&L: ${p['pnl']:.2f} ({p['pnl_pct']:+.2f}%)\n\n"
                )

            await update.message.reply_text(message)

        except Exception as e:
            logger.error(f"Error in /positions: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /portfolio - Portfolio summary."""
        try:
            summary = self.engine.get_portfolio_summary()

            message = f"""
💰 Portfolio summary:

Total value: ${summary['total_value']:,.2f}
Cash: ${summary['cash']:,.2f}
Positions: ${summary['positions_value']:,.2f}

Return: {summary['return_pct']:+.2f}%
Fees paid: ${summary['total_transaction_costs']:,.2f}

Regime: {self.engine.get_regime()}
Paused: {'🛑 YES' if summary['trading_paused'] else '✅ NO'}
            """
            await update.message.reply_text(message)

        except Exception as e:
            logger.error(f"Error in /portfolio: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_analysis(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /analysis - View available analysis."""
        try:
            fundamentals = self.engine.state["fundamental_analyses"]
            sentiments = self.engine.state["sentiment_analyses"]

            if not fundamentals and not sentiments:
                await update.message.reply_text("📭 No analysis available yet")
                return

            message = "📊 Available analysis:\n\n"

            if fundamentals:
                message += "Fundamental:\n"
                for ticker, entry in fundamentals.items():
                    score = entry.get("score", "?")
                    message += f"  • {ticker}: {score}/10\n"

            if sentiments:
                message += "\nSentiment:\n"
                for ticker, entry in sentiments.items():
                    sentiment = entry["data"].get("sentimiento", "?")
                    message += f"  • {ticker}: {sentiment}\n"

            await update.message.reply_text(message)

        except Exception as e:
            logger.error(f"Error in /analysis: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /help."""
        await self.cmd_start(update, context)

    # ── Callbacks de confirmación ────────────────────────────────

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja botones de confirmación/rechazo."""
        query = update.callback_query
        await query.answer()

        action = query.data

        if action == "cancel_operation":
            await query.edit_message_text("❌ Operation cancelled")
            return

        # Parsear acción
        parts = action.split("_")
        if len(parts) < 4:
            await query.edit_message_text("❌ Error procesando acción")
            return

        op_type = parts[1]  # "buy" o "sell"
        ticker = parts[2]
        quantity = int(parts[3])
        price = float("_".join(parts[4:]))  # Por si price tiene puntos

        try:
            if op_type == "buy":
                result = self.engine.execute_operation_manual(
                    ticker=ticker,
                    action="BUY",
                    quantity=quantity,
                    price=price,
                    origin=OPERATION_ORIGIN_MANUAL_TELEGRAM,
                    note=f"Usuario confirmó via Telegram"
                )
            elif op_type == "sell":
                result = self.engine.execute_operation_manual(
                    ticker=ticker,
                    action="SELL",
                    quantity=quantity,
                    price=price,
                    origin=OPERATION_ORIGIN_MANUAL_TELEGRAM,
                    note=f"Usuario confirmó via Telegram"
                )
            else:
                await query.edit_message_text("❌ Tipo de operación desconocido")
                return

            if result["success"]:
                trade = result["trade"]
                message = f"""
✅ Operation executed:

{result["message"]}

Bot Opinion: {trade['bot_opinion']}
Origin: {trade['origin']}
                """
                await query.edit_message_text(message)
            else:
                await query.edit_message_text(f"❌ {result['message']}")

        except Exception as e:
            logger.error(f"Error en callback: {e}")
            await query.edit_message_text(f"❌ Error: {e}")

    # ── Notificaciones desde scheduler ───────────────────────────

    async def notify_trade_opportunity(
        self, ticker: str, action: str, fundamental: Dict,
        technical: Dict, sentiment: Dict, operation_id: str
    ) -> None:
        """
        Notifica una oportunidad de compra automática.
        Espera confirmación del usuario durante 2h.

        Args:
            ticker: El ticker (MSFT, GOOG, etc.)
            action: "BUY" o "SELL"
            fundamental: Análisis fundamental
            technical: Análisis técnico
            sentiment: Análisis de sentimiento
            operation_id: ID único para esta operación (para timeout)
        """
        try:
            price = self.engine.get_current_price(ticker)
            if not price:
                logger.warning(f"Could not get price for {ticker}")
                return

            regime = self.engine.get_regime()

            message = f"""
🔔 Trading opportunity {action}:

Ticker: {ticker}
Price: ${price:.2f}
Regime: {regime}

📊 Analysis:
  Fundamental: {fundamental.get("score", "?")}/10 ({fundamental.get("recommendation")})
  Technical: {technical.get("señal")}
  Sentiment: {sentiment.get("sentimiento")}

⏰ You have 2 hours to respond (will execute automatically otherwise)
            """

            # Crear botones de confirmación
            keyboard = [
                [
                    InlineKeyboardButton("✅ Confirm", callback_data=f"auto_{action.lower()}_{ticker}_{operation_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_{operation_id}"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Guardar operación pendiente
            self.pending_operations[operation_id] = {
                "ticker": ticker,
                "action": action,
                "price": price,
                "created_at": datetime.now().isoformat(),
                "timeout_at": (datetime.now() + timedelta(seconds=OPERATION_TIMEOUT_SECONDS)).isoformat(),
                "fundamental": fundamental,
                "technical": technical,
                "sentiment": sentiment,
                "confirmed": False,
                "rejected": False,
            }
            self._save_pending_operations()

            # Enviar notificación
            if self.app:
                await self.app.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    reply_markup=reply_markup
                )

        except Exception as e:
            logger.error(f"Error sending notification: {e}")

    async def process_pending_operations(self) -> None:
        """
        Procesa operaciones pendientes que pasaron el timeout de 2h.
        Si el usuario no respondió, las ejecuta automáticamente (si sigue siendo válido).
        """
        now = datetime.now()

        for op_id, op_data in list(self.pending_operations.items()):
            timeout_at = datetime.fromisoformat(op_data["timeout_at"])

            if now > timeout_at and not op_data["confirmed"] and not op_data["rejected"]:
                # Pasó el timeout sin respuesta
                ticker = op_data["ticker"]
                action = op_data["action"]

                # Reanalizar
                fundamental = op_data["fundamental"]
                technical = self.engine.get_technical(ticker)
                sentiment = op_data["sentiment"]

                # Revalidar con decision engine
                decision = self.engine.decision_engine.evaluate_buy_opportunity_new(
                    ticker, fundamental, technical, sentiment
                )

                if decision.get("decision") == "BUY_CANDIDATE":
                    # Aún es válido → ejecutar automáticamente
                    price = self.engine.get_current_price(ticker)
                    if price:
                        quantity = max(1, int(self.engine.state["cash"] * 0.1 / price))
                        result = self.engine.execute_operation_manual(
                            ticker=ticker,
                            action=action,
                            quantity=quantity,
                            price=price,
                            origin="AUTO",
                            note=f"Ejecutada automáticamente después de timeout (sin respuesta user)"
                        )

                        if self.app:
                            message = f"✅ Executed automatically:\n{result['message']}"
                            await self.app.bot.send_message(chat_id=self.chat_id, text=message)

                        op_data["executed"] = True
                else:
                    # Ya no es válido → rechazar
                    op_data["rejected"] = True
                    if self.app:
                        message = f"⏰ Timeout: {action} opportunity for {ticker} is no longer valid"
                        await self.app.bot.send_message(chat_id=self.chat_id, text=message)

                self._save_pending_operations()

    # ── Inicialización del bot ───────────────────────────────────

    def setup_handlers(self, application: Application) -> None:
        """Registra todos los handlers de comandos."""
        application.add_handler(CommandHandler("start", self.cmd_start))
        application.add_handler(CommandHandler("buy", self.cmd_buy))
        application.add_handler(CommandHandler("sell", self.cmd_sell))
        application.add_handler(CommandHandler("positions", self.cmd_positions))
        application.add_handler(CommandHandler("portfolio", self.cmd_portfolio))
        application.add_handler(CommandHandler("analysis", self.cmd_analysis))
        application.add_handler(CommandHandler("help", self.cmd_help))
        application.add_handler(CallbackQueryHandler(self.button_callback))

    async def run(self) -> None:
        """Inicia el bot."""
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.setup_handlers(self.app)

        logger.info("🤖 Bot started. Waiting for commands...")
        await self.app.run_polling()


# ── Main ──────────────────────────────────────────────────────

def main():
    """Función principal."""
    engine = PaperTradingEngine(initial_capital=5000.0)
    bot = TelegramTradingBot(engine, chat_id=TELEGRAM_CHAT_ID)
    
    # Crear aplicación directamente
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    bot.app = app
    bot.setup_handlers(app)

    logger.info("🤖 Bot started. Waiting for commands...")
    app.run_polling()


if __name__ == "__main__":
    main()