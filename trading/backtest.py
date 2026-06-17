"""
BACKTEST MODULE (v2 - rediseñado)
==================================

Base del +185% + COSTES DE TRANSACCIÓN.

Cada compra y cada venta paga una comisión (por defecto 0.1% del importe).
Esto modela las comisiones del broker + spread + slippage aproximado.
Hace el resultado del backtest más realista y comparable con lo que
obtendría el bot operando con dinero real.
"""

import logging
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf

from crewai import Crew, Task, Process
from agents.fundamental_agent import create_fundamental_agent
from core.investment_decision_engine import InvestmentDecisionEngine
from config import AVAILABLE_SECTORS, SELECTED_SECTORS

import pickle
from pathlib import Path
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Backtest")


# Cache directory para datos históricos
CACHE_DIR = Path(__file__).parent.parent / "data" / "price_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Cache persistente de fundamentales (evita re-llamar al LLM entre runs del mismo test)
FUNDAMENTAL_CACHE_FILE = Path(__file__).parent.parent / "data" / "fundamental_cache.json"


def _load_fundamental_cache() -> dict:
    if FUNDAMENTAL_CACHE_FILE.exists():
        try:
            with open(FUNDAMENTAL_CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_fundamental_cache(cache: dict) -> None:
    try:
        FUNDAMENTAL_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(FUNDAMENTAL_CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        logger.warning(f"No se pudo guardar caché de fundamentales: {e}")


def _get_cache_path(ticker: str) -> Path:
    """Obtiene la ruta del archivo de caché para un ticker"""
    return CACHE_DIR / f"{ticker.upper()}_cache.pkl"


def _load_cached_data(ticker: str):
    """Carga datos del caché si existen"""
    cache_path = _get_cache_path(ticker)
    if cache_path.exists():
        try:
            with open(cache_path, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            logger.warning(f"Error cargando caché de {ticker}: {e}")
    return None


def _save_cached_data(ticker: str, df) -> None:
    """Guarda datos en caché"""
    try:
        cache_path = _get_cache_path(ticker)
        with open(cache_path, 'wb') as f:
            pickle.dump(df, f)
    except Exception as e:
        logger.warning(f"Error guardando caché de {ticker}: {e}")


def extract_json(text: str) -> Optional[dict]:
    def _try_parse(candidate_text: str) -> Optional[dict]:
        decoder = json.JSONDecoder()
        idx = 0
        first_dict = None
        while idx < len(candidate_text):
            idx = candidate_text.find("{", idx)
            if idx == -1:
                break
            try:
                obj, _ = decoder.raw_decode(candidate_text, idx)
                if isinstance(obj, dict):
                    if "score" in obj:
                        return obj
                    if first_dict is None:
                        first_dict = obj
            except json.JSONDecodeError:
                pass
            idx += 1
        return first_dict

    result = _try_parse(text)
    if result is not None:
        return result
    cleaned = re.sub(r",(\s*[}\]])", r"\1", text)
    return _try_parse(cleaned)


NEUTRAL_SENTIMENT = {
    "sentimiento": "NEUTRO",
    "confianza": 50,
    "catalizadores_positivos": [],
    "catalizadores_negativos": [],
    "red_flags": [],
    "noticias_clave": [],
    "resumen": "Sentimiento neutral fijo (no disponible históricamente en backtest)",
}

CONVICTION_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "VERY_HIGH": 3}

HEDGE_TICKER = "PSQ"
HEDGE_REGIMES = ("BEARISH", "BEAR_RALLY")
HEDGE_ALLOCATION_PCT = 0.40  # 40 % en bajistas — hedge más agresivo
HEDGE_EXIT_PARAMS = {
    "stop_loss_pct": -12,   # Era -8: más espacio para respirar (crash rápido)
    "take_profit_pct": 30,
    "trailing_trigger_pct": 15,
    "trailing_stop_pct": 10,
}

# Períodos mínimos de espera entre compras del mismo ticker (días naturales)
BUY_FREQUENCY_LIMIT_DAYS = 15      # Mín. días entre compras del mismo ticker
BUY_FREQUENCY_DEEP_DIP_RSI = 45    # RSI por debajo de este umbral: compra adicional permitida antes del límite

# Cooldowns tras stop loss (días naturales, dependientes del régimen)
STOP_LOSS_COOLDOWN = {
    "BULLISH":    14,   # Corrección temporal → re-entrada más rápida
    "NEUTRAL":    25,
    "BEAR_RALLY": 45,
    "BEARISH":    60,   # Mercado bajista → no re-entrar en semanas
}

REGIME_PROFILES = {
    "BULLISH": {
        "description": "Tendencia alcista (precio y SMA50 > SMA200 del benchmark)",
        "min_fundamental_score": 5,
        "min_conviction": None,
        "min_combined_score": None,
        "conviction_pct": {"VERY_HIGH": 0.75, "HIGH": 0.38, "MEDIUM": 0.15, "LOW": 0.05},
        # Stop loss amplio (-22%): correcciones normales de 15-20% en bull market
        # no deben cerrar posiciones de swing/position trading.
        # Take profit muy alto (200%) → prácticamente nunca activa; el trailing hace el trabajo.
        "exit_high": {"stop_loss_pct": -22, "take_profit_pct": 200, "trailing_trigger_pct": 35, "trailing_stop_pct": 25},
        "exit_low":  {"stop_loss_pct": -15, "take_profit_pct":  60, "trailing_trigger_pct": 22, "trailing_stop_pct": 18},
    },
    "NEUTRAL": {
        "description": "Sin tendencia clara (lateral)",
        "min_fundamental_score": 6,
        "min_conviction": "HIGH",       # Era None: exigimos más en incertidumbre
        "min_combined_score": None,
        "conviction_pct": {"VERY_HIGH": 0.40, "HIGH": 0.20, "MEDIUM": 0.0, "LOW": 0.0},
        "exit_high": {"stop_loss_pct": -13, "take_profit_pct": 28, "trailing_trigger_pct": 14, "trailing_stop_pct": 10},
        "exit_low":  {"stop_loss_pct": -10, "take_profit_pct": 18, "trailing_trigger_pct":  9, "trailing_stop_pct":  7},
    },
    "BEARISH": {
        "description": "Tendencia bajista (precio y SMA50 < SMA200 del benchmark)",
        "min_fundamental_score": 9,
        "min_conviction": "VERY_HIGH",
        "min_combined_score": 0.80,
        "conviction_pct": {"VERY_HIGH": 0.10, "HIGH": 0.0, "MEDIUM": 0.0, "LOW": 0.0},
        "exit_high": {"stop_loss_pct": -6, "take_profit_pct": 14, "trailing_trigger_pct": 7, "trailing_stop_pct": 5},
        "exit_low":  {"stop_loss_pct": -5, "take_profit_pct":  9, "trailing_trigger_pct": 5, "trailing_stop_pct": 4},
    },
    "BEAR_RALLY": {
        "description": "Rebote dentro de tendencia bajista mayor",
        "min_fundamental_score": 9,
        "min_conviction": "VERY_HIGH",
        "min_combined_score": 0.78,
        "conviction_pct": {"VERY_HIGH": 0.08, "HIGH": 0.0, "MEDIUM": 0.0, "LOW": 0.0},
        "exit_high": {"stop_loss_pct": -5, "take_profit_pct": 11, "trailing_trigger_pct": 6, "trailing_stop_pct": 4},
        "exit_low":  {"stop_loss_pct": -4, "take_profit_pct":  7, "trailing_trigger_pct": 4, "trailing_stop_pct": 3},
    },
}


class TechnicalIndicators:
    @staticmethod
    def calculate(df: pd.DataFrame) -> Dict:
        if df is None or len(df) < 50:
            return {"señal": "LATERAL", "confianza": 0, "error": "Datos insuficientes"}

        close = df["Close"]
        volume = df["Volume"]

        sma20 = close.rolling(20).mean()
        sma50 = close.rolling(50).mean()
        sma200 = close.rolling(200).mean() if len(df) >= 200 else None

        current_price = float(close.iloc[-1])
        sma20_val = float(sma20.iloc[-1])
        sma50_val = float(sma50.iloc[-1])
        sma200_val = (
            float(sma200.iloc[-1])
            if sma200 is not None and not pd.isna(sma200.iloc[-1])
            else None
        )

        # Momentum 20 días (rate of change)
        mom_period = min(20, len(close) - 1)
        momentum_20 = ((current_price - float(close.iloc[-mom_period - 1])) / float(close.iloc[-mom_period - 1]) * 100) if mom_period > 0 else 0.0

        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        rsi_val = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0

        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_val = float(macd_line.iloc[-1])
        signal_val = float(signal_line.iloc[-1])
        macd_above = macd_val > signal_val
        macd_strong = macd_above and macd_val > 0  # Por encima de cero = momentum real

        bb_mid = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        bb_lower = float((bb_mid - 2 * bb_std).iloc[-1])
        bb_upper = float((bb_mid + 2 * bb_std).iloc[-1])

        vol_avg20 = volume.rolling(20).mean()
        vol_ratio = (
            float(volume.iloc[-1] / vol_avg20.iloc[-1])
            if vol_avg20.iloc[-1] and vol_avg20.iloc[-1] > 0
            else 1.0
        )
        volume_confirms = vol_ratio > 1.15

        support = float(close.tail(20).min())
        resistance = float(close.tail(20).max())

        # SMA alineadas (tendencia corto plazo)
        sma_aligned_bull = current_price > sma20_val > sma50_val
        sma_aligned_bear = current_price < sma20_val < sma50_val

        # SMA200: estructura macro
        above_sma200 = sma200_val is not None and current_price > sma200_val
        below_sma200 = sma200_val is not None and current_price < sma200_val
        golden_cross = sma200_val is not None and sma50_val > sma200_val  # Bull estructural
        death_cross  = sma200_val is not None and sma50_val < sma200_val  # Bear estructural

        # RSI categorías mejoradas
        rsi_oversold      = rsi_val < 38            # Sobreventa: posible rebote
        rsi_healthy_bull  = 45 <= rsi_val <= 72     # NUEVO: momentum alcista sano
        rsi_overbought    = rsi_val > 76            # Sobrecompra: precaución

        confirmations = {
            "trend": False, "rsi": False, "macd": False,
            "volumen": volume_confirms, "sma200": False, "momentum": False,
        }
        bullish_points = 0
        bearish_points = 0

        # 1. Alineación SMA corto plazo (1 punto)
        if sma_aligned_bull:
            bullish_points += 1
            confirmations["trend"] = True
        elif sma_aligned_bear:
            bearish_points += 1

        # 2. SMA200 / Golden-Death Cross (0-2 puntos) — señal estructural más importante
        if sma200_val is not None:
            if above_sma200 and golden_cross:
                bullish_points += 2          # Máxima convicción alcista
                confirmations["sma200"] = True
            elif above_sma200:
                bullish_points += 1
                confirmations["sma200"] = True
            elif below_sma200 and death_cross:
                bearish_points += 2          # Máxima convicción bajista
            elif below_sma200:
                bearish_points += 1

        # 3. RSI (1 punto) — ahora reconoce momentum sano, no solo sobreventa
        if rsi_oversold or rsi_healthy_bull:
            bullish_points += 1
            confirmations["rsi"] = True
        elif rsi_overbought:
            bearish_points += 1

        # 4. MACD (1-2 puntos)
        if macd_strong:          # Línea encima de señal Y encima de cero
            bullish_points += 2
            confirmations["macd"] = True
        elif macd_above:         # Solo encima de señal (recuperando)
            bullish_points += 1
            confirmations["macd"] = True
        else:
            bearish_points += 1

        # 5. Momentum 20d (1 punto)
        if momentum_20 > 5:
            bullish_points += 1
            confirmations["momentum"] = True
        elif momentum_20 < -5:
            bearish_points += 1

        # 6. Volumen confirma (1 punto bonus)
        if volume_confirms:
            if bullish_points > bearish_points:
                bullish_points += 1
            elif bearish_points > bullish_points:
                bearish_points += 1

        # Señal final (máx ~8 bull / ~7 bear)
        # ALCISTA fuerte: ≥5 puntos; ALCISTA: ≥3; BAJISTA fuerte: ≥5; BAJISTA: ≥3
        if bullish_points >= 5:
            señal = "ALCISTA"
            confianza = min(95, 45 + bullish_points * 7)
        elif bearish_points >= 5:
            señal = "BAJISTA"
            confianza = min(95, 45 + bearish_points * 7)
        elif bullish_points >= 3:
            señal = "ALCISTA"
            confianza = min(72, 38 + bullish_points * 8)
        elif bearish_points >= 3:
            señal = "BAJISTA"
            confianza = min(72, 38 + bearish_points * 8)
        else:
            señal = "LATERAL"
            confianza = 35

        # Restricción estructural: no ALCISTA si precio está bajo SMA200
        if señal == "ALCISTA" and below_sma200:
            señal = "LATERAL"
            confianza = 35

        # "Buy the dip" en uptrend estructural:
        # Si el mercado está en tendencia larga (golden cross + por encima de SMA200)
        # y el precio ha retrocedido (RSI < 44), es oportunidad de compra aunque
        # las señales corto plazo no estén perfectas. Salvaguarda: solo aplica si el
        # precio está a máximo 8% por debajo del SMA50 (no es crash, solo corrección).
        bull_dip = (
            golden_cross
            and above_sma200
            and sma200_val is not None and current_price > sma200_val * 0.93
            and sma50_val > 0 and current_price > sma50_val * 0.92
            and 22 < rsi_val < 44
        )
        if bull_dip and señal in ("LATERAL", "BAJISTA"):
            señal = "ALCISTA"
            confianza = max(confianza, 58)

        entry = current_price
        if señal == "ALCISTA":
            stop_loss = round(min(support, sma50_val) * 0.98, 2)
            target = round(resistance * 1.06, 2)
        elif señal == "BAJISTA":
            stop_loss = round(max(resistance, sma50_val) * 1.02, 2)
            target = round(support * 0.95, 2)
        else:
            stop_loss = round(current_price * 0.95, 2)
            target = round(current_price * 1.05, 2)

        risk = abs(entry - stop_loss)
        reward = abs(target - entry)
        rr_ratio = round(reward / risk, 2) if risk > 0 else 1.0

        return {
            "señal": señal,
            "confianza": confianza,
            "rsi": round(rsi_val, 2),
            "rsi_interpretacion": (
                "oversold" if rsi_oversold
                else "healthy_bull" if rsi_healthy_bull
                else "overbought" if rsi_overbought
                else "neutral"
            ),
            "tendencia": "ALCISTA" if sma_aligned_bull else "BAJISTA" if sma_aligned_bear else "LATERAL",
            "golden_cross": golden_cross,
            "death_cross": death_cross,
            "above_sma200": above_sma200,
            "momentum_20d": round(momentum_20, 2),
            "entrada_sugerida": round(entry, 2),
            "stop_loss": stop_loss,
            "target_price": target,
            "reward_risk_ratio": rr_ratio,
            "confirmaciones": confirmations,
            "bullish_points": bullish_points,
            "bearish_points": bearish_points,
            "resumen": (
                f"SMA20={sma20_val:.2f} SMA50={sma50_val:.2f} "
                f"RSI={rsi_val:.1f} Mom20={momentum_20:+.1f}% "
                f"GC={golden_cross} DC={death_cross}"
            ),
        }


class BacktestSimulator:
    def __init__(
        self,
        initial_capital: float = 5000.0,
        lookback_days: int = 365,
        tickers: Optional[List[str]] = None,
        start_date=None,
        end_date=None,
        transaction_cost_pct: float = 0.001,
    ):
        """
        Args:
            ...
            transaction_cost_pct: Coste por operación (compra Y venta) como
                fracción del importe. Por defecto 0.001 = 0.1%. Modela
                comisiones del broker + spread bid/ask + slippage estimado.
                Valor típico para brokers retail modernos en acciones US.
                Poner a 0.0 para desactivar y comparar con el resultado puro.
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.lookback_days = lookback_days
        self.transaction_cost_pct = transaction_cost_pct

        if start_date and end_date:
            self.start_date = start_date
            self.end_date = min(end_date, datetime.now().date())
        else:
            self.end_date = datetime.now().date()
            self.start_date = self.end_date - timedelta(days=lookback_days)

        self.data_start_date = self.start_date - timedelta(days=400)
        self.tickers = tickers or self._default_tickers()

        self.trades: List[Dict] = []
        self.positions: Dict[str, List[Dict]] = {}
        self.daily_portfolio_values: List[Dict] = []

        self.stop_loss_cooldown: Dict[str, object] = {}  # ticker → fecha mín. re-entrada tras stop loss
        self.last_buy_date: Dict[str, object] = {}       # ticker → última fecha de compra (anti-pirámide)

        self.peak_portfolio_value = initial_capital
        self.trading_paused = False
        # 30 %: con la salida por cambio de régimen, el CB solo actúa en crashes extremos.
        # Pausa máxima de 5 días: evita que el bot se quede fuera durante la recuperación.
        self.pause_drawdown_threshold = 30.0
        self.resume_drawdown_threshold = 18.0
        self.paused_days_count = 0
        self.max_pause_days = 5
        self.days_paused_streak = 0

        self.historical_data: Dict[str, pd.DataFrame] = {}
        self.fundamental_cache: Dict[str, Dict] = {}

        self.regime_benchmark = "SPY"  # S&P500 como benchmark de régimen (más representativo que XLK)
        self.benchmark_data: Optional[pd.DataFrame] = None
        self.regimes: Dict = {}

        # Acumulador de costes de transacción pagados durante el backtest
        self.total_transaction_costs = 0.0

        self.decision_engine = InvestmentDecisionEngine()

        logger.info(f"Backtest: {self.start_date} → {self.end_date}")
        logger.info(f"Capital inicial: ${self.initial_capital:,.2f}")
        logger.info(f"Coste por operación: {self.transaction_cost_pct*100:.2f}%")
        logger.info(f"Tickers: {', '.join(self.tickers)}")

    def _default_tickers(self) -> List[str]:
        tickers = []
        for sector in SELECTED_SECTORS:
            if sector in AVAILABLE_SECTORS:
                tickers.extend(AVAILABLE_SECTORS[sector])
        seen = set()
        unique = []
        for t in tickers:
            if t not in seen:
                seen.add(t)
                unique.append(t)
        return unique

    def preload_data(self) -> None:
        logger.info(f"\n{'='*70}")
        logger.info("DESCARGANDO DATOS HISTÓRICOS")
        logger.info(f"{'='*70}")

        # Normalizar fechas a datetime.date (por si se pasan datetime.datetime)
        need_start = self.data_start_date.date() if hasattr(self.data_start_date, 'date') and callable(self.data_start_date.date) else self.data_start_date
        need_end   = self.end_date.date()        if hasattr(self.end_date,         'date') and callable(self.end_date.date)         else self.end_date

        for ticker in self.tickers:
            # — Intentar caché —
            cache_ok = False
            try:
                cached_df = _load_cached_data(ticker)
                if cached_df is not None and len(cached_df) > 0:
                    mask = (cached_df.index.date >= need_start) & (cached_df.index.date <= need_end)
                    masked = cached_df[mask]
                    earliest_cached = cached_df.index.min().date()
                    # Caché válido: cubre todo el período y tiene suficientes días para SMA200
                    if len(masked) >= 250 and earliest_cached <= need_start + timedelta(days=30):
                        self.historical_data[ticker] = masked
                        logger.info(f"  ✓ {ticker}: {len(masked)} días (desde caché)")
                        cache_ok = True
                    else:
                        logger.info(f"  ↻ {ticker}: caché insuficiente ({len(masked)} días / desde {earliest_cached}), descargando...")
            except Exception as e:
                logger.warning(f"  ⚠️ {ticker}: error leyendo caché: {e}")

            if cache_ok:
                continue

            # — Descargar de Yahoo Finance —
            try:
                df = yf.download(
                    ticker,
                    start=self.data_start_date,
                    end=self.end_date + timedelta(days=1),
                    progress=False,
                )
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                if len(df) > 0:
                    self.historical_data[ticker] = df
                    _save_cached_data(ticker, df)
                    logger.info(f"  ✓ {ticker}: {len(df)} días (guardados en caché)")
                else:
                    logger.warning(f"  ⚠️ {ticker}: sin datos")
            except Exception as e:
                logger.warning(f"  ❌ {ticker}: {e}")

        try:
            df = yf.download(
                self.regime_benchmark,
                start=self.data_start_date,
                end=self.end_date + timedelta(days=1),
                progress=False,
            )
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if len(df) > 0:
                self.benchmark_data = df
                logger.info(f"  ✓ {self.regime_benchmark} (benchmark régimen): {len(df)} días")
        except Exception as e:
            logger.warning(f"  ❌ Benchmark: {e}")

        try:
            df = yf.download(
                HEDGE_TICKER,
                start=self.data_start_date,
                end=self.end_date + timedelta(days=1),
                progress=False,
            )
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if len(df) > 0:
                self.historical_data[HEDGE_TICKER] = df
                logger.info(f"  ✓ {HEDGE_TICKER} (hedge inverso): {len(df)} días")
        except Exception as e:
            logger.warning(f"  ❌ Hedge: {e}")

    def precompute_regimes(self) -> None:
        if self.benchmark_data is None or len(self.benchmark_data) < 220:
            logger.warning(f"⚠️ Datos insuficientes. NEUTRAL todo el periodo.")
            return

        close = self.benchmark_data["Close"]
        sma50 = close.rolling(50).mean()
        sma200 = close.rolling(200).mean()
        sma200_slope = sma200 - sma200.shift(20)

        for i in range(len(self.benchmark_data)):
            d = self.benchmark_data.index[i].date()
            if not (self.start_date <= d <= self.end_date):
                continue

            price = close.iloc[i]
            s50 = sma50.iloc[i]
            s200 = sma200.iloc[i]
            slope = sma200_slope.iloc[i]

            if pd.isna(s50) or pd.isna(s200) or pd.isna(slope):
                self.regimes[d] = "NEUTRAL"
                continue

            macro_uptrend = slope > 0
            macro_downtrend = slope < 0
            price_above_200 = price > s200
            price_below_200 = price < s200
            sma_bullish = s50 > s200
            sma_bearish = s50 < s200

            if price_above_200 and sma_bullish and macro_uptrend:
                self.regimes[d] = "BULLISH"
            elif price_below_200 and sma_bearish:
                self.regimes[d] = "BEARISH"
            elif macro_downtrend and (price_above_200 or sma_bullish):
                self.regimes[d] = "BEAR_RALLY"
            else:
                self.regimes[d] = "NEUTRAL"

        if self.regimes:
            counts = {"BULLISH": 0, "NEUTRAL": 0, "BEAR_RALLY": 0, "BEARISH": 0}
            for r in self.regimes.values():
                counts[r] = counts.get(r, 0) + 1
            total = len(self.regimes)
            logger.info(f"\n{'='*70}")
            logger.info(f"RÉGIMEN DE MERCADO ({self.regime_benchmark})")
            logger.info(f"{'='*70}")
            for regime, count in counts.items():
                logger.info(f"   {regime:10s}: {count:4d} días ({count/total*100:5.1f}%)")

    def get_regime(self, analysis_date) -> str:
        return self.regimes.get(analysis_date, "NEUTRAL")

    def _build_fundamental_task(self, agent, ticker: str, strict: bool = False) -> Task:
        if not strict:
            description = f"""Analiza los fundamentos de {ticker}:
            - Ratios: P/E, P/B, deuda/equity, liquidez, ROE
            - Crecimiento: revenue YoY, earnings growth
            - Rentabilidad: márgenes brutos, operativos, netos
            - Riesgos: Altman Z-Score, free cash flow, deuda creciente

            Penalizaciones:
            - Free cash flow negativo → -3 puntos
            - Deuda/Equity > 2.0 → -2 puntos
            - Revenue declining > 10% → -2 puntos
            - Current ratio < 1.0 → -2 puntos
            - Z-Score < 1.23 → rating máximo 4

            Responde EXCLUSIVAMENTE con un objeto JSON:
            {{
                "score": <0-10>,
                "confidence": <0-100>,
                "risk_level": "LOW o MEDIUM o HIGH o CRITICAL",
                "recommendation": "BUY o HOLD o SELL o AVOID",
                "summary": "breve resumen"
            }}
            """
        else:
            description = f"""Responde con UNA SOLA LÍNEA, SOLO este JSON:
            {{"score": <0-10>, "confidence": <0-100>, "risk_level": "LOW", "recommendation": "BUY", "summary": "breve"}}
            Análisis fundamental de {ticker}.
            """

        return Task(description=description, agent=agent, expected_output="Un único objeto JSON")

    def run_fundamental_analysis(self) -> None:
        logger.info(f"\n{'='*70}")
        logger.info("ANÁLISIS FUNDAMENTAL (1 vez por ticker, con caché persistente)")
        logger.info(f"{'='*70}\n")

        persistent_cache = _load_fundamental_cache()

        for ticker in self.tickers:
            if ticker not in self.historical_data:
                continue

            # Usar caché persistente si existe (evita re-llamar al LLM entre runs)
            if ticker in persistent_cache:
                self.fundamental_cache[ticker] = persistent_cache[ticker]
                cached = persistent_cache[ticker]
                logger.info(
                    f"  ✓ {ticker} (caché): Score={cached.get('score')}/10 | "
                    f"Confidence={cached.get('confidence')}%"
                )
                continue

            analysis = None
            for attempt, strict in enumerate([False, True]):
                try:
                    if attempt == 0:
                        logger.info(f"  → Analizando {ticker}...")
                    else:
                        logger.info(f"    ↻ Reintentando {ticker}...")

                    fundamental_agent = create_fundamental_agent()
                    task = self._build_fundamental_task(fundamental_agent, ticker, strict=strict)
                    crew = Crew(
                        agents=[fundamental_agent],
                        tasks=[task],
                        process=Process.sequential,
                        verbose=False,
                    )
                    crew_result = crew.kickoff()
                    output_str = str(crew_result.raw)
                    parsed = extract_json(output_str)

                    if parsed is None or parsed.get("score") is None:
                        logger.warning(f"    ⚠️ JSON inválido: {output_str[:200]}")
                        continue

                    analysis = parsed
                    break
                except Exception as e:
                    logger.error(f"    ❌ Error: {e}")

            if analysis is None:
                analysis = {"score": 5, "confidence": 30, "error": "Parse error"}

            try:
                analysis["score"] = max(0, min(10, float(analysis.get("score", 5))))
            except (TypeError, ValueError):
                analysis["score"] = 5
            try:
                analysis["confidence"] = max(0, min(100, float(analysis.get("confidence", 30))))
            except (TypeError, ValueError):
                analysis["confidence"] = 30

            self.fundamental_cache[ticker] = analysis
            # Persistir en caché para futuras ejecuciones del mismo test
            persistent_cache[ticker] = analysis
            _save_fundamental_cache(persistent_cache)
            logger.info(
                f"    Score: {analysis.get('score', '?')}/10 | "
                f"Confidence: {analysis.get('confidence', '?')}%"
            )

    def _df_until(self, ticker: str, date) -> Optional[pd.DataFrame]:
        df = self.historical_data.get(ticker)
        if df is None:
            return None
        mask = df.index.date <= date
        sub = df.loc[mask]
        return sub if len(sub) > 0 else None

    def get_price_at_date(self, ticker: str, date) -> Optional[float]:
        sub = self._df_until(ticker, date)
        if sub is None:
            return None
        return float(sub["Close"].iloc[-1])

    def get_trading_days(self) -> List:
        all_dates = set()
        for df in self.historical_data.values():
            for d in df.index.date:
                if self.start_date <= d <= self.end_date:
                    all_dates.add(d)
        return sorted(all_dates)

    def analyze_day(self, analysis_date) -> Dict:
        regime = self.get_regime(analysis_date)
        profile = REGIME_PROFILES[regime]
        candidates = []

        for ticker in self.tickers:
            fundamental = self.fundamental_cache.get(ticker)
            if not fundamental or fundamental.get("score", 0) < profile["min_fundamental_score"]:
                continue

            df = self._df_until(ticker, analysis_date)
            if df is None or len(df) < 50:
                continue

            technical = TechnicalIndicators.calculate(df)
            sentiment = NEUTRAL_SENTIMENT
            decision = self.decision_engine.evaluate_buy_opportunity_new(
                ticker, fundamental, technical, sentiment
            )

            if decision.get("decision") != "BUY_CANDIDATE":
                continue

            min_conv = profile.get("min_conviction")
            if min_conv and CONVICTION_ORDER.get(decision.get("conviction"), 0) < CONVICTION_ORDER.get(min_conv, 0):
                continue

            min_score = profile.get("min_combined_score")
            if min_score and decision.get("combined_score", 0) < min_score:
                continue

            decision["regime"] = regime
            candidates.append(decision)

        return {"candidates": candidates, "regime": regime}

    def simulate_day(self, analysis_date, daily_analysis: Dict) -> None:
        regime = daily_analysis.get("regime", self.get_regime(analysis_date))
        profile = REGIME_PROFILES[regime]

        if self.daily_portfolio_values:
            last_value = self.daily_portfolio_values[-1]["total_value"]
        else:
            last_value = self.initial_capital

        self.peak_portfolio_value = max(self.peak_portfolio_value, last_value)
        current_drawdown = (
            (self.peak_portfolio_value - last_value) / self.peak_portfolio_value * 100
            if self.peak_portfolio_value > 0 else 0
        )

        if not self.trading_paused and current_drawdown >= self.pause_drawdown_threshold:
            self.trading_paused = True
            self.days_paused_streak = 0
            logger.info(
                f"  🛑 CIRCUIT BREAKER ({analysis_date}): drawdown {current_drawdown:.1f}% → PAUSA"
            )
        elif self.trading_paused:
            if current_drawdown <= self.resume_drawdown_threshold:
                self.trading_paused = False
                self.days_paused_streak = 0
                logger.info(f"  ✅ Drawdown recuperado ({analysis_date}) → REANUDANDO")
            else:
                self.days_paused_streak += 1
                if self.days_paused_streak >= self.max_pause_days:
                    self.trading_paused = False
                    self.days_paused_streak = 0
                    self.peak_portfolio_value = last_value
                    logger.info(f"  ⏰ Pausa máxima ({analysis_date}) → REANUDANDO")

        if self.trading_paused:
            self.paused_days_count += 1

        # ── Compras ──
        # Calcular valor total del portfolio para checks de concentración
        _portfolio_value = self.current_capital + sum(
            lot["qty"] * (self.get_price_at_date(tk, analysis_date) or 0)
            for tk, lots in self.positions.items()
            for lot in lots
        )

        for candidate in daily_analysis.get("candidates", []):
            if self.trading_paused:
                break

            ticker = candidate.get("ticker")
            conviction = candidate.get("conviction")
            score = candidate.get("combined_score", 0)

            # ── Cooldown tras stop loss ──
            cooldown_until = self.stop_loss_cooldown.get(ticker)
            if cooldown_until and analysis_date < cooldown_until:
                continue

            price = self.get_price_at_date(ticker, analysis_date)
            if not price:
                continue

            technical = candidate.get("technical", {})
            rsi = technical.get("rsi", 55.0)
            is_new_position = ticker not in self.positions

            # ── Filtro RSI: evitar entrar en sobrecompra ──
            # Nueva posición en BULLISH: hasta RSI 72 (rango "sano alcista").
            # Nueva posición en otros regímenes: máx RSI 62 (más estricto).
            # Adición a posición existente: solo en dip (RSI ≤ 52 BULLISH, ≤ 47 resto).
            rsi_limit_new = 72 if regime == "BULLISH" else 62
            rsi_limit_add = 52 if regime == "BULLISH" else 47
            if is_new_position and rsi > rsi_limit_new:
                continue
            if not is_new_position and rsi > rsi_limit_add:
                continue

            # ── Anti-pirámide: límite de frecuencia por ticker ──
            # Máximo 1 compra del mismo ticker cada 15 días naturales.
            # Excepción: RSI < BUY_FREQUENCY_DEEP_DIP_RSI (dip profundo = dip-buy válido).
            last_buy = self.last_buy_date.get(ticker)
            if last_buy is not None:
                days_gap = (analysis_date - last_buy).days
                min_gap = 8 if rsi < BUY_FREQUENCY_DEEP_DIP_RSI else BUY_FREQUENCY_LIMIT_DAYS
                if days_gap < min_gap:
                    continue

            # ── Concentración máxima por ticker: 50 % del portfolio ──
            if ticker in self.positions and _portfolio_value > 0:
                position_value = sum(lot["qty"] * price for lot in self.positions[ticker])
                if position_value / _portfolio_value > 0.50:
                    continue

            conviction_pct = profile["conviction_pct"].get(conviction, 0.0)
            if conviction_pct <= 0:
                continue

            amount_to_invest = self.current_capital * conviction_pct
            quantity = int(amount_to_invest / price)

            # ── Tamaño mínimo: evitar micro-lotes (≥ 2 acciones) ──
            if quantity < 2:
                continue

            cost = quantity * price
            fee = cost * self.transaction_cost_pct
            total_outflow = cost + fee

            # Ajuste si no hay liquidez suficiente para incluir la fee
            while total_outflow > self.current_capital and quantity > 0:
                quantity -= 1
                cost = quantity * price
                fee = cost * self.transaction_cost_pct
                total_outflow = cost + fee

            if quantity >= 2 and total_outflow <= self.current_capital:
                self.current_capital -= total_outflow
                self.total_transaction_costs += fee
                self.last_buy_date[ticker] = analysis_date  # registrar para anti-pirámide

                self.positions.setdefault(ticker, []).append({
                    "qty": quantity,
                    "entry_price": price,
                    "entry_date": analysis_date,
                    "conviction": conviction,
                    "score": score,
                    "peak_price": price,
                    "entry_regime": regime,
                    "entry_fee": fee,
                })
                self.trades.append({
                    "date": analysis_date,
                    "ticker": ticker,
                    "action": "BUY",
                    "price": price,
                    "quantity": quantity,
                    "amount": cost,
                    "fee": fee,
                    "conviction": conviction,
                    "regime": regime,
                })

        # ── Hedge ──
        # En BEARISH/BEAR_RALLY desplegamos PSQ (ETF inverso Nasdaq) sin exigir
        # señal ALCISTA propia: en mercados bajistas PSQ sube por definición, y
        # esperar confirmación técnica puede hacer perder el mejor punto de entrada.
        # Solo evitamos entrar si PSQ muestra señal BAJISTA activa (indicaría rebote
        # del mercado que podría perjudicarnos).
        if regime in HEDGE_REGIMES and HEDGE_TICKER not in self.positions:
            hedge_df = self._df_until(HEDGE_TICKER, analysis_date)
            if hedge_df is not None and len(hedge_df) >= 50:
                hedge_technical = TechnicalIndicators.calculate(hedge_df)
                if hedge_technical.get("señal") != "BAJISTA":
                    hedge_price = self.get_price_at_date(HEDGE_TICKER, analysis_date)
                    if hedge_price:
                        amount = self.current_capital * HEDGE_ALLOCATION_PCT
                        qty = int(amount / hedge_price)

                        if qty > 0:
                            cost = qty * hedge_price
                            fee = cost * self.transaction_cost_pct
                            total_outflow = cost + fee

                            while total_outflow > self.current_capital and qty > 0:
                                qty -= 1
                                cost = qty * hedge_price
                                fee = cost * self.transaction_cost_pct
                                total_outflow = cost + fee

                            if qty > 0 and total_outflow <= self.current_capital:
                                self.current_capital -= total_outflow
                                self.total_transaction_costs += fee

                                self.positions[HEDGE_TICKER] = [{
                                    "qty": qty,
                                    "entry_price": hedge_price,
                                    "entry_date": analysis_date,
                                    "conviction": "HEDGE",
                                    "score": 0,
                                    "peak_price": hedge_price,
                                    "entry_regime": regime,
                                    "entry_fee": fee,
                                }]
                                self.trades.append({
                                    "date": analysis_date,
                                    "ticker": HEDGE_TICKER,
                                    "action": "BUY",
                                    "price": hedge_price,
                                    "quantity": qty,
                                    "amount": cost,
                                    "fee": fee,
                                    "conviction": "HEDGE",
                                    "regime": regime,
                                    "is_hedge": True,
                                })

        # ── Revisión de posiciones abiertas ──
        for ticker in list(self.positions.keys()):
            current_price = self.get_price_at_date(ticker, analysis_date)
            if not current_price:
                continue

            remaining_lots = []
            for lot in self.positions[ticker]:
                cost = lot["qty"] * lot["entry_price"]
                lot_value = lot["qty"] * current_price
                pnl = lot_value - cost
                pnl_pct = (pnl / cost * 100) if cost > 0 else 0

                lot["peak_price"] = max(lot.get("peak_price", lot["entry_price"]), current_price)
                drawdown_from_peak_pct = (
                    (current_price - lot["peak_price"]) / lot["peak_price"] * 100
                    if lot["peak_price"] > 0 else 0
                )

                is_hedge = (ticker == HEDGE_TICKER)
                if is_hedge:
                    params = HEDGE_EXIT_PARAMS
                    force_close_hedge = regime not in HEDGE_REGIMES
                else:
                    conv = lot.get("conviction", "MEDIUM")
                    # Stop loss: usa los parámetros del RÉGIMEN DE ENTRADA.
                    # Evita que transiciones a BEAR_RALLY/BEARISH apliquen stops
                    # más cortos (-5 %) a posiciones abiertas en BULLISH (-22 %).
                    # La salida macro la gestiona "Cambio de Régimen".
                    entry_regime_name = lot.get("entry_regime", regime)
                    entry_profile = REGIME_PROFILES.get(entry_regime_name, profile)
                    entry_params = (
                        entry_profile["exit_high"] if conv in ("VERY_HIGH", "HIGH")
                        else entry_profile["exit_low"]
                    )
                    # Take profit y trailing: régimen ACTUAL (gestión dinámica del momentum)
                    current_params = (
                        profile["exit_high"] if conv in ("VERY_HIGH", "HIGH")
                        else profile["exit_low"]
                    )
                    force_close_hedge = False

                sell_reason = None
                if force_close_hedge:
                    sell_reason = "Cierre Hedge"

                # ── Salida por cambio de régimen ──
                # Solo en BEARISH (no en BEAR_RALLY): los rebotes técnicos en tendencia
                # bajista son temporales. En posiciones ganadoras el stop loss desde
                # entrada del régimen BEAR_RALLY no dispara, por lo que se mantienen.
                # Evitamos así salidas precipitadas en años de recuperación (2023, 2025).
                elif (
                    not is_hedge
                    and lot.get("entry_regime") in ("BULLISH", "NEUTRAL")
                    and regime == "BEARISH"
                ):
                    sell_reason = "Cambio de Régimen"

                elif is_hedge:
                    # Para hedge (PSQ) usamos sus propios params fijos
                    if pnl_pct <= HEDGE_EXIT_PARAMS["stop_loss_pct"]:
                        sell_reason = "Stop Loss"
                    elif pnl_pct >= HEDGE_EXIT_PARAMS["take_profit_pct"]:
                        sell_reason = "Take Profit"
                    elif (
                        pnl_pct >= HEDGE_EXIT_PARAMS["trailing_trigger_pct"]
                        and drawdown_from_peak_pct <= -HEDGE_EXIT_PARAMS["trailing_stop_pct"]
                    ):
                        sell_reason = "Trailing Stop"
                else:
                    # Stop loss con confirmación de 3 días consecutivos.
                    # Filtra caídas en V (COVID-2020: sólo 2 días bajo el umbral
                    # antes del rebote masivo) sin afectar mercados bajistas
                    # sostenidos donde el precio permanece bajo más de 3 jornadas.
                    if pnl_pct <= entry_params["stop_loss_pct"]:
                        lot["days_below_stop"] = lot.get("days_below_stop", 0) + 1
                        if lot["days_below_stop"] >= 3:
                            sell_reason = "Stop Loss"
                    else:
                        lot["days_below_stop"] = 0
                    # Take profit y trailing: régimen actual (ajuste dinámico)
                    if sell_reason is None and pnl_pct >= current_params["take_profit_pct"]:
                        sell_reason = "Take Profit"
                    elif sell_reason is None and (
                        pnl_pct >= current_params["trailing_trigger_pct"]
                        and drawdown_from_peak_pct <= -current_params["trailing_stop_pct"]
                    ):
                        sell_reason = "Trailing Stop"

                if sell_reason:
                    fee = lot_value * self.transaction_cost_pct
                    net_inflow = lot_value - fee
                    self.current_capital += net_inflow
                    self.total_transaction_costs += fee

                    entry_fee = lot.get("entry_fee", 0)
                    pnl_net = pnl - entry_fee - fee

                    self.trades.append({
                        "date": analysis_date,
                        "ticker": ticker,
                        "action": "SELL",
                        "price": current_price,
                        "quantity": lot["qty"],
                        "amount": lot_value,
                        "fee": fee,
                        "pnl": pnl_net,
                        "pnl_gross": pnl,
                        "pnl_pct": pnl_pct,
                        "reason": sell_reason,
                        "regime": regime,
                        "regime_at_entry": lot.get("entry_regime"),
                        "is_hedge": is_hedge,
                    })

                    if not is_hedge:
                        if sell_reason == "Stop Loss":
                            # Cooldown dependiente del régimen en el que disparó el stop
                            days = STOP_LOSS_COOLDOWN.get(regime, 25)
                            self.stop_loss_cooldown[ticker] = analysis_date + timedelta(days=days)
                        elif sell_reason == "Cambio de Régimen":
                            # 45 días mínimos; en bear sostenido el régimen ya bloquea re-entrada
                            self.stop_loss_cooldown[ticker] = analysis_date + timedelta(days=45)
                else:
                    remaining_lots.append(lot)

            if remaining_lots:
                self.positions[ticker] = remaining_lots
            else:
                del self.positions[ticker]

        positions_value = 0.0
        for ticker, lots in self.positions.items():
            current_price = self.get_price_at_date(ticker, analysis_date)
            if current_price:
                for lot in lots:
                    positions_value += lot["qty"] * current_price

        total_value = self.current_capital + positions_value
        self.daily_portfolio_values.append({
            "date": analysis_date,
            "total_value": total_value,
            "cash": self.current_capital,
            "positions_value": positions_value,
            "return_pct": ((total_value - self.initial_capital) / self.initial_capital) * 100,
            "regime": regime,
        })

    def run_backtest(self) -> Dict:
        logger.info(f"\n{'='*70}")
        logger.info(f"INICIANDO BACKTEST: {self.start_date} → {self.end_date}")
        logger.info(f"{'='*70}\n")

        self.preload_data()
        if not self.historical_data:
            return {"error": "No se pudieron descargar datos históricos"}

        self.precompute_regimes()
        self.run_fundamental_analysis()

        trading_days = self.get_trading_days()
        logger.info(f"\n{'='*70}")
        logger.info(f"SIMULANDO {len(trading_days)} DÍAS DE TRADING")
        logger.info(f"{'='*70}\n")

        for i, day in enumerate(trading_days):
            daily_analysis = self.analyze_day(day)
            self.simulate_day(day, daily_analysis)

            if (i + 1) % 50 == 0 or (i + 1) == len(trading_days):
                last = self.daily_portfolio_values[-1]
                logger.info(
                    f"  Día {i+1}/{len(trading_days)} ({day}) → "
                    f"${last['total_value']:,.2f} ({last['return_pct']:+.2f}%)"
                )

        return self.calculate_metrics()

    def calculate_metrics(self) -> Dict:
        if not self.daily_portfolio_values:
            return {"error": "No data"}

        initial_value = self.initial_capital
        final_value = self.daily_portfolio_values[-1]["total_value"]
        total_return_pct = ((final_value - initial_value) / initial_value) * 100

        peak = initial_value
        max_drawdown = 0.0
        for day in self.daily_portfolio_values:
            value = day["total_value"]
            if value > peak:
                peak = value
            drawdown = ((peak - value) / peak) * 100
            max_drawdown = max(max_drawdown, drawdown)

        values = [d["total_value"] for d in self.daily_portfolio_values]
        daily_returns = pd.Series(values).pct_change().dropna()
        if len(daily_returns) > 1 and daily_returns.std() > 0:
            sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * (252 ** 0.5)
        else:
            sharpe_ratio = 0.0

        sell_trades = [t for t in self.trades if t["action"] == "SELL"]
        winning_trades = len([t for t in sell_trades if t.get("pnl", 0) > 0])
        win_rate = (winning_trades / len(sell_trades) * 100) if sell_trades else 0.0

        regime_days = {"BULLISH": 0, "NEUTRAL": 0, "BEAR_RALLY": 0, "BEARISH": 0}
        for r in self.regimes.values():
            regime_days[r] = regime_days.get(r, 0) + 1
        regime_trades = {"BULLISH": 0, "NEUTRAL": 0, "BEAR_RALLY": 0, "BEARISH": 0}
        for t in self.trades:
            if t["action"] == "BUY":
                regime_trades[t.get("regime", "NEUTRAL")] = regime_trades.get(t.get("regime", "NEUTRAL"), 0) + 1

        buyhold_return = self.calculate_buyhold_return()
        perfect_timing_return = self.calculate_perfect_timing_return()
        spy_return = self.calculate_spy_return()

        return {
            "backtest_period": {
                "start": str(self.start_date),
                "end": str(self.end_date),
                "trading_days": len(self.daily_portfolio_values),
                "tickers": self.tickers,
            },
            "fundamental_scores": {
                t: self.fundamental_cache.get(t, {}).get("score")
                for t in self.tickers
            },
            "performance": {
                "initial_capital": initial_value,
                "final_value": round(final_value, 2),
                "total_return_pct": round(total_return_pct, 2),
                "max_drawdown_pct": round(max_drawdown, 2),
                "sharpe_ratio": round(sharpe_ratio, 2),
            },
            "trading": {
                "total_buys": len([t for t in self.trades if t["action"] == "BUY"]),
                "total_sells": len(sell_trades),
                "open_positions": len(self.positions),
                "win_rate_pct": round(win_rate, 2),
                "stop_loss_count": len([t for t in sell_trades if t.get("reason") == "Stop Loss"]),
                "circuit_breaker_paused_days": self.paused_days_count,
            },
            "costs": {
                "transaction_cost_pct": self.transaction_cost_pct * 100,
                "total_transaction_costs": round(self.total_transaction_costs, 2),
                "cost_as_pct_of_initial": round(self.total_transaction_costs / self.initial_capital * 100, 2),
            },
            "hedge": {
                "ticker": HEDGE_TICKER,
                "trades": len([t for t in self.trades if t.get("is_hedge")]),
                "pnl": round(sum(t.get("pnl", 0) for t in self.trades if t.get("is_hedge") and t["action"] == "SELL"), 2),
            },
            "regime": {"days": regime_days, "buys": regime_trades},
            "comparison": {
                "bot_return_pct": round(total_return_pct, 2),
                "buyhold_return_pct": round(buyhold_return, 2),
                "perfect_timing_return_pct": round(perfect_timing_return, 2),
                "spy_return_pct": round(spy_return, 2),
                "bot_vs_buyhold_diff": round(total_return_pct - buyhold_return, 2),
                "bot_vs_perfect_diff": round(perfect_timing_return - total_return_pct, 2),
                "bot_vs_spy_diff": round(total_return_pct - spy_return, 2),
            },
        }

    def calculate_buyhold_return(self) -> float:
        valid = [t for t in self.tickers if t in self.historical_data]
        if not valid:
            return 0.0
        allocation = self.initial_capital / len(valid)
        final_value = 0.0
        for ticker in valid:
            df = self.historical_data[ticker]
            period = df[(df.index.date >= self.start_date) & (df.index.date <= self.end_date)]
            if len(period) < 2:
                final_value += allocation
                continue
            start_price = float(period["Close"].iloc[0])
            end_price = float(period["Close"].iloc[-1])
            shares = allocation / start_price
            final_value += shares * end_price
        return ((final_value - self.initial_capital) / self.initial_capital) * 100

    def calculate_perfect_timing_return(self) -> float:
        valid = [t for t in self.tickers if t in self.historical_data]
        if not valid:
            return 0.0
        allocation = self.initial_capital / len(valid)
        final_value = 0.0
        for ticker in valid:
            df = self.historical_data[ticker]
            period = df[(df.index.date >= self.start_date) & (df.index.date <= self.end_date)]
            closes = period["Close"].values
            if len(closes) < 2:
                final_value += allocation
                continue
            best_return = 0.0
            min_so_far = closes[0]
            for price in closes[1:]:
                if price > min_so_far:
                    ret = (price - min_so_far) / min_so_far
                    best_return = max(best_return, ret)
                min_so_far = min(min_so_far, price)
            final_value += allocation * (1 + best_return)
        return ((final_value - self.initial_capital) / self.initial_capital) * 100

    def calculate_spy_return(self) -> float:
        try:
            spy = yf.download("SPY", start=self.start_date, end=self.end_date + timedelta(days=1), progress=False)
            if isinstance(spy.columns, pd.MultiIndex):
                spy.columns = spy.columns.get_level_values(0)
            if len(spy) >= 2:
                start_price = float(spy["Close"].iloc[0])
                end_price = float(spy["Close"].iloc[-1])
                return ((end_price - start_price) / start_price) * 100
        except Exception as e:
            logger.warning(f"No se pudo calcular SPY: {e}")
        return 0.0

    def print_report(self, metrics: Dict) -> None:
        if "error" in metrics:
            logger.error(f"Error: {metrics['error']}")
            return

        logger.info(f"\n{'='*70}")
        logger.info("REPORTE DE BACKTEST [con costes de transacción]")
        logger.info(f"{'='*70}\n")

        period = metrics["backtest_period"]
        logger.info(f"📅 Período: {period['start']} → {period['end']}")
        logger.info(f"   ({period['trading_days']} días de trading)")
        logger.info(f"   Tickers: {', '.join(period['tickers'])}\n")

        logger.info("📊 SCORES FUNDAMENTALES:")
        for ticker, score in metrics["fundamental_scores"].items():
            estado = "✅" if score is not None and score >= 6 else "⊘ filtrado"
            logger.info(f"   {ticker}: {score}/10  {estado}")

        perf = metrics["performance"]
        logger.info(f"\n💰 RENDIMIENTO (neto de comisiones):")
        logger.info(f"   Capital inicial:  ${perf['initial_capital']:,.2f}")
        logger.info(f"   Capital final:    ${perf['final_value']:,.2f}")
        logger.info(f"   Return Total:     {perf['total_return_pct']:+.2f}%")
        logger.info(f"   Max Drawdown:     -{perf['max_drawdown_pct']:.2f}%")
        logger.info(f"   Sharpe Ratio:     {perf['sharpe_ratio']:.2f}")

        costs = metrics["costs"]
        logger.info(f"\n💸 COSTES DE TRANSACCIÓN:")
        logger.info(f"   Coste por op:     {costs['transaction_cost_pct']:.2f}%")
        logger.info(f"   Total pagado:     ${costs['total_transaction_costs']:,.2f}")
        logger.info(f"   % del inicial:    {costs['cost_as_pct_of_initial']:.2f}%")

        trading = metrics["trading"]
        logger.info(f"\n📈 ACTIVIDAD DE TRADING:")
        logger.info(f"   Compras:             {trading['total_buys']}")
        logger.info(f"   Ventas:              {trading['total_sells']}")
        logger.info(f"   Posiciones abiertas: {trading['open_positions']}")
        logger.info(f"   Win Rate:            {trading['win_rate_pct']:.2f}%")
        logger.info(f"   Stop Losses:         {trading['stop_loss_count']}")
        if trading["circuit_breaker_paused_days"] > 0:
            logger.info(f"   🛑 Circuit breaker: {trading['circuit_breaker_paused_days']} días")

        hedge = metrics.get("hedge", {})
        if hedge.get("trades", 0) > 0:
            sign = "+" if hedge["pnl"] >= 0 else ""
            logger.info(f"   🛡️  Hedge: {hedge['trades']} ops, P&L: {sign}${hedge['pnl']:,.2f}")

        regime = metrics.get("regime", {})
        if regime:
            days = regime.get("days", {})
            buys = regime.get("buys", {})
            total_days = sum(days.values()) or 1
            logger.info(f"\n🌡️  RÉGIMEN ({self.regime_benchmark}):")
            for r in ("BULLISH", "NEUTRAL", "BEAR_RALLY", "BEARISH"):
                d = days.get(r, 0)
                b = buys.get(r, 0)
                logger.info(f"   {r:10s}: {d:4d} días ({d/total_days*100:5.1f}%)  →  {b:3d} compras")

        comp = metrics["comparison"]
        logger.info(f"\n🏁 COMPARACIÓN:")
        logger.info(f"   Bot (neto):      {comp['bot_return_pct']:>8.2f}%")
        logger.info(f"   Buy & Hold:      {comp['buyhold_return_pct']:>8.2f}%")
        logger.info(f"   SPY:             {comp['spy_return_pct']:>8.2f}%")
        logger.info(f"   Perfect Timing:  {comp['perfect_timing_return_pct']:>8.2f}%")
        logger.info(f"\n   Bot vs Buy&Hold: {comp['bot_vs_buyhold_diff']:+.2f} pp")
        logger.info(f"   Bot vs SPY:      {comp['bot_vs_spy_diff']:+.2f} pp")

        logger.info(f"\n{'='*70}\n")