"""
TEST SUITE - INVESTMENT SWARM
==============================

Suite completa de tests para validar:
- Paper Trading Engine
- Telegram Bot
- Scheduler
- Dashboard
- Integraciones

Uso:
    python test_suite.py              # Ejecuta todos los tests
    python test_suite.py --verbose    # Con output detallado
    python test_suite.py --component paper_trading  # Solo un componente
"""

import sys
from pathlib import Path

# Agregar carpeta raíz al path (IMPORTANTE para imports)
root_path = str(Path(__file__).parent.parent)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

import json
import asyncio
from datetime import datetime
import unittest
from unittest.mock import patch, MagicMock

# Colores
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_section(title):
    """Imprime sección."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.ENDC}\n")

def print_test_result(test_name, passed, details=""):
    """Imprime resultado de test."""
    status = f"{Colors.GREEN}✓ PASS{Colors.ENDC}" if passed else f"{Colors.RED}✗ FAIL{Colors.ENDC}"
    print(f"{status} {test_name}")
    if details:
        print(f"   {Colors.YELLOW}{details}{Colors.ENDC}")

# ═════════════════════════════════════════════════════════════
# TEST 1: PAPER TRADING ENGINE
# ═════════════════════════════════════════════════════════════

class TestPaperTradingEngine(unittest.TestCase):
    """Tests para Paper Trading Engine."""
    
    def setUp(self):
        """Inicializa antes de cada test."""
        from paper_trading_engine import PaperTradingEngine
        self.engine = PaperTradingEngine(initial_capital=5000.0)
    
    def test_initialization(self):
        """Verifica inicialización."""
        self.assertEqual(self.engine.state["cash"], 5000.0)
        self.assertEqual(self.engine.state["watchlist"], [])
        self.assertEqual(len(self.engine.state["positions"]), 0)
        print_test_result("Inicialización del engine", True)
    
    def test_add_ticker(self):
        """Verifica agregar ticker."""
        self.engine.add_ticker("MSFT")
        self.assertIn("MSFT", self.engine.state["watchlist"])
        print_test_result("Agregar ticker a watchlist", True)
    
    def test_remove_ticker(self):
        """Verifica remover ticker."""
        self.engine.add_ticker("MSFT")
        self.engine.remove_ticker("MSFT")
        self.assertNotIn("MSFT", self.engine.state["watchlist"])
        print_test_result("Remover ticker de watchlist", True)
    
    def test_get_portfolio_summary(self):
        """Verifica resumen de cartera."""
        summary = self.engine.get_portfolio_summary()
        self.assertIn("cash", summary)
        self.assertIn("total_value", summary)
        self.assertIn("return_pct", summary)
        print_test_result("Obtener resumen de cartera", True)
    
    def test_get_regime(self):
        """Verifica obtener régimen."""
        regime = self.engine.get_regime()
        valid_regimes = ["BULLISH", "NEUTRAL", "BEAR_RALLY", "BEARISH"]
        self.assertIn(regime, valid_regimes)
        print_test_result(f"Obtener régimen ({regime})", True)
    
    def test_state_persistence(self):
        """Verifica persistencia de estado."""
        self.engine.add_ticker("GOOG")
        self.engine.save_state()
        
        # Crear nuevo engine
        from paper_trading_engine import PaperTradingEngine
        engine2 = PaperTradingEngine(initial_capital=5000.0)
        
        self.assertIn("GOOG", engine2.state["watchlist"])
        print_test_result("Persistencia de estado (save/load)", True)

# ═════════════════════════════════════════════════════════════
# TEST 2: TELEGRAM BOT
# ═════════════════════════════════════════════════════════════

class TestTelegramBot(unittest.TestCase):
    """Tests para Telegram Bot."""
    
    def setUp(self):
        """Inicializa antes de cada test."""
        from paper_trading_engine import PaperTradingEngine
        from telegram_bot import TelegramTradingBot
        self.engine = PaperTradingEngine(initial_capital=5000.0)
        self.bot = TelegramTradingBot(self.engine, chat_id="123456789")
    
    def test_initialization(self):
        """Verifica inicialización del bot."""
        self.assertIsNotNone(self.bot.engine)
        self.assertEqual(self.bot.chat_id, "123456789")
        print_test_result("Inicialización del Telegram Bot", True)
    
    def test_has_app(self):
        """Verifica que tiene aplicación."""
        self.assertIsNotNone(self.bot.app)
        print_test_result("Bot tiene aplicación (app)", True)
    
    def test_pending_operations_structure(self):
        """Verifica estructura de operaciones pendientes."""
        self.assertIsInstance(self.bot.pending_operations, dict)
        print_test_result("Estructura de operaciones pendientes", True)

# ═════════════════════════════════════════════════════════════
# TEST 3: SCHEDULER
# ═════════════════════════════════════════════════════════════

class TestScheduler(unittest.TestCase):
    """Tests para Scheduler."""
    
    def setUp(self):
        """Inicializa antes de cada test."""
        from paper_trading_engine import PaperTradingEngine
        from telegram_bot import TelegramTradingBot
        from scheduler import InvestmentScheduler
        
        self.engine = PaperTradingEngine(initial_capital=5000.0)
        self.telegram_bot = TelegramTradingBot(self.engine, chat_id="123456789")
        self.scheduler = InvestmentScheduler(self.engine, self.telegram_bot)
    
    def test_initialization(self):
        """Verifica inicialización del scheduler."""
        self.assertIsNotNone(self.scheduler.engine)
        self.assertIsNotNone(self.scheduler.telegram_bot)
        print_test_result("Inicialización del Scheduler", True)
    
    def test_market_hours_detection(self):
        """Verifica detección de horarios de mercado."""
        is_open = self.scheduler.is_market_open()
        self.assertIsInstance(is_open, bool)
        print_test_result(f"Detección de horarios de mercado ({is_open})", True)
    
    def test_should_run_analysis(self):
        """Verifica si debe ejecutar análisis."""
        should_run = self.scheduler.should_run_analysis()
        self.assertIsInstance(should_run, bool)
        print_test_result(f"Verificación de análisis diario ({should_run})", True)

# ═════════════════════════════════════════════════════════════
# TEST 4: INTEGRACIONES
# ═════════════════════════════════════════════════════════════

class TestIntegrations(unittest.TestCase):
    """Tests de integración entre componentes."""
    
    def setUp(self):
        """Inicializa antes de cada test."""
        from paper_trading_engine import PaperTradingEngine
        from telegram_bot import TelegramTradingBot
        from scheduler import InvestmentScheduler
        
        self.engine = PaperTradingEngine(initial_capital=5000.0)
        self.telegram_bot = TelegramTradingBot(self.engine, chat_id="123456789")
        self.scheduler = InvestmentScheduler(self.engine, self.telegram_bot)
    
    def test_engine_scheduler_integration(self):
        """Verifica integración engine-scheduler."""
        self.engine.add_ticker("MSFT")
        self.assertIn("MSFT", self.scheduler.engine.state["watchlist"])
        print_test_result("Integración Engine-Scheduler", True)
    
    def test_scheduler_telegram_integration(self):
        """Verifica integración scheduler-telegram."""
        self.assertIsNotNone(self.scheduler.telegram_bot)
        self.assertEqual(
            self.scheduler.telegram_bot.engine,
            self.scheduler.engine
        )
        print_test_result("Integración Scheduler-Telegram", True)
    
    def test_origin_tracking(self):
        """Verifica que se registra origin de operaciones."""
        self.engine.add_ticker("MSFT")
        
        # Simular operación manual
        price = 420.0
        result = self.engine.execute_operation_manual(
            ticker="MSFT",
            action="BUY",
            quantity=10,
            price=price,
            origin="MANUAL_DASHBOARD",
            note="Test operation"
        )
        
        if result["success"]:
            # Verificar que se registró origin
            last_trade = self.engine.state["trade_history"][-1]
            self.assertEqual(last_trade["origin"], "MANUAL_DASHBOARD")
            print_test_result("Tracking de origin en operaciones", True)
        else:
            self.fail(f"No se pudo ejecutar operación: {result['message']}")
    
    def test_bot_opinion_calculation(self):
        """Verifica cálculo de bot_opinion."""
        self.engine.add_ticker("MSFT")
        
        # Simular con análisis disponible
        self.engine.state["fundamental_analyses"]["MSFT"] = {
            "data": {"score": 8.0, "recommendation": "BUY"},
            "timestamp": datetime.now().isoformat()
        }
        
        # Calcular opinión
        bot_opinion = self.engine._calculate_bot_opinion(
            "MSFT",
            fundamental={"score": 8.0},
            technical={"direction": "BULLISH"},
            sentiment={"sentimiento": "POSITIVO"}
        )
        
        self.assertIn(bot_opinion, ["SÍ", "NO"])
        print_test_result(f"Cálculo de bot_opinion ({bot_opinion})", True)

# ═════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════

def run_tests(verbose=False, component=None):
    """Ejecuta todos los tests."""
    print_section("🧪 TEST SUITE - INVESTMENT SWARM")
    
    # Crear suite de tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Agregar tests según componente
    if component is None or component == "paper_trading":
        suite.addTests(loader.loadTestsFromTestCase(TestPaperTradingEngine))
    
    if component is None or component == "telegram":
        suite.addTests(loader.loadTestsFromTestCase(TestTelegramBot))
    
    if component is None or component == "scheduler":
        suite.addTests(loader.loadTestsFromTestCase(TestScheduler))
    
    if component is None or component == "integration":
        suite.addTests(loader.loadTestsFromTestCase(TestIntegrations))
    
    # Ejecutar tests
    runner = unittest.TextTestRunner(verbosity=2 if verbose else 1)
    result = runner.run(suite)
    
    # Resumen
    print_section("📊 RESUMEN DE TESTS")
    print(f"Tests ejecutados: {result.testsRun}")
    print(f"{Colors.GREEN}Passed: {result.testsRun - len(result.failures) - len(result.errors)}{Colors.ENDC}")
    if result.failures:
        print(f"{Colors.RED}Failures: {len(result.failures)}{Colors.ENDC}")
    if result.errors:
        print(f"{Colors.RED}Errors: {len(result.errors)}{Colors.ENDC}")
    
    return result.wasSuccessful()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Suite para Investment Swarm")
    parser.add_argument("--verbose", action="store_true", help="Output detallado")
    parser.add_argument("--component", choices=["paper_trading", "telegram", "scheduler", "integration"],
                       help="Ejecutar solo un componente")
    
    args = parser.parse_args()
    
    success = run_tests(verbose=args.verbose, component=args.component)
    sys.exit(0 if success else 1)