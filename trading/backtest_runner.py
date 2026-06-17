"""
BACKTEST RUNNER - Simplified version for Streamlit
Runs backtests without heavy logging for dashboard integration
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import yfinance as yf
import logging
import os
import pickle
import shutil
from pathlib import Path

# Disable yfinance logging
logging.getLogger('yfinance').setLevel(logging.ERROR)

from trading.backtest import BacktestSimulator

# Cache directory
CACHE_DIR = Path(__file__).parent.parent / "data" / "price_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

class BacktestRunner:
    """Simplificado runner para ejecutar backtests desde Streamlit"""

    @staticmethod
    def _get_cache_path(ticker: str) -> Path:
        """Obtiene la ruta del archivo de caché para un ticker"""
        return CACHE_DIR / f"{ticker.upper()}_cache.pkl"

    @staticmethod
    def _load_cached_data(ticker: str) -> Optional[pd.DataFrame]:
        """Carga datos del caché si existen"""
        cache_path = BacktestRunner._get_cache_path(ticker)
        if cache_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"⚠️ Error cargando caché de {ticker}: {e}")
        return None

    @staticmethod
    def _save_cached_data(ticker: str, df: pd.DataFrame) -> None:
        """Guarda datos en caché"""
        try:
            cache_path = BacktestRunner._get_cache_path(ticker)
            with open(cache_path, 'wb') as f:
                pickle.dump(df, f)
        except Exception as e:
            print(f"⚠️ Error guardando caché de {ticker}: {e}")

    @staticmethod
    def clear_all_cache() -> Tuple[bool, str]:
        """Elimina todo el caché de datos históricos"""
        try:
            if CACHE_DIR.exists():
                shutil.rmtree(CACHE_DIR)
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                return True, f"✅ Caché eliminado: {CACHE_DIR}"
            else:
                return True, "ℹ️ No hay caché para eliminar"
        except Exception as e:
            return False, f"❌ Error al eliminar caché: {e}"

    @staticmethod
    def get_cache_size() -> str:
        """Obtiene el tamaño total del caché"""
        try:
            if not CACHE_DIR.exists():
                return "0 B"

            total_size = sum(f.stat().st_size for f in CACHE_DIR.rglob('*') if f.is_file())

            # Convertir a unidades legibles
            for unit in ['B', 'KB', 'MB', 'GB']:
                if total_size < 1024:
                    return f"{total_size:.1f} {unit}"
                total_size /= 1024

            return f"{total_size:.1f} TB"
        except:
            return "? B"

    @staticmethod
    def get_cached_tickers() -> List[str]:
        """Obtiene lista de tickers en caché"""
        try:
            if not CACHE_DIR.exists():
                return []

            cached = []
            for file in CACHE_DIR.glob('*_cache.pkl'):
                ticker = file.stem.replace('_cache', '')
                cached.append(ticker)
            return sorted(cached)
        except:
            return []

    PREDEFINED_RANGES = {
        "Last 30 days": (-30, 0),
        "Last 3 months": (-90, 0),
        "Last 6 months": (-180, 0),
        "Last 1 year": (-365, 0),
        "Last 2 years": (-730, 0),
        "2025": (datetime(2025, 1, 1), datetime(2025, 12, 31)),
        "2024": (datetime(2024, 1, 1), datetime(2024, 12, 31)),
        "2023": (datetime(2023, 1, 1), datetime(2023, 12, 31)),
        "2022": (datetime(2022, 1, 1), datetime(2022, 12, 31)),
        "2021": (datetime(2021, 1, 1), datetime(2021, 12, 31)),
        "2020": (datetime(2020, 1, 1), datetime(2020, 12, 31)),
        "2019": (datetime(2019, 1, 1), datetime(2019, 12, 31)),
        "2018": (datetime(2018, 1, 1), datetime(2018, 12, 31)),
    }

    @staticmethod
    def parse_date_range(range_key: str, custom_start=None, custom_end=None) -> Tuple[datetime, datetime]:
        """Parsea rango de fechas"""
        today = datetime.now().date()

        if range_key == "Custom" and custom_start and custom_end:
            start = custom_start if isinstance(custom_start, datetime) else datetime.combine(custom_start, datetime.min.time())
            end = custom_end if isinstance(custom_end, datetime) else datetime.combine(custom_end, datetime.min.time())
            return start.date(), end.date()

        if range_key in BacktestRunner.PREDEFINED_RANGES:
            r = BacktestRunner.PREDEFINED_RANGES[range_key]

            if isinstance(r[0], int):
                start = today + timedelta(days=r[0])
                end = today + timedelta(days=r[1])
            else:
                start = r[0].date() if isinstance(r[0], datetime) else r[0]
                end = r[1].date() if isinstance(r[1], datetime) else r[1]

            return start, end

        return today - timedelta(days=365), today

    @staticmethod
    def run_backtest(
        date_range: str,
        initial_capital: float = 5000.0,
        transaction_cost_pct: float = 0.001,
        custom_start=None,
        custom_end=None,
        tickers: Optional[List[str]] = None,
        progress_callback=None
    ) -> Dict:
        """Ejecuta un backtest para el rango de fechas especificado"""
        try:
            start_date, end_date = BacktestRunner.parse_date_range(
                date_range, custom_start, custom_end
            )

            if progress_callback:
                progress_callback(f"Inicializando backtest: {start_date} → {end_date}")

            simulator = BacktestSimulator(
                initial_capital=initial_capital,
                start_date=start_date,
                end_date=end_date,
                transaction_cost_pct=transaction_cost_pct,
                tickers=tickers,
            )

            if progress_callback:
                progress_callback("Descargando datos históricos...")

            metrics = simulator.run_backtest()

            metrics['trades'] = simulator.trades
            metrics['daily_values'] = simulator.daily_portfolio_values
            metrics['positions'] = simulator.positions

            return {
                'success': True,
                'metrics': metrics,
                'simulator': simulator
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'metrics': None,
                'simulator': None
            }

    @staticmethod
    def format_metrics_for_display(metrics: Dict) -> Dict:
        """Formatea métricas para mostrar en Streamlit"""

        if not metrics:
            return {}

        return {
            "Período": {
                "Inicio": metrics['backtest_period']['start'],
                "Fin": metrics['backtest_period']['end'],
                "Días": metrics['backtest_period']['trading_days'],
            },
            "Performance": {
                "Capital Inicial": f"${metrics['performance']['initial_capital']:,.2f}",
                "Capital Final": f"${metrics['performance']['final_value']:,.2f}",
                "Return %": f"{metrics['performance']['total_return_pct']:+.2f}%",
                "Max Drawdown": f"{metrics['performance']['max_drawdown_pct']:.2f}%",
                "Sharpe Ratio": f"{metrics['performance']['sharpe_ratio']:.2f}",
            },
            "Trading": {
                "Total Compras": metrics['trading']['total_buys'],
                "Total Ventas": metrics['trading']['total_sells'],
                "Posiciones Abiertas": metrics['trading']['open_positions'],
                "Win Rate": f"{metrics['trading']['win_rate_pct']:.2f}%",
                "Stop Loss": metrics['trading']['stop_loss_count'],
            },
            "Costos": {
                "% Transacción": f"{metrics['costs']['transaction_cost_pct']:.2f}%",
                "Total Pagado": f"${metrics['costs']['total_transaction_costs']:,.2f}",
                "% del Capital": f"{metrics['costs']['cost_as_pct_of_initial']:.2f}%",
            },
            "Comparación": {
                "Bot Return": f"{metrics['comparison']['bot_return_pct']:+.2f}%",
                "Buy & Hold": f"{metrics['comparison']['buyhold_return_pct']:+.2f}%",
                "Perfect Timing": f"{metrics['comparison']['perfect_timing_return_pct']:+.2f}%",
                "SPY Return": f"{metrics['comparison']['spy_return_pct']:+.2f}%",
                "Bot vs Buy&Hold": f"{metrics['comparison']['bot_vs_buyhold_diff']:+.2f}%",
                "Bot vs Perfect Timing": f"{metrics['comparison']['bot_vs_perfect_diff']:+.2f}%",
                "Bot vs SPY": f"{metrics['comparison']['bot_vs_spy_diff']:+.2f}%",
            }
        }

    @staticmethod
    def get_trades_dataframe(trades: List[Dict]) -> pd.DataFrame:
        """Convierte lista de trades a DataFrame para mostrar"""
        if not trades:
            return pd.DataFrame()

        df_data = []
        for trade in trades:
            df_data.append({
                "Fecha": trade.get('date', 'N/A'),
                "Ticker": trade.get('ticker', 'N/A'),
                "Acción": trade.get('action', 'N/A'),
                "Cantidad": trade.get('quantity', 0),
                "Precio": f"${trade.get('price', 0):.2f}",
                "Total": f"${trade.get('quantity', 0) * trade.get('price', 0):,.2f}",
                "Razón": trade.get('reason', '-'),
                "P&L": f"${trade.get('pnl', 0):,.2f}" if trade.get('action') == 'SELL' else '-',
            })

        return pd.DataFrame(df_data)

    @staticmethod
    def get_daily_performance_dataframe(daily_values: List[Dict]) -> pd.DataFrame:
        """Convierte valores diarios a DataFrame para gráfico"""
        if not daily_values:
            return pd.DataFrame()

        df_data = []
        for daily in daily_values:
            df_data.append({
                "Date": daily.get('date', 'N/A'),
                "Portfolio Value": daily.get('total_value', 0),
                "Cash": daily.get('cash', 0),
                "Return %": daily.get('return_pct', 0),
            })

        return pd.DataFrame(df_data)
