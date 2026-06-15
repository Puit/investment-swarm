import os
import sys
from dotenv import load_dotenv
load_dotenv()

import logging
from datetime import datetime, date
from pytz import timezone
from pathlib import Path

from broker_manager import BrokerManager
from scheduler import AnalysisScheduler, log_scheduler_info
from crew import (
    scheduled_search,
    scheduled_confirm,
    scheduled_execute,
    scheduled_review,
)
from config import MARKET_TIMEZONE, SIMULATION_MODE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("Main")


class InvestmentSwarmApp:
    """Aplicación principal que orquesta todo el sistema"""

    def __init__(self):
        self.broker = BrokerManager()
        self.scheduler = AnalysisScheduler()
        self.running = False

    def initialize(self) -> bool:
        """Inicializa la aplicación"""
        logger.info("="*70)
        logger.info("🚀 INVESTMENT SWARM - INICIALIZANDO")
        logger.info("="*70)

        # Conectar con broker (simulación o real)
        if SIMULATION_MODE:
            logger.info("📊 Modo SIMULACIÓN activado")
            capital = self.broker.get_available_capital()
            logger.info(f"💰 Capital simulado: ${capital:.2f}")
        else:
            logger.info("🔗 Conectando con Interactive Brokers...")
            if not self.broker.connect():
                logger.error("❌ No se pudo conectar con el broker")
                return False
            capital = self.broker.get_available_capital()
            logger.info(f"💰 Capital disponible: ${capital:.2f}")

        # Mostrar info del mercado
        log_scheduler_info()

        logger.info("\n✅ Inicialización completada")
        return True

    def start_scheduler(self):
        """Inicia el scheduler"""
        logger.info("\n" + "="*70)
        logger.info("⏰ INICIANDO SCHEDULER")
        logger.info("="*70)

        self.scheduler.start(
            search_callback=scheduled_search,
            confirm_callback=scheduled_confirm,
            execute_callback=scheduled_execute,
            review_callback=scheduled_review,
        )

        self.running = True
        logger.info("\n✅ Scheduler iniciado. Próximos jobs:")
        for job in self.scheduler.get_next_jobs():
            logger.info(f"  • {job['name']}: {job['next_run']}")

    def stop_scheduler(self):
        """Detiene el scheduler"""
        logger.info("\n🛑 Deteniendo scheduler...")
        self.scheduler.stop()
        self.running = False
        logger.info("✅ Scheduler detenido")

    def get_status(self) -> dict:
        """Retorna estado actual del sistema"""
        portfolio = self.broker.get_portfolio_value()
        scheduler_status = self.scheduler.get_scheduler_status()

        return {
            "timestamp": datetime.now(timezone(MARKET_TIMEZONE)).isoformat(),
            "simulation_mode": SIMULATION_MODE,
            "scheduler_running": self.running,
            "portfolio": portfolio,
            "scheduler": scheduler_status,
        }

    def print_status(self):
        """Imprime el estado en consola"""
        status = self.get_status()
        tz = timezone(MARKET_TIMEZONE)
        now = datetime.now(tz)

        print("\n" + "="*70)
        print("📊 ESTADO DEL SISTEMA")
        print("="*70)
        print(f"⏰ Hora actual (ET): {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔄 Scheduler: {'✅ Corriendo' if self.running else '⏸️ Detenido'}")
        print(f"🎭 Modo: {'Simulación' if SIMULATION_MODE else 'Real Money'}")

        portfolio = status["portfolio"]
        print(f"\n💼 PORTFOLIO:")
        print(f"   Total: ${portfolio['total_value']:.2f}")
        print(f"   Cash: ${portfolio['available_capital']:.2f}")
        print(f"   Posiciones: ${portfolio['positions_value']:.2f}")
        print(f"   P&L: ${portfolio['total_pnl']:.2f}")
        print(f"   Activos: {portfolio['num_positions']}")

        print(f"\n📅 PRÓXIMOS JOBS:")
        for job in status["scheduler"]["next_jobs"]:
            print(f"   • {job['name']}")
            print(f"     {job['next_run']}")

        print("="*70 + "\n")

    def run_interactive(self):
        """Modo interactivo en consola"""
        print("\n" + "="*70)
        print("🎮 MODO INTERACTIVO")
        print("="*70)
        print("\nComandos disponibles:")
        print("  start    - Inicia el scheduler")
        print("  stop     - Detiene el scheduler")
        print("  status   - Muestra estado actual")
        print("  search   - Ejecuta búsqueda manual")
        print("  confirm  - Ejecuta confirmación manual")
        print("  execute  - Ejecuta compra manual")
        print("  review   - Ejecuta revisión manual")
        print("  backtest - Simula operaciones del año pasado")
        print("  exit     - Salir")
        print("="*70)

        while True:
            try:
                cmd = input("\n> ").strip().lower()

                if cmd == "start":
                    if not self.running:
                        self.start_scheduler()
                    else:
                        print("⚠️ Scheduler ya está corriendo")

                elif cmd == "stop":
                    if self.running:
                        self.stop_scheduler()
                    else:
                        print("⚠️ Scheduler no está corriendo")

                elif cmd == "status":
                    self.print_status()

                elif cmd == "search":
                    print("\n🔍 Ejecutando búsqueda manual...")
                    scheduled_search()

                elif cmd == "confirm":
                    print("\n✓ Ejecutando confirmación manual...")
                    scheduled_confirm()

                elif cmd == "execute":
                    print("\n💳 Ejecutando ejecución manual...")
                    scheduled_execute()

                elif cmd == "review":
                    print("\n📋 Ejecutando revisión manual...")
                    scheduled_review()

                elif cmd == "backtest":
                    print("\n📈 Iniciando backtest del año pasado...")
                    self.run_backtest()

                elif cmd == "exit":
                    print("\n👋 Saliendo...")
                    if self.running:
                        self.stop_scheduler()
                    if not SIMULATION_MODE:
                        self.broker.disconnect()
                    break

                else:
                    print("❌ Comando no reconocido")

            except KeyboardInterrupt:
                print("\n\n👋 Saliendo...")
                if self.running:
                    self.stop_scheduler()
                if not SIMULATION_MODE:
                    self.broker.disconnect()
                break
            except Exception as e:
                print(f"❌ Error: {e}")

    def run_backtest(self):
        """Ejecuta backtest. Permite elegir año/rango de años y tickers."""
        from backtest import BacktestSimulator

        current_year = datetime.now().year

        # ── Periodo ──
        print(f"\n📅 Selecciona el periodo del backtest:")
        print(f"   - Un año concreto, entre 2015 y {current_year} (ej: 2022)")
        print(f"   - Un rango de años (ej: 2022-2024)")
        print(f"   - ENTER para usar los últimos 365 días")
        choice = input("   Periodo: ").strip()

        start_date = None
        end_date = None

        if choice:
            if "-" in choice:
                parts = choice.split("-")
                if (
                    len(parts) == 2
                    and parts[0].strip().isdigit()
                    and parts[1].strip().isdigit()
                ):
                    y1, y2 = int(parts[0].strip()), int(parts[1].strip())
                    if y1 > y2:
                        y1, y2 = y2, y1
                    if 2015 <= y1 <= current_year and 2015 <= y2 <= current_year:
                        start_date = date(y1, 1, 1)
                        end_date = date(y2, 12, 31)
                        logger.info(f"📅 Periodo seleccionado: {y1}-{y2}")
                    else:
                        print(f"   ⚠️ Rango fuera de 2015-{current_year}, usando últimos 365 días")
                else:
                    print(f"   ⚠️ Formato no válido (usa AAAA-AAAA), usando últimos 365 días")
            elif choice.isdigit() and 2015 <= int(choice) <= current_year:
                year = int(choice)
                start_date = date(year, 1, 1)
                end_date = date(year, 12, 31)
                logger.info(f"📅 Periodo seleccionado: año {year}")
            else:
                print(f"   ⚠️ Valor no válido, usando últimos 365 días")

        # ── Tickers ──
        print(f"\n📊 Tickers a analizar (separados por comas, ej: AAPL,MSFT,NVDA)")
        print(f"   ENTER para usar los tickers por defecto (sectores configurados)")
        tickers_input = input("   Tickers: ").strip()

        tickers = None
        if tickers_input:
            tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
            if tickers:
                logger.info(f"📊 Tickers seleccionados: {', '.join(tickers)}")
            else:
                tickers = None

        logger.info("\n" + "="*70)
        logger.info("INICIANDO BACKTEST")
        logger.info("="*70)

        try:
            simulator = BacktestSimulator(
                initial_capital=5000.0,
                lookback_days=365,
                start_date=start_date,
                end_date=end_date,
                tickers=tickers,
            )

            metrics = simulator.run_backtest()
            simulator.print_report(metrics)

        except Exception as e:
            logger.error(f"Error en backtest: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Función principal"""
    import argparse

    parser = argparse.ArgumentParser(description="Investment Swarm - AI Trading System")
    parser.add_argument(
        "--mode",
        choices=["interactive", "dashboard", "daemon"],
        default="interactive",
        help="Modo de ejecución",
    )
    parser.add_argument(
        "--auto-start",
        action="store_true",
        help="Inicia scheduler automáticamente",
    )

    args = parser.parse_args()

    # Inicializar app
    app = InvestmentSwarmApp()
    if not app.initialize():
        sys.exit(1)

    # Elegir modo de ejecución
    if args.mode == "interactive":
        if args.auto_start:
            app.start_scheduler()
        app.run_interactive()

    elif args.mode == "dashboard":
        # Lanzar Streamlit dashboard
        if args.auto_start:
            app.start_scheduler()
        os.system("streamlit run dashboard.py")

    elif args.mode == "daemon":
        # Modo daemon - solo scheduler sin UI
        logger.info("🖥️ Modo DAEMON - Scheduler ejecutándose en background")
        app.start_scheduler()
        try:
            # Mantener el programa corriendo
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\n👋 Deteniendo...")
            app.stop_scheduler()
            if not SIMULATION_MODE:
                app.broker.disconnect()


if __name__ == "__main__":
    main()