"""
SCHEDULER - INVESTMENT SWARM
=============================

Orquestador de automatización. Corre continuamente o en horario específico.

Funcionalidad:
1. Análisis automáticos diarios según preferencias por ticker
2. Notificaciones a Telegram si hay oportunidad de compra
3. Timeout de 2h: si no hay respuesta, reanaliza
4. Ejecución automática si sigue siendo válido
5. Manejo de órdenes pendientes (mercado cerrado)

Uso:
    python scheduler.py          # Corre en loop continuo
    python scheduler.py --once   # Ejecuta una vez (para testing)

Alternativa: Usar APScheduler para horarios específicos
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict
import json
import sys

from paper_trading_engine import PaperTradingEngine
from telegram_bot import TelegramTradingBot

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Configuración ──
ANALYSIS_SCHEDULE_HOUR = 9  # 09:00 cada día (hora española)
ANALYSIS_SCHEDULE_MINUTE = 30
RECHECK_INTERVAL_SECONDS = 300  # Revisar cada 5 minutos si hay confirmaciones pendientes
MARKET_OPEN_HOUR = 9  # 09:30 mercado abre
MARKET_CLOSE_HOUR = 22  # 22:00 mercado cierra


class InvestmentScheduler:
    """Orquestador de análisis automáticos y ejecución de operaciones."""

    def __init__(self, engine: PaperTradingEngine, telegram_bot: TelegramTradingBot):
        self.engine = engine
        self.telegram_bot = telegram_bot
        self.last_analysis_date = None
        self.pending_confirmations = {}

    def is_market_open(self) -> bool:
        """Verifica si el mercado está abierto (09:30 - 22:00 CET, lunes-viernes)."""
        now = datetime.now()
        
        # Solo de lunes a viernes
        if now.weekday() >= 5:  # Sábado = 5, Domingo = 6
            return False
        
        # Entre 09:30 y 22:00
        current_time = now.hour + now.minute / 60
        return 9.5 <= current_time < 22.0

    def should_run_analysis(self) -> bool:
        """Verifica si ya corrió análisis hoy."""
        today = datetime.now().date()
        
        if self.last_analysis_date is None:
            return True
        
        if self.last_analysis_date != today:
            return True
        
        return False

    async def run_daily_analysis(self) -> None:
        """
        Ejecuta análisis diarios para cada ticker en la watchlist.
        
        Flujo:
        1. Para cada ticker: ejecuta análisis según preferencias
        2. Corre decision engine
        3. Si BUY: notifica a Telegram + aguarda respuesta (2h timeout)
        """
        if not self.should_run_analysis():
            logger.info("Análisis ya ejecutado hoy, saltando...")
            return

        watchlist = self.engine.state["watchlist"]
        if not watchlist:
            logger.info("Watchlist vacía, nada que analizar")
            return

        logger.info(f"🔍 Iniciando análisis diarios para {len(watchlist)} tickers...")

        for ticker in watchlist:
            try:
                await self._analyze_and_notify_ticker(ticker)
            except Exception as e:
                logger.error(f"Error analizando {ticker}: {e}")

        self.last_analysis_date = datetime.now().date()
        logger.info("✅ Análisis diarios completados")

    async def _analyze_and_notify_ticker(self, ticker: str) -> None:
        """
        Analiza un ticker y notifica a Telegram si hay oportunidad de compra.
        """
        logger.info(f"  Analizando {ticker}...")

        # Obtener preferencias
        prefs = self.engine.get_analysis_preference(ticker)
        
        # Análisis fundamental (si está habilitado)
        fundamental = None
        if prefs.get("daily_fundamental", False):
            logger.info(f"    → Fundamental...")
            self.engine.run_fundamental_analysis(ticker, force=False)
            fund_entry = self.engine.get_fundamental(ticker)
            if fund_entry:
                fundamental = fund_entry["data"]
        else:
            # Usar el último análisis o default
            fund_entry = self.engine.get_fundamental(ticker)
            if fund_entry:
                fundamental = fund_entry["data"]

        # Análisis técnico (SIEMPRE)
        logger.info(f"    → Technical...")
        technical = self.engine.get_technical(ticker)

        # Análisis sentimiento (si está habilitado)
        sentiment = None
        if prefs.get("daily_sentiment", False):
            logger.info(f"    → Sentiment...")
            self.engine.run_sentiment_analysis(ticker, force=False)
            sent_entry = self.engine.get_sentiment(ticker)
            if sent_entry:
                sentiment = sent_entry["data"]
        else:
            # Usar el último análisis o default
            sent_entry = self.engine.get_sentiment(ticker)
            if sent_entry:
                sentiment = sent_entry["data"]

        # Decision engine
        if not fundamental or not technical:
            logger.warning(f"  Análisis incompleto para {ticker}, saltando...")
            return

        decision = self.engine.decision_engine.evaluate_buy_opportunity_new(
            ticker, fundamental, technical, sentiment
        )

        if decision.get("decision") != "BUY_CANDIDATE":
            logger.info(f"  ⊘ {ticker}: No es BUY_CANDIDATE ({decision.get('reason')})")
            return

        # BUY_CANDIDATE encontrado → notificar a Telegram
        logger.info(f"  🟢 {ticker}: BUY_CANDIDATE! Notificando a Telegram...")

        operation_id = f"{ticker}_{datetime.now().isoformat()}"
        
        # Guardar operación pendiente
        self.pending_confirmations[operation_id] = {
            "ticker": ticker,
            "action": "BUY",
            "fundamental": fundamental,
            "technical": technical,
            "sentiment": sentiment,
            "created_at": datetime.now().isoformat(),
            "timeout_at": (datetime.now() + timedelta(hours=2)).isoformat(),
            "market_open_at_creation": self.is_market_open(),
            "confirmed": False,
            "rejected": False,
            "executed": False,
        }

        # Enviar notificación a Telegram
        if self.telegram_bot and self.telegram_bot.app:
            await self.telegram_bot.notify_trade_opportunity(
                ticker=ticker,
                action="BUY",
                fundamental=fundamental,
                technical=technical,
                sentiment=sentiment,
                operation_id=operation_id
            )
            logger.info(f"  📲 Notificación enviada a Telegram")

    async def process_pending_operations(self) -> None:
        """
        Procesa operaciones pendientes que completaron su timeout de 2h.
        
        Lógica:
        - Si timeout >= 2h y sin respuesta del usuario
          ├─ Si mercado abierto: reanaliza
          │  ├─ Si sigue siendo válido: ejecuta
          │  └─ Si no es válido: cancela
          └─ Si mercado cerrado: guarda como orden pendiente
        """
        now = datetime.now()
        
        for op_id, op_data in list(self.pending_confirmations.items()):
            timeout_at = datetime.fromisoformat(op_data["timeout_at"])
            
            # Solo procesar si pasó timeout y no fue confirmada/rechazada
            if now <= timeout_at or op_data["confirmed"] or op_data["rejected"]:
                continue

            logger.info(f"⏰ Timeout de 2h para {op_id}")

            ticker = op_data["ticker"]
            
            # Reanalizar
            logger.info(f"  📊 Reanalizado {ticker}...")
            
            fundamental = op_data["fundamental"]
            technical = self.engine.get_technical(ticker)
            sentiment = op_data["sentiment"]

            decision = self.engine.decision_engine.evaluate_buy_opportunity_new(
                ticker, fundamental, technical, sentiment
            )

            still_valid = decision.get("decision") == "BUY_CANDIDATE"

            if self.is_market_open():
                # Mercado abierto
                if still_valid:
                    logger.info(f"  🟢 {ticker}: Aún es válido, ejecutando...")
                    await self._execute_auto_trade(ticker, op_data)
                    op_data["executed"] = True
                else:
                    logger.info(f"  🔴 {ticker}: Ya no es válido, cancelando...")
                    op_data["rejected"] = True
                    
                    # Notificar a Telegram
                    if self.telegram_bot and self.telegram_bot.app:
                        msg = f"⏰ Timeout: Oportunidad de BUY en {ticker} ya no es válida"
                        await self.telegram_bot.app.bot.send_message(
                            chat_id=self.telegram_bot.chat_id,
                            text=msg
                        )
            else:
                # Mercado cerrado
                logger.info(f"  🌙 Mercado cerrado, guardando orden para mañana...")
                op_data["is_pending_for_tomorrow"] = True
                # Notificar a Telegram
                if self.telegram_bot and self.telegram_bot.app:
                    msg = f"🌙 Orden pendiente para mañana (apertura de mercado): BUY {ticker}"
                    await self.telegram_bot.app.bot.send_message(
                        chat_id=self.telegram_bot.chat_id,
                        text=msg
                    )

    async def execute_pending_for_tomorrow(self) -> None:
        """
        Ejecuta órdenes pendientes al abrir el mercado (si no fueron rechazadas).
        """
        logger.info("📈 Verificando órdenes pendientes para hoy...")
        
        market_just_opened = False
        now = datetime.now()
        current_time = now.hour + now.minute / 60
        
        # Si está entre 09:30 y 10:00, consideramos que acaba de abrir
        if 9.5 <= current_time < 10.0 and now.weekday() < 5:
            market_just_opened = True

        if not market_just_opened:
            return

        for op_id, op_data in list(self.pending_confirmations.items()):
            if not op_data.get("is_pending_for_tomorrow"):
                continue
            
            if op_data["confirmed"] or op_data["rejected"] or op_data["executed"]:
                continue

            ticker = op_data["ticker"]
            logger.info(f"  Ejecutando orden pendiente: BUY {ticker}")

            await self._execute_auto_trade(ticker, op_data)
            op_data["executed"] = True

    async def _execute_auto_trade(self, ticker: str, op_data: Dict) -> None:
        """
        Ejecuta una operación automática.
        """
        try:
            price = self.engine.get_current_price(ticker)
            if not price:
                logger.error(f"  ❌ No se pudo obtener precio para {ticker}")
                return

            # Usar el 10% del cash disponible para esta operación
            amount_to_invest = self.engine.state["cash"] * 0.1
            quantity = max(1, int(amount_to_invest / price))

            result = self.engine.execute_operation_manual(
                ticker=ticker,
                action="BUY",
                quantity=quantity,
                price=price,
                origin="AUTO",
                note=f"Ejecutada automáticamente por scheduler después de timeout de 2h"
            )

            if result["success"]:
                logger.info(f"  ✅ {result['message']}")
                
                # Notificar a Telegram
                if self.telegram_bot and self.telegram_bot.app:
                    msg = f"✅ Ejecutada automáticamente:\n{result['message']}"
                    await self.telegram_bot.app.bot.send_message(
                        chat_id=self.telegram_bot.chat_id,
                        text=msg
                    )
            else:
                logger.error(f"  ❌ {result['message']}")

        except Exception as e:
            logger.error(f"  ❌ Error ejecutando {ticker}: {e}")

    async def run_continuous(self, check_interval: int = RECHECK_INTERVAL_SECONDS) -> None:
        """
        Corre el scheduler continuamente.
        
        Lógica:
        - Cada día a hora X: ejecuta análisis diarios
        - Cada check_interval: procesa operaciones pendientes con timeout
        """
        logger.info(f"🚀 Scheduler iniciado (check cada {check_interval}s)")

        last_check_time = None

        while True:
            try:
                now = datetime.now()

                # Verificar si es hora de análisis diarios
                current_hour_min = now.hour + now.minute / 60
                target_hour_min = ANALYSIS_SCHEDULE_HOUR + ANALYSIS_SCHEDULE_MINUTE / 60

                if abs(current_hour_min - target_hour_min) < 0.05:  # Dentro de 3 minutos
                    if last_check_time is None or (now - last_check_time).seconds > 120:
                        await self.run_daily_analysis()
                        last_check_time = now

                # Procesar operaciones pendientes
                await self.process_pending_operations()

                # Ejecutar órdenes pendientes para mañana
                await self.execute_pending_for_tomorrow()

                # Esperar antes del siguiente chequeo
                await asyncio.sleep(check_interval)

            except Exception as e:
                logger.error(f"Error en loop principal: {e}")
                await asyncio.sleep(check_interval)

    def run_once(self) -> None:
        """
        Ejecuta una sola vez (para testing o manual).
        """
        logger.info("Ejecutando scheduler una sola vez...")
        asyncio.run(self.run_daily_analysis())
        logger.info("✅ Completado")


# ── Main ──

async def main_async():
    """Función principal async."""
    engine = PaperTradingEngine(initial_capital=5000.0)
    telegram_bot = TelegramTradingBot(engine)
    
    scheduler = InvestmentScheduler(engine, telegram_bot)
    
    # Ejecutar scheduler en loop continuo
    await scheduler.run_continuous()


def main():
    """Función principal."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Investment Swarm Scheduler")
    parser.add_argument("--once", action="store_true", help="Ejecuta una sola vez (testing)")
    parser.add_argument("--time", default="09:30", help="Hora de análisis diarios (HH:MM)")
    args = parser.parse_args()

    # Parsear hora
    if args.time:
        try:
            hour, minute = map(int, args.time.split(":"))
            globals()["ANALYSIS_SCHEDULE_HOUR"] = hour
            globals()["ANALYSIS_SCHEDULE_MINUTE"] = minute
            logger.info(f"⏰ Análisis programados para {hour:02d}:{minute:02d} CET")
        except ValueError:
            logger.warning(f"Formato de hora inválido: {args.time}, usando default 09:30")

    engine = PaperTradingEngine(initial_capital=5000.0)
    telegram_bot = TelegramTradingBot(engine)
    scheduler = InvestmentScheduler(engine, telegram_bot)

    if args.once:
        logger.info("Modo: Ejecutar una sola vez")
        scheduler.run_once()
    else:
        logger.info("Modo: Loop continuo")
        logger.info(f"💬 Telegram Bot debe estar corriendo en otra terminal")
        try:
            asyncio.run(scheduler.run_continuous())
        except KeyboardInterrupt:
            logger.info("Scheduler detenido por usuario")


if __name__ == "__main__":
    main()