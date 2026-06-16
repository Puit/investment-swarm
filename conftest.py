"""
Configuración compartida de tests (pytest).

Proporciona fixtures reutilizables para todos los tests.

Fixtures disponibles:
- paper_trading_engine: Instancia limpia del engine
- telegram_bot: Instancia limpia del bot
- scheduler: Instancia limpia del scheduler
"""

import sys
from pathlib import Path

# Agregar carpeta raíz al path
sys.path.insert(0, str(Path(__file__).parent))

import pytest
from paper_trading_engine import PaperTradingEngine
from telegram_bot import TelegramTradingBot
from scheduler import InvestmentScheduler


@pytest.fixture
def paper_trading_engine():
    """Fixture: Paper Trading Engine limpio."""
    engine = PaperTradingEngine(initial_capital=5000.0)
    yield engine
    # Cleanup: limpiar estado después del test
    engine.state["watchlist"].clear()
    engine.state["positions"].clear()


@pytest.fixture
def telegram_bot(paper_trading_engine):
    """Fixture: Telegram Bot con engine limpio."""
    bot = TelegramTradingBot(paper_trading_engine, chat_id="123456789")
    yield bot
    # Cleanup
    bot.pending_operations.clear()


@pytest.fixture
def scheduler(paper_trading_engine, telegram_bot):
    """Fixture: Scheduler con engine y bot limpios."""
    scheduler = InvestmentScheduler(paper_trading_engine, telegram_bot)
    yield scheduler
    # Cleanup
    scheduler.pending_confirmations.clear()


@pytest.fixture
def sample_ticker(paper_trading_engine):
    """Fixture: Agrega un ticker de prueba."""
    paper_trading_engine.add_ticker("MSFT")
    yield "MSFT"
    paper_trading_engine.remove_ticker("MSFT")


@pytest.fixture
def sample_portfolio(paper_trading_engine):
    """Fixture: Crea una cartera con tickers."""
    tickers = ["MSFT", "GOOG", "AAPL"]
    for ticker in tickers:
        paper_trading_engine.add_ticker(ticker)
    yield tickers
    for ticker in tickers:
        paper_trading_engine.remove_ticker(ticker)