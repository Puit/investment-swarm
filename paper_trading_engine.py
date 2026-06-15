"""
PAPER TRADING ENGINE
=====================

Motor de paper trading en tiempo real, diseñado para usarse desde el
dashboard (Streamlit).

Principios de diseño (acordados con el usuario):

1. El agente FUNDAMENTAL y el agente de SENTIMIENTO solo se ejecutan
   cuando el usuario lo pide explícitamente desde el dashboard (botón
   "Analizar" / "Renovar"). Los resultados se cachean con timestamp.

2. El agente TÉCNICO gestiona el dinero de forma continua sobre una
   WATCHLIST que el usuario define. En cada "scan":
     - Calcula el régimen de mercado (XLK) y el indicador técnico de
       cada ticker con datos 100% en tiempo real (sin look-ahead bias,
       porque es información real del momento).
     - Combina con el fundamental/sentimiento cacheados (o valores por
       defecto neutros si el usuario aún no los ha pedido).
     - Decide compra/venta con el InvestmentDecisionEngine + REGIME_PROFILES
       (misma lógica validada en el backtest del +185%).

3. Modo "invertir ahora": fuerza la entrada en los tickers de la
   watchlist que no tengan posición abierta, repartiendo el cash
   disponible entre ellos, SIN esperar una señal técnica de entrada
   óptima. Las salidas (stop loss / take profit / trailing) siempre
   se evalúan, en cualquier modo.

Persistencia: JSON simple en disco (data/paper_trading_state.json).
Suficiente para un solo usuario / paper trading.
"""

import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf

from crewai import Crew, Task, Process
from agents.fundamental_agent import create_fundamental_agent
from investment_decision_engine import InvestmentDecisionEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PaperTrading")


# ═══════════════════════════════════════════════════════════════
# UTILIDADES COMPARTIDAS (mismas que backtest.py)
# ═══════════════════════════════════════════════════════════════

def extract_json(text: str) -> Optional[dict]:
    """Extrae el primer objeto JSON válido de un texto, tolerante a
    texto extra y comas finales (igual que en backtest.py)."""

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
                    if "score" in obj or "sentimiento" in obj:
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
    "resumen": "Sin análisis de sentimiento todavía (valor neutro por defecto)",
}

# Score fundamental por defecto si el usuario aún no ha pedido el
# análisis fundamental de ese ticker. 6/10 = pasa el filtro mínimo de
# BULLISH/NEUTRAL pero NO el de BEARISH/BEAR_RALLY (que exigen 8).
# Esto refleja: "confío en este ticker lo bastante para vigilarlo,
# pero no tengo aún el análisis profundo".
DEFAULT_FUNDAMENTAL_SCORE = 6.0
DEFAULT_FUNDAMENTAL = {
    "score": DEFAULT_FUNDAMENTAL_SCORE,
    "confidence": 50,
    "recommendation": "HOLD",
    "summary": "Sin análisis fundamental todavía (score neutro por defecto)",
}

CONVICTION_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "VERY_HIGH": 3}

# Coste de transacción realista para Interactive Brokers
TRANSACTION_COST_PCT = 0.0005  # 0.05%

# Cuánto tiempo se considera "fresco" un análisis cacheado
FUNDAMENTAL_CACHE_DAYS = 7
SENTIMENT_CACHE_HOURS = 6


# ═══════════════════════════════════════════════════════════════
# HEDGE (idéntico a backtest.py)
# ═══════════════════════════════════════════════════════════════

HEDGE_TICKER = "PSQ"
HEDGE_REGIMES = ("BEARISH", "BEAR_RALLY")
HEDGE_ALLOCATION_PCT = 0.25
HEDGE_EXIT_PARAMS = {
    "stop_loss_pct": -10,
    "take_profit_pct": 20,
    "trailing_trigger_pct": 10,
    "trailing_stop_pct": 8,
}


# ═══════════════════════════════════════════════════════════════
# PERFILES DE RÉGIMEN (base validada del +185%)
# ═══════════════════════════════════════════════════════════════

REGIME_PROFILES = {
    "BULLISH": {
        "description": "Tendencia alcista (precio y SMA50 > SMA200 del benchmark)",
        "min_fundamental_score": 5,
        "min_conviction": None,
        "min_combined_score": None,
        "conviction_pct": {"VERY_HIGH": 0.60, "HIGH": 0.25, "MEDIUM": 0.10, "LOW": 0.05},
        "exit_high": {"stop_loss_pct": -12, "take_profit_pct": 50, "trailing_trigger_pct": 15, "trailing_stop_pct": 10},
        "exit_low":  {"stop_loss_pct": -10, "take_profit_pct": 25, "trailing_trigger_pct": 10, "trailing_stop_pct": 8},
    },
    "NEUTRAL": {
        "description": "Sin tendencia clara (lateral)",
        "min_fundamental_score": 6,
        "min_conviction": None,
        "min_combined_score": None,
        "conviction_pct": {"VERY_HIGH": 0.40, "HIGH": 0.15, "MEDIUM": 0.07, "LOW": 0.03},
        "exit_high": {"stop_loss_pct": -8, "take_profit_pct": 18, "trailing_trigger_pct": 8, "trailing_stop_pct": 6},
        "exit_low":  {"stop_loss_pct": -7, "take_profit_pct": 12, "trailing_trigger_pct": 6, "trailing_stop_pct": 5},
    },
    "BEARISH": {
        "description": "Tendencia bajista (precio y SMA50 < SMA200 del benchmark)",
        "min_fundamental_score": 8,
        "min_conviction": "VERY_HIGH",
        "min_combined_score": 0.75,
        "conviction_pct": {"VERY_HIGH": 0.20, "HIGH": 0.0, "MEDIUM": 0.0, "LOW": 0.0},
        "exit_high": {"stop_loss_pct": -7, "take_profit_pct": 15, "trailing_trigger_pct": 6, "trailing_stop_pct": 5},
        "exit_low":  {"stop_loss_pct": -6, "take_profit_pct": 10, "trailing_trigger_pct": 5, "trailing_stop_pct": 4},
    },
    "BEAR_RALLY": {
        "description": "Rebote dentro de tendencia bajista mayor",
        "min_fundamental_score": 8,
        "min_conviction": "VERY_HIGH",
        "min_combined_score": 0.70,
        "conviction_pct": {"VERY_HIGH": 0.15, "HIGH": 0.0, "MEDIUM": 0.0, "LOW": 0.0},
        "exit_high": {"stop_loss_pct": -6, "take_profit_pct": 12, "trailing_trigger_pct": 5, "trailing_stop_pct": 4},
        "exit_low":  {"stop_loss_pct": -5, "take_profit_pct": 8, "trailing_trigger_pct": 4, "trailing_stop_pct": 3},
    },
}


# ═══════════════════════════════════════════════════════════════
# INDICADORES TÉCNICOS (idéntico a backtest.py)
# ═══════════════════════════════════════════════════════════════

class TechnicalIndicators:
    """Calcula indicadores técnicos sobre un DataFrame OHLCV en vivo.
    Mismo cálculo que en el backtest → cero look-ahead bias, porque
    aquí SIEMPRE usamos datos hasta "ahora"."""

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
        macd_above = bool(macd_line.iloc[-1] > signal_line.iloc[-1])

        bb_mid = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        bb_lower = (bb_mid - 2 * bb_std).iloc[-1]
        bb_upper = (bb_mid + 2 * bb_std).iloc[-1]

        vol_avg20 = volume.rolling(20).mean()
        vol_ratio = (
            float(volume.iloc[-1] / vol_avg20.iloc[-1])
            if vol_avg20.iloc[-1] and vol_avg20.iloc[-1] > 0
            else 1.0
        )
        volume_confirms = vol_ratio > 1.2

        support = float(close.tail(20).min())
        resistance = float(close.tail(20).max())

        trend_bullish = current_price > sma20_val > sma50_val
        trend_bearish = current_price < sma20_val < sma50_val
        if sma200_val:
            trend_bullish = trend_bullish and sma50_val > sma200_val
            trend_bearish = trend_bearish and sma50_val < sma200_val

        rsi_oversold = rsi_val < 35
        rsi_overbought = rsi_val > 65

        confirmations = {"trend": False, "rsi": False, "macd": False, "volumen": volume_confirms}
        bullish_points = 0
        bearish_points = 0

        if trend_bullish:
            bullish_points += 1
            confirmations["trend"] = True
        elif trend_bearish:
            bearish_points += 1

        if rsi_oversold:
            bullish_points += 1
            confirmations["rsi"] = True
        elif rsi_overbought:
            bearish_points += 1

        if macd_above:
            bullish_points += 1
            confirmations["macd"] = True
        else:
            bearish_points += 1

        if volume_confirms:
            if bullish_points > bearish_points:
                bullish_points += 1
            elif bearish_points > bullish_points:
                bearish_points += 1

        if bullish_points >= 3:
            señal = "ALCISTA"
            confianza = min(95, 50 + bullish_points * 12)
        elif bearish_points >= 3:
            señal = "BAJISTA"
            confianza = min(95, 50 + bearish_points * 12)
        else:
            señal = "LATERAL"
            confianza = 40

        entry = current_price
        if señal == "ALCISTA":
            stop_loss = round(min(support, sma50_val) * 0.98, 2)
            target = round(resistance * 1.05, 2)
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
                "oversold" if rsi_oversold else "overbought" if rsi_overbought else "neutral"
            ),
            "tendencia": "ALCISTA" if trend_bullish else "BAJISTA" if trend_bearish else "LATERAL",
            "entrada_sugerida": round(entry, 2),
            "stop_loss": stop_loss,
            "target_price": target,
            "reward_risk_ratio": rr_ratio,
            "confirmaciones": confirmations,
            "resumen": (
                f"SMA20={sma20_val:.2f} SMA50={sma50_val:.2f} "
                f"RSI={rsi_val:.1f} VolRatio={vol_ratio:.2f} "
                f"BB=[{bb_lower:.2f},{bb_upper:.2f}]"
            ),
        }


# ═══════════════════════════════════════════════════════════════
# MOTOR DE PAPER TRADING
# ═══════════════════════════════════════════════════════════════

DEFAULT_STATE_FILE = Path("data/paper_trading_state.json")

# Orígenes de operaciones
OPERATION_ORIGIN_AUTO = "AUTO"
OPERATION_ORIGIN_MANUAL_TELEGRAM = "MANUAL_TELEGRAM"
OPERATION_ORIGIN_MANUAL_DASHBOARD = "MANUAL_DASHBOARD"

# Preferencias de análisis diarios por ticker
DEFAULT_ANALYSIS_PREFERENCES = {
    # "MSFT": {
    #     "daily_fundamental": True,
    #     "daily_sentiment": False,
    #     "analysis_time": "09:30"  # Hora del día (formato HH:MM)
    # }
}


class PaperTradingEngine:
    """
    Gestiona el estado del paper trading: cash, posiciones, watchlist,
    histórico de operaciones y cachés de análisis fundamental/sentimiento.

    Todo se persiste en un JSON simple en disco.
    """

    def __init__(self, state_file: Path = DEFAULT_STATE_FILE, initial_capital: float = 5000.0):
        self.state_file = Path(state_file)
        self.initial_capital = initial_capital
        self.decision_engine = InvestmentDecisionEngine()
        self.state = self._load_state()

    # ── Persistencia ──────────────────────────────────────────

    def _default_state(self) -> Dict:
        return {
            "cash": self.initial_capital,
            "initial_capital": self.initial_capital,
            "positions": {},          # ticker -> [lotes]
            "trade_history": [],
            "watchlist": [],
            "fundamental_analyses": {},  # ticker -> {data, timestamp}
            "sentiment_analyses": {},    # ticker -> {data, timestamp}
            "stop_loss_cooldown": {},    # ticker -> fecha límite ISO
            "peak_portfolio_value": self.initial_capital,
            "trading_paused": False,
            "pause_started_at": None,
            "regime_cache": None,        # {"regime": ..., "date": "YYYY-MM-DD"}
            "total_transaction_costs": 0.0,
            "created_at": datetime.now().isoformat(),
            "last_scan_at": None,
            "analysis_preferences": {},  # ticker -> {daily_fundamental, daily_sentiment, analysis_time}
            "pending_manual_operations": [],  # Operaciones pendientes de mercado cerrado
        }

    def _load_state(self) -> Dict:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"⚠️ No se pudo leer estado previo ({e}), creando nuevo.")
                state = self._default_state()
        else:
            state = self._default_state()

        # Forward-compat: rellenar claves nuevas que no existían en versiones anteriores
        for key, value in self._default_state().items():
            state.setdefault(key, value)

        return state

    def save(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2, default=str)

    def reset(self) -> None:
        """Reinicia completamente el paper trading (cash, posiciones, histórico).
        Mantiene los análisis fundamental/sentimiento cacheados (son caros)."""
        fundamental = self.state.get("fundamental_analyses", {})
        sentiment = self.state.get("sentiment_analyses", {})
        watchlist = self.state.get("watchlist", [])

        self.state = self._default_state()
        self.state["fundamental_analyses"] = fundamental
        self.state["sentiment_analyses"] = sentiment
        self.state["watchlist"] = watchlist
        self.save()

    # ── Watchlist ──────────────────────────────────────────────

    def add_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        if ticker and ticker not in self.state["watchlist"]:
            self.state["watchlist"].append(ticker)
            self.save()

    def remove_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        if ticker in self.state["watchlist"]:
            self.state["watchlist"].remove(ticker)
            self.save()

    # ── Análisis fundamental (on-demand) ──────────────────────

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
                "summary": "resumen de 2-4 frases explicando el porqué del score"
            }}
            """
        else:
            description = f"""Responde con UNA SOLA LÍNEA, SOLO este JSON:
            {{"score": <0-10>, "confidence": <0-100>, "risk_level": "LOW", "recommendation": "BUY", "summary": "breve"}}
            Análisis fundamental de {ticker}.
            """

        return Task(description=description, agent=agent, expected_output="Un único objeto JSON")

    def get_fundamental(self, ticker: str) -> Optional[Dict]:
        """Devuelve el análisis fundamental cacheado (o None si nunca se ha pedido)."""
        ticker = ticker.upper().strip()
        return self.state["fundamental_analyses"].get(ticker)

    def is_fundamental_stale(self, ticker: str) -> bool:
        entry = self.get_fundamental(ticker)
        if not entry:
            return True
        ts = datetime.fromisoformat(entry["timestamp"])
        return datetime.now() - ts > timedelta(days=FUNDAMENTAL_CACHE_DAYS)

    def run_fundamental_analysis(self, ticker: str, force: bool = False) -> Dict:
        """
        Ejecuta (o recupera de caché) el análisis fundamental de un ticker.

        - Si ya existe en caché y no es 'force', devuelve el cacheado.
        - Si no existe o force=True, llama al agente LLM y cachea el resultado.
        """
        ticker = ticker.upper().strip()

        if not force:
            cached = self.get_fundamental(ticker)
            if cached:
                return cached

        logger.info(f"📊 Ejecutando análisis fundamental de {ticker}...")

        analysis = None
        for attempt, strict in enumerate([False, True]):
            try:
                fundamental_agent = create_fundamental_agent()
                task = self._build_fundamental_task(fundamental_agent, ticker, strict=strict)
                crew = Crew(agents=[fundamental_agent], tasks=[task], process=Process.sequential, verbose=False)
                crew_result = crew.kickoff()
                output_str = str(crew_result.raw)
                parsed = extract_json(output_str)

                if parsed is None or parsed.get("score") is None:
                    logger.warning(f"  ⚠️ JSON inválido (intento {attempt+1}): {output_str[:200]}")
                    continue

                analysis = parsed
                break
            except Exception as e:
                logger.error(f"  ❌ Error: {e}")

        if analysis is None:
            analysis = {
                "score": DEFAULT_FUNDAMENTAL_SCORE,
                "confidence": 30,
                "recommendation": "HOLD",
                "summary": "Error al analizar (se usa score neutro por defecto)",
                "error": "Parse error",
            }

        try:
            analysis["score"] = max(0, min(10, float(analysis.get("score", DEFAULT_FUNDAMENTAL_SCORE))))
        except (TypeError, ValueError):
            analysis["score"] = DEFAULT_FUNDAMENTAL_SCORE
        try:
            analysis["confidence"] = max(0, min(100, float(analysis.get("confidence", 50))))
        except (TypeError, ValueError):
            analysis["confidence"] = 50

        entry = {"data": analysis, "timestamp": datetime.now().isoformat()}
        # Compatibilidad: exponer también score/confidence al nivel superior
        # para que sea fácil acceder desde el dashboard sin entrar en "data"
        entry["score"] = analysis["score"]
        entry["confidence"] = analysis["confidence"]

        self.state["fundamental_analyses"][ticker] = entry
        self.save()
        return entry

    # ── Análisis de sentimiento (on-demand) ───────────────────

    def _build_sentiment_task(self, agent, ticker: str, strict: bool = False) -> Task:
        if not strict:
            description = f"""Analiza el sentimiento de mercado actual sobre {ticker}
            usando las noticias y fuentes disponibles (últimos 3-5 días).

            Evalúa:
            - Tono general de las noticias recientes (positivo/negativo/neutro)
            - Catalizadores positivos relevantes (resultados, productos, partnerships)
            - Catalizadores negativos o riesgos (demandas, bajadas de rating, escándalos)
            - Red flags críticas que un inversor debería conocer

            Responde EXCLUSIVAMENTE con un objeto JSON:
            {{
                "sentimiento": "POSITIVO o NEUTRO o NEGATIVO",
                "confianza": <0-100>,
                "catalizadores_positivos": ["..."],
                "catalizadores_negativos": ["..."],
                "red_flags": ["..."],
                "noticias_clave": ["..."],
                "resumen": "resumen de 2-4 frases"
            }}
            """
        else:
            description = f"""Responde con UNA SOLA LÍNEA, SOLO este JSON:
            {{"sentimiento": "NEUTRO", "confianza": <0-100>, "catalizadores_positivos": [], "catalizadores_negativos": [], "red_flags": [], "noticias_clave": [], "resumen": "breve"}}
            Análisis de sentimiento de mercado sobre {ticker}, basado en noticias recientes.
            """

        return Task(description=description, agent=agent, expected_output="Un único objeto JSON")

    def get_sentiment(self, ticker: str) -> Optional[Dict]:
        ticker = ticker.upper().strip()
        return self.state["sentiment_analyses"].get(ticker)

    def is_sentiment_stale(self, ticker: str) -> bool:
        entry = self.get_sentiment(ticker)
        if not entry:
            return True
        ts = datetime.fromisoformat(entry["timestamp"])
        return datetime.now() - ts > timedelta(hours=SENTIMENT_CACHE_HOURS)

    def run_sentiment_analysis(self, ticker: str, force: bool = False) -> Dict:
        """
        Ejecuta (o recupera de caché) el análisis de sentimiento de un ticker.

        Requiere `agents.sentiment_agent.create_sentiment_agent`. Si el módulo
        no existe en el proyecto, devuelve un error explicativo en vez de
        romper el dashboard.
        """
        ticker = ticker.upper().strip()

        if not force:
            cached = self.get_sentiment(ticker)
            if cached:
                return cached

        logger.info(f"📰 Ejecutando análisis de sentimiento de {ticker}...")

        try:
            from agents.sentiment_agent import create_sentiment_agent
        except ImportError as e:
            error_entry = {
                "data": {
                    **NEUTRAL_SENTIMENT,
                    "resumen": (
                        "No se encontró agents/sentiment_agent.py "
                        f"(create_sentiment_agent). Error: {e}"
                    ),
                    "error": "module_not_found",
                },
                "timestamp": datetime.now().isoformat(),
            }
            # No cacheamos errores de módulo no encontrado: si el usuario
            # añade el módulo y reintenta, debe poder volver a intentarlo
            # sin "force".
            return error_entry

        analysis = None
        for attempt, strict in enumerate([False, True]):
            try:
                sentiment_agent = create_sentiment_agent()
                task = self._build_sentiment_task(sentiment_agent, ticker, strict=strict)
                crew = Crew(agents=[sentiment_agent], tasks=[task], process=Process.sequential, verbose=False)
                crew_result = crew.kickoff()
                output_str = str(crew_result.raw)
                parsed = extract_json(output_str)

                if parsed is None or parsed.get("sentimiento") is None:
                    logger.warning(f"  ⚠️ JSON inválido (intento {attempt+1}): {output_str[:200]}")
                    continue

                analysis = parsed
                break
            except Exception as e:
                logger.error(f"  ❌ Error: {e}")

        if analysis is None:
            analysis = {
                **NEUTRAL_SENTIMENT,
                "resumen": "Error al analizar (se usa sentimiento neutro por defecto)",
                "error": "Parse error",
            }

        try:
            analysis["confianza"] = max(0, min(100, float(analysis.get("confianza", 50))))
        except (TypeError, ValueError):
            analysis["confianza"] = 50

        entry = {"data": analysis, "timestamp": datetime.now().isoformat()}
        self.state["sentiment_analyses"][ticker] = entry
        self.save()
        return entry

    # ── Datos de mercado en vivo ───────────────────────────────

    def get_current_price(self, ticker: str) -> Optional[float]:
        try:
            df = yf.download(ticker, period="5d", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if len(df) == 0:
                return None
            return float(df["Close"].iloc[-1])
        except Exception as e:
            logger.warning(f"No se pudo obtener precio de {ticker}: {e}")
            return None

    def _download_history(self, ticker: str, period: str = "400d") -> Optional[pd.DataFrame]:
        try:
            df = yf.download(ticker, period=period, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df if len(df) > 0 else None
        except Exception as e:
            logger.warning(f"No se pudo descargar histórico de {ticker}: {e}")
            return None

    def get_technical(self, ticker: str) -> Dict:
        df = self._download_history(ticker)
        return TechnicalIndicators.calculate(df)

    def get_regime(self, force_refresh: bool = False) -> str:
        """
        Régimen de mercado actual (XLK), cacheado durante el día (la
        clasificación con SMA200/SMA50 apenas cambia intradía).
        """
        today = datetime.now().date().isoformat()
        cache = self.state.get("regime_cache")
        if cache and cache.get("date") == today and not force_refresh:
            return cache["regime"]

        df = self._download_history("XLK")
        if df is None or len(df) < 220:
            regime = "NEUTRAL"
        else:
            close = df["Close"]
            sma50 = close.rolling(50).mean()
            sma200 = close.rolling(200).mean()
            sma200_slope = sma200 - sma200.shift(20)

            price = float(close.iloc[-1])
            s50 = float(sma50.iloc[-1])
            s200 = float(sma200.iloc[-1])
            slope = float(sma200_slope.iloc[-1])

            macro_uptrend = slope > 0
            macro_downtrend = slope < 0
            price_above_200 = price > s200
            price_below_200 = price < s200
            sma_bullish = s50 > s200
            sma_bearish = s50 < s200

            if price_above_200 and sma_bullish and macro_uptrend:
                regime = "BULLISH"
            elif price_below_200 and sma_bearish:
                regime = "BEARISH"
            elif macro_downtrend and (price_above_200 or sma_bullish):
                regime = "BEAR_RALLY"
            else:
                regime = "NEUTRAL"

        self.state["regime_cache"] = {"regime": regime, "date": today}
        self.save()
        return regime

    # ── Resumen de cartera ─────────────────────────────────────

    def get_portfolio_summary(self) -> Dict:
        positions_value = 0.0
        position_details = []

        for ticker, lots in self.state["positions"].items():
            price = self.get_current_price(ticker)
            for lot in lots:
                qty = lot["qty"]
                entry_price = lot["entry_price"]
                cost = qty * entry_price
                value = qty * price if price else cost
                pnl = value - cost
                pnl_pct = (pnl / cost * 100) if cost > 0 else 0
                positions_value += value
                position_details.append({
                    "ticker": ticker,
                    "qty": qty,
                    "entry_price": entry_price,
                    "current_price": price,
                    "value": value,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "conviction": lot.get("conviction"),
                    "entry_date": lot.get("entry_date"),
                    "entry_regime": lot.get("entry_regime"),
                    "is_hedge": ticker == HEDGE_TICKER,
                })

        cash = self.state["cash"]
        total_value = cash + positions_value
        initial = self.state["initial_capital"]

        return {
            "cash": cash,
            "positions_value": positions_value,
            "total_value": total_value,
            "initial_capital": initial,
            "return_pct": ((total_value - initial) / initial * 100) if initial else 0.0,
            "positions": position_details,
            "trading_paused": self.state.get("trading_paused", False),
            "total_transaction_costs": self.state.get("total_transaction_costs", 0.0),
            "last_scan_at": self.state.get("last_scan_at"),
        }

    # ── Preferencias de análisis por ticker ─────────────────────

    def set_analysis_preference(self, ticker: str, daily_fundamental: bool = False, daily_sentiment: bool = False, analysis_time: str = "09:30") -> None:
        """Configura qué análisis quieres que se hagan automáticamente cada día."""
        ticker = ticker.upper().strip()
        self.state["analysis_preferences"][ticker] = {
            "daily_fundamental": daily_fundamental,
            "daily_sentiment": daily_sentiment,
            "analysis_time": analysis_time,
        }
        self.save()

    def get_analysis_preference(self, ticker: str) -> Dict:
        """Obtiene las preferencias de análisis para un ticker."""
        ticker = ticker.upper().strip()
        return self.state["analysis_preferences"].get(ticker, {
            "daily_fundamental": False,
            "daily_sentiment": False,
            "analysis_time": "09:30",
        })

    # ── Operaciones manuales (con bot_opinion) ──────────────────

    def _calculate_bot_opinion(self, ticker: str, fundamental: Optional[Dict] = None, technical: Optional[Dict] = None, sentiment: Optional[Dict] = None) -> str:
        """
        Calcula si el bot estaría de acuerdo con una operación en este momento.
        Devuelve "SÍ" o "NO".
        """
        regime = self.get_regime()
        profile = REGIME_PROFILES[regime]

        if fundamental is None:
            fundamental_entry = self.get_fundamental(ticker)
            fundamental = fundamental_entry["data"] if fundamental_entry else DEFAULT_FUNDAMENTAL
        if technical is None:
            technical = self.get_technical(ticker)
        if sentiment is None:
            sentiment_entry = self.get_sentiment(ticker)
            sentiment = sentiment_entry["data"] if sentiment_entry else NEUTRAL_SENTIMENT

        # Misma lógica que en auto_scan
        if fundamental.get("score", 0) < profile["min_fundamental_score"]:
            return "NO"

        decision = self.decision_engine.evaluate_buy_opportunity_new(ticker, fundamental, technical, sentiment)
        if decision.get("decision") != "BUY_CANDIDATE":
            return "NO"

        min_conv = profile.get("min_conviction")
        if min_conv and CONVICTION_ORDER.get(decision.get("conviction"), 0) < CONVICTION_ORDER.get(min_conv, 0):
            return "NO"

        min_score = profile.get("min_combined_score")
        if min_score and decision.get("combined_score", 0) < min_score:
            return "NO"

        return "SÍ"

    def execute_operation_manual(
        self, ticker: str, action: str, quantity: int, price: float,
        origin: str = OPERATION_ORIGIN_MANUAL_DASHBOARD, note: Optional[str] = None
    ) -> Dict:
        """
        Ejecuta una operación manual (COMPRA o VENTA).

        Args:
            ticker: El ticker (MSFT, GOOG, etc.)
            action: "BUY" o "SELL"
            quantity: Cantidad de acciones
            price: Precio (por defecto el actual, pero se puede pasar manual)
            origin: MANUAL_TELEGRAM, MANUAL_DASHBOARD, o AUTO
            note: Nota adicional (ej: "usuario solicitó manualmente")

        Returns:
            Dict con resultado de la operación
        """
        ticker = ticker.upper().strip()
        result = {"success": False, "message": "", "trade": None}

        # Obtener precio actual si no se proporciona (aunque debería proporcionarse)
        if price <= 0:
            current_price = self.get_current_price(ticker)
            if not current_price:
                result["message"] = f"No se pudo obtener precio para {ticker}"
                return result
            price = current_price

        # Validar cantidad
        if quantity <= 0:
            result["message"] = "Cantidad debe ser positiva"
            return result

        # Calcular bot_opinion en este momento
        bot_opinion = self._calculate_bot_opinion(ticker)

        # Ejecutar operación
        if action.upper() == "BUY":
            return self._execute_manual_buy(ticker, quantity, price, origin, bot_opinion, note)
        elif action.upper() == "SELL":
            return self._execute_manual_sell(ticker, quantity, price, origin, bot_opinion, note)
        else:
            result["message"] = "Acción debe ser BUY o SELL"
            return result

    def _execute_manual_buy(self, ticker: str, quantity: int, price: float, origin: str, bot_opinion: str, note: Optional[str]) -> Dict:
        """Ejecuta una compra manual."""
        result = {"success": False, "message": "", "trade": None}

        cost = quantity * price
        fee = cost * TRANSACTION_COST_PCT
        total_outflow = cost + fee

        if total_outflow > self.state["cash"]:
            result["message"] = f"Cash insuficiente. Necesitas ${total_outflow:,.2f}, tienes ${self.state['cash']:,.2f}"
            return result

        # Ejecutar compra
        self.state["cash"] -= total_outflow
        self.state["total_transaction_costs"] += fee

        regime = self.get_regime()
        self.state["positions"].setdefault(ticker, []).append({
            "qty": quantity,
            "entry_price": price,
            "entry_date": datetime.now().isoformat(),
            "conviction": "MANUAL",
            "score": 0,
            "peak_price": price,
            "entry_regime": regime,
            "entry_fee": fee,
        })

        trade = {
            "date": datetime.now().isoformat(),
            "ticker": ticker,
            "action": "BUY",
            "price": price,
            "quantity": quantity,
            "amount": cost,
            "fee": fee,
            "origin": origin,
            "bot_opinion": bot_opinion,
            "note": note,
            "regime": regime,
        }
        self.state["trade_history"].append(trade)
        self.save()

        result["success"] = True
        result["message"] = f"✅ Compra ejecutada: {quantity} {ticker} @ ${price} (bot: {bot_opinion})"
        result["trade"] = trade
        return result

    def _execute_manual_sell(self, ticker: str, quantity: int, price: float, origin: str, bot_opinion: str, note: Optional[str]) -> Dict:
        """Ejecuta una venta manual."""
        result = {"success": False, "message": "", "trade": None}

        if ticker not in self.state["positions"]:
            result["message"] = f"No tienes posición abierta en {ticker}"
            return result

        lots = self.state["positions"][ticker]
        total_qty_available = sum(lot["qty"] for lot in lots)

        if quantity > total_qty_available:
            result["message"] = f"Quieres vender {quantity}, pero solo tienes {total_qty_available}"
            return result

        # Vender lotes (FIFO)
        qty_to_sell = quantity
        lot_index = 0
        regime = self.get_regime()

        while qty_to_sell > 0 and lot_index < len(lots):
            lot = lots[lot_index]

            if lot["qty"] <= qty_to_sell:
                # Vender el lote completo
                lot_value = lot["qty"] * price
                fee = lot_value * TRANSACTION_COST_PCT
                net_inflow = lot_value - fee

                entry_cost = lot["qty"] * lot["entry_price"]
                entry_fee = lot.get("entry_fee", 0)
                pnl_net = (lot_value - entry_cost) - entry_fee - fee
                pnl_pct = ((lot_value - entry_cost) / entry_cost * 100) if entry_cost > 0 else 0

                self.state["cash"] += net_inflow
                self.state["total_transaction_costs"] += fee

                trade = {
                    "date": datetime.now().isoformat(),
                    "ticker": ticker,
                    "action": "SELL",
                    "price": price,
                    "quantity": lot["qty"],
                    "amount": lot_value,
                    "fee": fee,
                    "pnl": pnl_net,
                    "pnl_pct": pnl_pct,
                    "origin": origin,
                    "bot_opinion": bot_opinion,
                    "reason": "Manual",
                    "regime": regime,
                    "regime_at_entry": lot.get("entry_regime"),
                    "note": note,
                }
                self.state["trade_history"].append(trade)

                qty_to_sell -= lot["qty"]
                lot_index += 1
            else:
                # Vender parte del lote
                qty_partial = qty_to_sell
                lot_value = qty_partial * price
                fee = lot_value * TRANSACTION_COST_PCT
                net_inflow = lot_value - fee

                entry_cost = qty_partial * lot["entry_price"]
                entry_fee_partial = lot.get("entry_fee", 0) * (qty_partial / lot["qty"])
                pnl_net = (lot_value - entry_cost) - entry_fee_partial - fee
                pnl_pct = ((lot_value - entry_cost) / entry_cost * 100) if entry_cost > 0 else 0

                self.state["cash"] += net_inflow
                self.state["total_transaction_costs"] += fee

                trade = {
                    "date": datetime.now().isoformat(),
                    "ticker": ticker,
                    "action": "SELL",
                    "price": price,
                    "quantity": qty_partial,
                    "amount": lot_value,
                    "fee": fee,
                    "pnl": pnl_net,
                    "pnl_pct": pnl_pct,
                    "origin": origin,
                    "bot_opinion": bot_opinion,
                    "reason": "Manual",
                    "regime": regime,
                    "regime_at_entry": lot.get("entry_regime"),
                    "note": note,
                }
                self.state["trade_history"].append(trade)

                lot["qty"] -= qty_partial
                qty_to_sell = 0

        # Limpiar lotes vacíos
        self.state["positions"][ticker] = [lot for lot in lots if lot["qty"] > 0]
        if not self.state["positions"][ticker]:
            self.state["positions"].pop(ticker)

        self.save()

        result["success"] = True
        result["message"] = f"✅ Venta ejecutada: {quantity} {ticker} @ ${price} (bot: {bot_opinion})"
        result["trade"] = trade
        return result

    # ── Escaneo / trading ──────────────────────────────────────

    def scan(self, mode: str = "auto") -> Dict:
        """
        Ejecuta un ciclo de paper trading:
          1. Revisa posiciones abiertas → aplica stop loss / take profit / trailing
          2. Evalúa la watchlist → abre nuevas posiciones según el modo

        mode:
          - "auto": solo compra si hay señal técnica + fundamental/sentimiento
                    favorable (decision_engine = BUY_CANDIDATE), respetando
                    circuit breaker y cooldowns.
          - "invest_now": fuerza la entrada inmediata en los tickers de la
                    watchlist sin posición abierta, repartiendo el cash
                    disponible entre ellos a precio de mercado actual.
                    Las salidas siempre se evalúan igual.

        Returns: resumen de acciones realizadas (compras/ventas) para
        mostrar en el dashboard.
        """
        regime = self.get_regime()
        profile = REGIME_PROFILES[regime]
        actions = {"regime": regime, "buys": [], "sells": [], "skipped": [], "notes": []}

        # ── 1. Circuit breaker (drawdown) ──
        summary = self.get_portfolio_summary()
        total_value = summary["total_value"]
        peak = max(self.state.get("peak_portfolio_value", total_value), total_value)
        self.state["peak_portfolio_value"] = peak
        drawdown = (peak - total_value) / peak * 100 if peak > 0 else 0

        if not self.state["trading_paused"] and drawdown >= 15.0:
            self.state["trading_paused"] = True
            self.state["pause_started_at"] = datetime.now().isoformat()
            actions["notes"].append(f"🛑 Circuit breaker activado (drawdown {drawdown:.1f}%)")
        elif self.state["trading_paused"]:
            if drawdown <= 8.0:
                self.state["trading_paused"] = False
                self.state["pause_started_at"] = None
                actions["notes"].append("✅ Circuit breaker desactivado (drawdown recuperado)")
            else:
                paused_since = self.state.get("pause_started_at")
                if paused_since:
                    days_paused = (datetime.now() - datetime.fromisoformat(paused_since)).days
                    if days_paused >= 20:
                        self.state["trading_paused"] = False
                        self.state["pause_started_at"] = None
                        self.state["peak_portfolio_value"] = total_value
                        actions["notes"].append("⏰ Pausa máxima alcanzada → reanudando (pico reseteado)")

        # ── 2. Revisar posiciones abiertas (salidas) ──
        for ticker in list(self.state["positions"].keys()):
            price = self.get_current_price(ticker)
            if not price:
                continue

            remaining_lots = []
            for lot in self.state["positions"][ticker]:
                cost = lot["qty"] * lot["entry_price"]
                lot_value = lot["qty"] * price
                pnl = lot_value - cost
                pnl_pct = (pnl / cost * 100) if cost > 0 else 0

                lot["peak_price"] = max(lot.get("peak_price", lot["entry_price"]), price)
                drawdown_from_peak_pct = (
                    (price - lot["peak_price"]) / lot["peak_price"] * 100
                    if lot["peak_price"] > 0 else 0
                )

                is_hedge = (ticker == HEDGE_TICKER)
                if is_hedge:
                    params = HEDGE_EXIT_PARAMS
                    force_close = regime not in HEDGE_REGIMES
                else:
                    conv = lot.get("conviction", "MEDIUM")
                    params = profile["exit_high"] if conv in ("VERY_HIGH", "HIGH") else profile["exit_low"]
                    force_close = False

                sell_reason = None
                if force_close:
                    sell_reason = "Cierre Hedge (régimen ya no bajista)"
                elif pnl_pct <= params["stop_loss_pct"]:
                    sell_reason = "Stop Loss"
                elif pnl_pct >= params["take_profit_pct"]:
                    sell_reason = "Take Profit"
                elif (
                    pnl_pct >= params["trailing_trigger_pct"]
                    and drawdown_from_peak_pct <= -params["trailing_stop_pct"]
                ):
                    sell_reason = "Trailing Stop"

                if sell_reason:
                    fee = lot_value * TRANSACTION_COST_PCT
                    net_inflow = lot_value - fee
                    self.state["cash"] += net_inflow
                    self.state["total_transaction_costs"] += fee

                    entry_fee = lot.get("entry_fee", 0)
                    pnl_net = pnl - entry_fee - fee

                    trade = {
                        "date": datetime.now().isoformat(),
                        "ticker": ticker,
                        "action": "SELL",
                        "price": price,
                        "quantity": lot["qty"],
                        "amount": lot_value,
                        "fee": fee,
                        "pnl": pnl_net,
                        "pnl_pct": pnl_pct,
                        "reason": sell_reason,
                        "regime": regime,
                        "regime_at_entry": lot.get("entry_regime"),
                        "is_hedge": is_hedge,
                    }
                    self.state["trade_history"].append(trade)
                    actions["sells"].append(trade)

                    if sell_reason == "Stop Loss" and not is_hedge:
                        cooldown_until = (datetime.now() + timedelta(days=14)).isoformat()
                        self.state["stop_loss_cooldown"][ticker] = cooldown_until
                else:
                    remaining_lots.append(lot)

            if remaining_lots:
                self.state["positions"][ticker] = remaining_lots
            else:
                self.state["positions"].pop(ticker, None)

        # ── 3. Nuevas entradas ──
        watchlist = self.state["watchlist"]

        if mode == "invest_now":
            self._invest_now(watchlist, regime, profile, actions)
        else:
            self._auto_scan(watchlist, regime, profile, actions)

        # ── 4. Hedge (si aplica) ──
        self._maybe_open_hedge(regime, actions)

        self.state["last_scan_at"] = datetime.now().isoformat()
        self.save()
        return actions

    def _auto_scan(self, watchlist: List[str], regime: str, profile: Dict, actions: Dict) -> None:
        if self.state["trading_paused"]:
            actions["notes"].append("Sin compras: circuit breaker activo")
            return

        for ticker in watchlist:
            cooldown_until = self.state["stop_loss_cooldown"].get(ticker)
            if cooldown_until and datetime.now() < datetime.fromisoformat(cooldown_until):
                actions["skipped"].append({"ticker": ticker, "reason": "En cooldown tras stop loss"})
                continue

            fundamental_entry = self.get_fundamental(ticker)
            fundamental = fundamental_entry["data"] if fundamental_entry else DEFAULT_FUNDAMENTAL

            if fundamental.get("score", 0) < profile["min_fundamental_score"]:
                actions["skipped"].append({
                    "ticker": ticker,
                    "reason": f"Fundamental {fundamental.get('score')} < mínimo {profile['min_fundamental_score']} ({regime})",
                })
                continue

            technical = self.get_technical(ticker)
            sentiment_entry = self.get_sentiment(ticker)
            sentiment = sentiment_entry["data"] if sentiment_entry else NEUTRAL_SENTIMENT

            decision = self.decision_engine.evaluate_buy_opportunity_new(ticker, fundamental, technical, sentiment)

            if decision.get("decision") != "BUY_CANDIDATE":
                actions["skipped"].append({
                    "ticker": ticker,
                    "reason": decision.get("reason", "No es BUY_CANDIDATE"),
                })
                continue

            min_conv = profile.get("min_conviction")
            if min_conv and CONVICTION_ORDER.get(decision.get("conviction"), 0) < CONVICTION_ORDER.get(min_conv, 0):
                actions["skipped"].append({"ticker": ticker, "reason": f"Convicción insuficiente para {regime}"})
                continue

            min_score = profile.get("min_combined_score")
            if min_score and decision.get("combined_score", 0) < min_score:
                actions["skipped"].append({"ticker": ticker, "reason": f"Score combinado insuficiente para {regime}"})
                continue

            conviction = decision.get("conviction")
            conviction_pct = profile["conviction_pct"].get(conviction, 0.0)
            if conviction_pct <= 0:
                actions["skipped"].append({"ticker": ticker, "reason": f"conviction_pct=0 para {conviction} en {regime}"})
                continue

            price = self.get_current_price(ticker)
            if not price:
                continue

            amount_to_invest = self.state["cash"] * conviction_pct
            self._execute_buy(ticker, price, amount_to_invest, conviction, decision.get("combined_score", 0), regime, actions)

    def _invest_now(self, watchlist: List[str], regime: str, profile: Dict, actions: Dict) -> None:
        """Reparte el cash disponible entre los tickers de la watchlist
        que no tengan posición abierta, a precio de mercado actual,
        ignorando la señal técnica de entrada (pero respetando cooldowns)."""
        candidates = [
            t for t in watchlist
            if t not in self.state["positions"]
            and not (
                self.state["stop_loss_cooldown"].get(t)
                and datetime.now() < datetime.fromisoformat(self.state["stop_loss_cooldown"][t])
            )
        ]

        if not candidates:
            actions["notes"].append("Invertir ahora: no hay tickers disponibles (ya en cartera o en cooldown)")
            return

        cash_per_ticker = self.state["cash"] / len(candidates)

        for ticker in candidates:
            price = self.get_current_price(ticker)
            if not price:
                actions["skipped"].append({"ticker": ticker, "reason": "Sin precio disponible"})
                continue

            fundamental_entry = self.get_fundamental(ticker)
            fundamental = fundamental_entry["data"] if fundamental_entry else DEFAULT_FUNDAMENTAL
            technical = self.get_technical(ticker)
            sentiment_entry = self.get_sentiment(ticker)
            sentiment = sentiment_entry["data"] if sentiment_entry else NEUTRAL_SENTIMENT

            combined_score, conviction = self.decision_engine.calculate_combined_score(fundamental, technical, sentiment)

            self._execute_buy(ticker, price, cash_per_ticker, conviction, combined_score, regime, actions, note="invertir_ahora")

    def _execute_buy(
        self, ticker: str, price: float, amount_to_invest: float,
        conviction: str, combined_score: float, regime: str,
        actions: Dict, note: Optional[str] = None,
    ) -> None:
        quantity = int(amount_to_invest / price)
        if quantity <= 0:
            actions["skipped"].append({"ticker": ticker, "reason": "Cash insuficiente para 1 acción"})
            return

        cost = quantity * price
        fee = cost * TRANSACTION_COST_PCT
        total_outflow = cost + fee

        while total_outflow > self.state["cash"] and quantity > 0:
            quantity -= 1
            cost = quantity * price
            fee = cost * TRANSACTION_COST_PCT
            total_outflow = cost + fee

        if quantity <= 0 or total_outflow > self.state["cash"]:
            actions["skipped"].append({"ticker": ticker, "reason": "Cash insuficiente tras comisiones"})
            return

        self.state["cash"] -= total_outflow
        self.state["total_transaction_costs"] += fee

        self.state["positions"].setdefault(ticker, []).append({
            "qty": quantity,
            "entry_price": price,
            "entry_date": datetime.now().isoformat(),
            "conviction": conviction,
            "score": combined_score,
            "peak_price": price,
            "entry_regime": regime,
            "entry_fee": fee,
        })

        # Calcular bot_opinion para esta operación automática (siempre SÍ, porque el bot decidió comprar)
        bot_opinion = "SÍ"

        trade = {
            "date": datetime.now().isoformat(),
            "ticker": ticker,
            "action": "BUY",
            "price": price,
            "quantity": quantity,
            "amount": cost,
            "fee": fee,
            "conviction": conviction,
            "regime": regime,
            "origin": OPERATION_ORIGIN_AUTO,  # ← Marcar como automático
            "bot_opinion": bot_opinion,
            "note": note,
        }
        self.state["trade_history"].append(trade)
        actions["buys"].append(trade)

    def _maybe_open_hedge(self, regime: str, actions: Dict) -> None:
        if regime not in HEDGE_REGIMES or HEDGE_TICKER in self.state["positions"]:
            return
        if self.state["trading_paused"]:
            return

        hedge_technical = self.get_technical(HEDGE_TICKER)
        if hedge_technical.get("señal") != "ALCISTA":
            return

        price = self.get_current_price(HEDGE_TICKER)
        if not price:
            return

        amount = self.state["cash"] * HEDGE_ALLOCATION_PCT
        quantity = int(amount / price)
        if quantity <= 0:
            return

        cost = quantity * price
        fee = cost * TRANSACTION_COST_PCT
        total_outflow = cost + fee
        if total_outflow > self.state["cash"]:
            return

        self.state["cash"] -= total_outflow
        self.state["total_transaction_costs"] += fee

        self.state["positions"][HEDGE_TICKER] = [{
            "qty": quantity,
            "entry_price": price,
            "entry_date": datetime.now().isoformat(),
            "conviction": "HEDGE",
            "score": 0,
            "peak_price": price,
            "entry_regime": regime,
            "entry_fee": fee,
        }]

        trade = {
            "date": datetime.now().isoformat(),
            "ticker": HEDGE_TICKER,
            "action": "BUY",
            "price": price,
            "quantity": quantity,
            "amount": cost,
            "fee": fee,
            "conviction": "HEDGE",
            "regime": regime,
            "is_hedge": True,
        }
        self.state["trade_history"].append(trade)
        actions["buys"].append(trade)