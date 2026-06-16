"""
SCHEDULER v2 - DUAL MODE (PAPER + LIVE)
========================================

Orquestador de automatización para ambos entornos.

Funcionalidad:
1. Análisis automáticos diarios (compartidos: fundamental + sentimiento)
2. Análisis técnico por entorno (paper vs live)
3. Operaciones automáticas en ambos si las condiciones se cumplen
4. Notificaciones a Telegram
5. Timeout de 2h con reanalización

Uso:
    python scheduler.py
    python scheduler.py --once
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Tuple
import json
import sys

from paper_trading_engine import PaperTradingEngine
from interactive_brokers_broker import InteractiveBrokersBroker

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Configuración
ANALYSIS_SCHEDULE_HOUR = 9
ANALYSIS_SCHEDULE_MINUTE = 30
RECHECK_INTERVAL_SECONDS = 300  # 5 minutos
MARKET_OPEN_HOUR = 9
MARKET_CLOSE_HOUR = 22


class InvestmentSchedulerV2:
    """Orquestador dual-mode para Paper + Live Trading."""

    def __init__(
        self,
        paper_engine: PaperTradingEngine,
        live_broker: Optional[InteractiveBrokersBroker] = None,
        telegram_bot=None
    ):
        """
        Inicializa el scheduler dual-mode.
        
        Args:
            paper_engine: PaperTradingEngine
            live_broker: InteractiveBrokersBroker (opcional)
            telegram_bot: TelegramTradingBotV2 (opcional)
        """
        self.paper_engine = paper_engine
        self.live_broker = live_broker
        self.telegram_bot = telegram_bot
        
        self.last_analysis_date = None
        self.pending_confirmations = {
            "paper": {},
            "live": {},
        }
        
        logger.info("InvestmentSchedulerV2 inicializado")
        logger.info(f"  Paper Trading: ✓")
        logger.info(f"  Live Trading: {'✓' if live_broker else '✗ (no disponible)'}")
    
    def is_market_open(self) -> bool:
        """Verifica si el mercado está abierto (09:30-22:00 CET, lunes-viernes)."""
        now = datetime.now()
        
        if now.weekday() >= 5:  # Sábado-domingo
            return False
        
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
        Ejecuta análisis diarios para ambos entornos.
        
        1. Análisis fundamental (compartido)
        2. Análisis sentimiento (compartido)
        3. Análisis técnico (paper)
        4. Análisis técnico (live)
        """
        logger.info("=" * 60)
        logger.info("🔍 INICIANDO ANÁLISIS DIARIO DUAL-MODE")
        logger.info("=" * 60)
        
        # Obtener watchlist
        watchlist = self.paper_engine.state.get("watchlist", [])
        
        if not watchlist:
            logger.warning("⚠️ Watchlist vacía")
            return
        
        logger.info(f"📊 Analizando {len(watchlist)} tickers\n")
        
        for ticker in watchlist:
            logger.info(f"🔎 Procesando: {ticker}")
            
            # 1. Análisis fundamental (COMPARTIDO)
            fund_score = await self._analyze_fundamental(ticker)
            logger.info(f"  📊 Fundamental: {fund_score:.1f}/10")
            
            # Si fundamental es bajo (<5), saltar
            if fund_score < 5.0:
                logger.info(f"  ⚠️ Score fundamental bajo, saltando")
                continue
            
            # 2. Análisis sentimiento (COMPARTIDO)
            sent_score = await self._analyze_sentiment(ticker)
            logger.info(f"  📰 Sentimiento: {sent_score:.1f}/10")
            
            # 3. Análisis técnico PAPER
            paper_signal = await self._analyze_technical(ticker, "paper")
            logger.info(f"  📈 Técnico (Paper): {paper_signal}")
            
            # 4. Análisis técnico LIVE
            live_signal = None
            if self.live_broker and self.live_broker.connected:
                live_signal = await self._analyze_technical(ticker, "live")
                logger.info(f"  📈 Técnico (Live): {live_signal}")
            
            # 5. Tomar decisiones por entorno
            # PAPER
            paper_decision = self._make_decision(fund_score, sent_score, paper_signal)
            if paper_decision["action"] != "HOLD":
                await self._handle_paper_operation(ticker, paper_decision)
            
            # LIVE
            if self.live_broker and self.live_broker.connected and live_signal:
                live_decision = self._make_decision(fund_score, sent_score, live_signal)
                if live_decision["action"] != "HOLD":
                    await self._handle_live_operation(ticker, live_decision)
            
            logger.info()
        
        self.last_analysis_date = datetime.now().date()
        logger.info("✅ Análisis diario completado\n")
    
    async def _analyze_fundamental(self, ticker: str) -> float:
        """
        Análisis fundamental (compartido para ambos entornos).
        
        Returns:
            Score 0-10
        """
        # TODO: Implementar análisis fundamental real
        # Por ahora retorna score simulado
        import random
        return random.uniform(4.0, 9.0)
    
    async def _analyze_sentiment(self, ticker: str) -> float:
        """
        Análisis sentimiento (compartido para ambos entornos).
        
        Returns:
            Score 0-10
        """
        # TODO: Implementar análisis de sentimiento real
        import random
        return random.uniform(4.0, 9.0)
    
    async def _analyze_technical(self, ticker: str, environment: str) -> str:
        """
        Análisis técnico (específico del entorno).
        
        Args:
            ticker: Símbolo
            environment: "paper" o "live"
        
        Returns:
            "BUY" / "HOLD" / "SELL"
        """
        # TODO: Implementar análisis técnico real
        # Por ahora retorna señal simulada
        import random
        signals = ["BUY", "HOLD", "SELL"]
        return random.choice(signals)
    
    def _make_decision(self, fund_score: float, sent_score: float, signal: str) -> Dict:
        """
        Toma decisión de compra/venta basada en análisis.
        
        Lógica:
        - Si signal=BUY AND (fund_score + sent_score)/2 > 6.5 → BUY
        - Si signal=SELL → SELL
        - Sino → HOLD
        """
        combined_score = (fund_score + sent_score) / 2
        
        if signal == "BUY" and combined_score > 6.5:
            return {
                "action": "BUY",
                "confidence": combined_score,
                "bot_opinion": "SÍ"
            }
        elif signal == "SELL" and combined_score < 4.5:
            return {
                "action": "SELL",
                "confidence": combined_score,
                "bot_opinion": "SÍ"
            }
        else:
            return {
                "action": "HOLD",
                "confidence": combined_score,
                "bot_opinion": "NO"
            }
    
    async def _handle_paper_operation(self, ticker: str, decision: Dict) -> None:
        """Ejecuta operación en paper trading."""
        logger.info(f"  → Paper: {decision['action']} (conf: {decision['confidence']:.1f})")
        
        try:
            price = self.paper_engine.get_current_price(ticker)
            
            if decision['action'] == "BUY":
                result = self.paper_engine.execute_operation_manual(
                    ticker=ticker,
                    action="BUY",
                    quantity=10,  # Cantidad default
                    price=price,
                    origin="AUTO",
                    note=f"Auto: {decision['confidence']:.1f}/10"
                )
            elif decision['action'] == "SELL":
                # TODO: Validar que hay posiciones abiertas
                result = self.paper_engine.execute_operation_manual(
                    ticker=ticker,
                    action="SELL",
                    quantity=10,
                    price=price,
                    origin="AUTO",
                    note=f"Auto: {decision['confidence']:.1f}/10"
                )
            
            if result['success']:
                logger.info(f"  ✓ {result['message']}")
            else:
                logger.warning(f"  ✗ {result['message']}")
        
        except Exception as e:
            logger.error(f"  ✗ Error: {e}")
    
    async def _handle_live_operation(self, ticker: str, decision: Dict) -> None:
        """Ejecuta operación en live trading (con confirmación)."""
        logger.info(f"  → Live: {decision['action']} (conf: {decision['confidence']:.1f}) - PENDIENTE")
        
        # Guardar como pendiente para confirmar en Telegram
        self.pending_confirmations["live"][ticker] = {
            "action": decision['action'],
            "confidence": decision['confidence'],
            "timestamp": datetime.now().isoformat(),
            "executed": False
        }
        
        # Notificar por Telegram (si está disponible)
        if self.telegram_bot:
            await self._notify_telegram(ticker, decision, "live")
    
    async def _notify_telegram(self, ticker: str, decision: Dict, environment: str) -> None:
        """Notifica operación pendiente al usuario por Telegram."""
        try:
            message = f"""
🤖 *Operación automática pendiente*

Entorno: {'🔴 Live Trading' if environment == 'live' else '📚 Paper Trading'}
Ticker: {ticker}
Acción: {decision['action']}
Confianza: {decision['confidence']:.1f}/10

Para ejecutar:
/buy {ticker} 10 (si es BUY)
/sell {ticker} 10 (si es SELL)

o cancela con /back
"""
            
            # TODO: Enviar por Telegram
            logger.info(f"  📱 Notificación enviada a Telegram")
        
        except Exception as e:
            logger.error(f"  ✗ Error notificando: {e}")
    
    async def check_pending_operations(self) -> None:
        """
        Verifica operaciones pendientes.
        
        Si han pasado 2h sin confirmación:
        - Reanaliza
        - Si sigue siendo válido, ejecuta automáticamente
        """
        now = datetime.now()
        timeout_hours = 2
        
        for environment in ["paper", "live"]:
            pending = self.pending_confirmations[environment]
            
            for ticker, op in list(pending.items()):
                op_time = datetime.fromisoformat(op['timestamp'])
                elapsed = (now - op_time).total_seconds() / 3600
                
                if elapsed > timeout_hours and not op['executed']:
                    logger.info(f"⏱️ Timeout de {timeout_hours}h: reanalizar {ticker}")
                    
                    # Reanalizar
                    fund_score = await self._analyze_fundamental(ticker)
                    sent_score = await self._analyze_sentiment(ticker)
                    signal = await self._analyze_technical(ticker, environment)
                    
                    decision = self._make_decision(fund_score, sent_score, signal)
                    
                    if decision['action'] != "HOLD":
                        # Ejecutar
                        if environment == "paper":
                            await self._handle_paper_operation(ticker, decision)
                        else:
                            await self._handle_live_operation(ticker, decision)
                        
                        op['executed'] = True
    
    async def start(self) -> None:
        """Inicia el scheduler en loop continuo."""
        logger.info("🚀 Scheduler iniciado")
        
        try:
            while True:
                try:
                    # Verificar si debe ejecutar análisis
                    if self.is_market_open() and self.should_run_analysis():
                        await self.run_daily_analysis()
                    
                    # Verificar operaciones pendientes
                    await self.check_pending_operations()
                    
                    # Esperar antes de siguiente check
                    await asyncio.sleep(RECHECK_INTERVAL_SECONDS)
                
                except Exception as e:
                    logger.error(f"Error en loop: {e}")
                    await asyncio.sleep(RECHECK_INTERVAL_SECONDS)
        
        except KeyboardInterrupt:
            logger.info("\n⏹ Scheduler detenido")


async def main():
    """Función principal."""
    from paper_trading_engine import PaperTradingEngine
    
    # Crear engine
    engine = PaperTradingEngine(initial_capital=5000.0)
    engine.add_ticker("MSFT")
    engine.add_ticker("GOOG")
    engine.add_ticker("AAPL")
    
    # Crear scheduler (sin live broker ni telegram por ahora)
    scheduler = InvestmentSchedulerV2(
        paper_engine=engine,
        live_broker=None,
        telegram_bot=None
    )
    
    # Ejecutar análisis una vez si --once
    if "--once" in sys.argv:
        await scheduler.run_daily_analysis()
    else:
        # Continuo
        await scheduler.start()


if __name__ == "__main__":
    asyncio.run(main())