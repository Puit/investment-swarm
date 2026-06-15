"""
BACKTEST MODULE (v2 - rediseñado)
==================================

Simula operaciones sobre datos históricos del año pasado, de forma RÁPIDA y REALISTA:

- FUNDAMENTAL: 1 sola vez por ticker (vía LLM/CrewAI). Los fundamentos no cambian
  significativamente día a día, así que se calcula UNA vez y se usa como filtro fijo
  durante todo el periodo.

- TÉCNICO: Calculado MATEMÁTICAMENTE (pandas/numpy) para cada día del histórico,
  usando SOLO datos disponibles hasta esa fecha (SMA20/50/200, RSI14, MACD,
  Bollinger Bands, volumen, soporte/resistencia). Esto es instantáneo (sin LLM)
  y SÍ refleja la situación real de cada día.

- SENTIMIENTO: No hay forma práctica de obtener noticias históricas día a día,
  así que se usa un valor NEUTRO fijo. (El componente de sentimiento pesa 25%
  en la decisión combinada, así que el resultado sigue siendo representativo
  del peso de fundamental + técnico).

Comparativas al final:
- Bot vs Buy&Hold (capital repartido equitativamente entre los tickers analizados)
- Bot vs Perfect Timing (mejor compra-venta única posible por ticker, conociendo el futuro)
- Bot vs SPY (S&P 500)
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
from investment_decision_engine import InvestmentDecisionEngine
from config import AVAILABLE_SECTORS, SELECTED_SECTORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Backtest")


def extract_json(text: str) -> Optional[dict]:
    """
    Extrae el primer objeto JSON válido de un texto, con tolerancia a:

    1. Texto extra antes/después del JSON
       ("Aquí está el análisis: {...} Espero que ayude")
       → resuelto con json.JSONDecoder().raw_decode, que ignora
         "extra data" tras el valor parseado.

    2. Comas finales (trailing commas) dentro del objeto, p.ej.:
           {"a": 1, "b": {"x": 1,}, }
       Esto es MUY común en LLMs y rompe json.loads incluso a mitad
       del objeto (raw_decode no puede "saltarse" el error interno).
       → resuelto eliminando comas finales con regex antes de parsear.

    3. Objetos anidados: si el primer "{" corresponde a un sub-diccionario
       (p.ej. "key_metrics") en vez del objeto principal, prioriza el
       primer dict que contenga la clave "score".
    """

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

    # Intento 1: texto original
    result = _try_parse(text)
    if result is not None:
        return result

    # Intento 2: eliminar comas finales antes de "}" o "]" (trailing commas)
    cleaned = re.sub(r",(\s*[}\]])", r"\1", text)
    return _try_parse(cleaned)



# Sentimiento neutral fijo (no hay datos históricos de noticias día a día)
NEUTRAL_SENTIMENT = {
    "sentimiento": "NEUTRO",
    "confianza": 50,
    "catalizadores_positivos": [],
    "catalizadores_negativos": [],
    "red_flags": [],
    "noticias_clave": [],
    "resumen": "Sentimiento neutral fijo (no disponible históricamente en backtest)",
}


# ═══════════════════════════════════════════════════════════════
# INDICADORES TÉCNICOS (cálculo matemático, sin LLM)
# ═══════════════════════════════════════════════════════════════

class TechnicalIndicators:
    """
    Calcula indicadores técnicos sobre un DataFrame histórico (OHLCV)
    y devuelve un dict con el MISMO formato que el agente técnico de crew.py,
    para poder reutilizar el decision_engine sin cambios.
    """

    @staticmethod
    def calculate(df: pd.DataFrame) -> Dict:
        if df is None or len(df) < 50:
            return {"señal": "LATERAL", "confianza": 0, "error": "Datos insuficientes"}

        close = df["Close"]
        volume = df["Volume"]

        # ── Medias móviles ──
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

        # ── RSI (14) ──
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        rsi_val = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0

        # ── MACD ──
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_above = bool(macd_line.iloc[-1] > signal_line.iloc[-1])

        # ── Bollinger Bands ──
        bb_mid = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        bb_lower = (bb_mid - 2 * bb_std).iloc[-1]
        bb_upper = (bb_mid + 2 * bb_std).iloc[-1]

        # ── Volumen ──
        vol_avg20 = volume.rolling(20).mean()
        vol_ratio = (
            float(volume.iloc[-1] / vol_avg20.iloc[-1])
            if vol_avg20.iloc[-1] and vol_avg20.iloc[-1] > 0
            else 1.0
        )
        volume_confirms = vol_ratio > 1.2

        # ── Soporte / Resistencia (min/max últimos 20 días) ──
        support = float(close.tail(20).min())
        resistance = float(close.tail(20).max())

        # ── Tendencia ──
        trend_bullish = current_price > sma20_val > sma50_val
        trend_bearish = current_price < sma20_val < sma50_val
        if sma200_val:
            trend_bullish = trend_bullish and sma50_val > sma200_val
            trend_bearish = trend_bearish and sma50_val < sma200_val

        rsi_oversold = rsi_val < 35
        rsi_overbought = rsi_val > 65

        # ── Conteo de confirmaciones (multi-factor) ──
        confirmations = {
            "trend": False,
            "rsi": False,
            "macd": False,
            "volumen": volume_confirms,
        }

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

        # ── Señal final ──
        if bullish_points >= 3:
            señal = "ALCISTA"
            confianza = min(95, 50 + bullish_points * 12)
        elif bearish_points >= 3:
            señal = "BAJISTA"
            confianza = min(95, 50 + bearish_points * 12)
        else:
            señal = "LATERAL"
            confianza = 40

        # ── Entry / Stop / Target ──
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
# SIMULADOR DE BACKTEST
# ═══════════════════════════════════════════════════════════════

class BacktestSimulator:
    """
    Simula operaciones históricas del año pasado.

    Flujo:
    1. Descarga datos históricos de cada ticker (1 sola vez, con margen extra
       para poder calcular SMA200 desde el primer día del periodo).
    2. Ejecuta análisis FUNDAMENTAL vía LLM, 1 sola vez por ticker.
    3. Para cada día de trading del periodo:
       - Para tickers con fundamental >= 6: calcula técnico (matemático)
         + sentimiento neutral → decisión combinada
       - Simula compras/ventas según la decisión y las reglas de
         stop-loss / take-profit
    4. Calcula métricas finales y compara vs Buy&Hold, Perfect Timing y SPY.
    """

    def __init__(
        self,
        initial_capital: float = 5000.0,
        lookback_days: int = 365,
        tickers: Optional[List[str]] = None,
        start_date=None,
        end_date=None,
    ):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.lookback_days = lookback_days

        if start_date and end_date:
            # Periodo explícito (ej: un año concreto 2015-2026)
            self.start_date = start_date
            self.end_date = min(end_date, datetime.now().date())
        else:
            # Modo por defecto: últimos N días desde hoy
            self.end_date = datetime.now().date()
            self.start_date = self.end_date - timedelta(days=lookback_days)

        # Margen extra para poder calcular SMA200 desde el día 1 del periodo
        self.data_start_date = self.start_date - timedelta(days=400)

        self.tickers = tickers or self._default_tickers()

        self.trades: List[Dict] = []
        self.positions: Dict[str, List[Dict]] = {}
        self.daily_portfolio_values: List[Dict] = []

        self.historical_data: Dict[str, pd.DataFrame] = {}
        self.fundamental_cache: Dict[str, Dict] = {}

        self.decision_engine = InvestmentDecisionEngine()

        logger.info(f"Backtest: {self.start_date} → {self.end_date}")
        logger.info(f"Capital inicial: ${self.initial_capital:,.2f}")
        logger.info(f"Tickers: {', '.join(self.tickers)}")

    # ── Setup ──────────────────────────────────────────────────

    def _default_tickers(self) -> List[str]:
        """Toma tickers de los sectores seleccionados, sin duplicados, máx 10."""
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

        return unique[:10]

    def preload_data(self) -> None:
        """Descarga TODO el histórico necesario de una sola vez por ticker."""
        logger.info(f"\n{'='*70}")
        logger.info("DESCARGANDO DATOS HISTÓRICOS")
        logger.info(f"{'='*70}")

        for ticker in self.tickers:
            try:
                df = yf.download(
                    ticker,
                    start=self.data_start_date,
                    end=self.end_date + timedelta(days=1),
                    progress=False,
                )

                # yfinance a veces devuelve columnas MultiIndex
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                if len(df) > 0:
                    self.historical_data[ticker] = df
                    logger.info(f"  ✓ {ticker}: {len(df)} días descargados")
                else:
                    logger.warning(f"  ⚠️ {ticker}: sin datos")

            except Exception as e:
                logger.warning(f"  ❌ {ticker}: {e}")

    def _build_fundamental_task(self, agent, ticker: str, strict: bool = False) -> Task:
        """
        Construye la Task de análisis fundamental.

        - strict=False: prompt normal, schema simple (sin key_metrics/red_flags
          anidados, que son los que más rompen el JSON con comillas internas
          y no se usan en la decisión final).
        - strict=True: prompt de reintento, ultra-mínimo, una sola línea,
          para casos donde el primer intento no produjo JSON válido.
        """
        if not strict:
            description = f"""Analiza los fundamentos de {ticker}:
            - Ratios: P/E, P/B, deuda/equity, liquidez, ROE
            - Crecimiento: revenue YoY, earnings growth
            - Rentabilidad: márgenes brutos, operativos, netos
            - Riesgos: Altman Z-Score, free cash flow, deuda creciente

            Penalizaciones (resta del rating, mínimo 0):
            - Free cash flow negativo → -3 puntos
            - Deuda/Equity > 2.0 → -2 puntos
            - Revenue declining > 10% → -2 puntos
            - Current ratio < 1.0 → -2 puntos
            - Z-Score < 1.23 → rating máximo 4

            Responde EXCLUSIVAMENTE con un objeto JSON (sin texto antes ni
            después, sin comentarios). No incluyas comillas dobles dentro
            de los valores de texto (usa comillas simples si necesitas citar).

            Formato exacto:
            {{
                "score": <numero entre 0 y 10>,
                "confidence": <numero entre 0 y 100>,
                "risk_level": "LOW o MEDIUM o HIGH o CRITICAL",
                "recommendation": "BUY o HOLD o SELL o AVOID",
                "summary": "breve resumen de 1-2 frases sin comillas dobles"
            }}
            """
        else:
            description = f"""Tu respuesta anterior sobre {ticker} no era JSON
            válido. Responde AHORA con UNA SOLA LÍNEA, SOLO el siguiente JSON,
            sin texto adicional, sin saltos de línea, sin comillas dobles
            dentro de los valores:

            {{"score": <0-10>, "confidence": <0-100>, "risk_level": "LOW", "recommendation": "BUY", "summary": "breve"}}

            Sustituye los valores por tu análisis fundamental real de {ticker}
            (ratios, crecimiento, riesgos), pero el FORMATO debe ser
            EXACTAMENTE ese objeto JSON de una línea, nada más.
            """

        return Task(
            description=description,
            agent=agent,
            expected_output="Un único objeto JSON, sin texto adicional",
        )

    def run_fundamental_analysis(self) -> None:
        """Ejecuta el análisis fundamental UNA vez por ticker (vía LLM)."""
        logger.info(f"\n{'='*70}")
        logger.info("ANÁLISIS FUNDAMENTAL (1 vez por ticker)")
        logger.info(f"{'='*70}\n")

        for ticker in self.tickers:
            if ticker not in self.historical_data:
                continue

            analysis = None

            for attempt, strict in enumerate([False, True]):
                try:
                    if attempt == 0:
                        logger.info(f"  → Analizando fundamentos de {ticker}...")
                    else:
                        logger.info(f"    ↻ Reintentando {ticker} con prompt estricto...")

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

                    if parsed is None:
                        logger.warning(f"    ⚠️ No se pudo parsear JSON. Output: {output_str[:300]}")
                        continue

                    if parsed.get("score") is None:
                        logger.warning(f"    ⚠️ JSON sin 'score'. Output: {output_str[:300]}")
                        continue

                    analysis = parsed
                    break  # éxito, no hace falta reintentar

                except Exception as e:
                    logger.error(f"    ❌ Error: {e}")

            if analysis is None:
                # Ambos intentos fallaron → fallback neutral con baja confianza
                analysis = {"score": 5, "confidence": 30, "error": "Parse error (2 intentos)"}

            # ── Clamping: el LLM a veces se pasa de los límites del rango ──
            try:
                analysis["score"] = max(0, min(10, float(analysis.get("score", 5))))
            except (TypeError, ValueError):
                analysis["score"] = 5

            try:
                analysis["confidence"] = max(0, min(100, float(analysis.get("confidence", 30))))
            except (TypeError, ValueError):
                analysis["confidence"] = 30

            self.fundamental_cache[ticker] = analysis
            logger.info(
                f"    Score: {analysis.get('score', '?')}/10 | "
                f"Confidence: {analysis.get('confidence', '?')}%"
            )


    # ── Acceso a datos históricos ────────────────────────────────

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
        """Calendario de días de trading dentro del periodo (basado en datos reales)."""
        all_dates = set()
        for df in self.historical_data.values():
            dates = df.index.date
            for d in dates:
                if self.start_date <= d <= self.end_date:
                    all_dates.add(d)
        return sorted(all_dates)

    # ── Análisis diario (sin LLM) ────────────────────────────────

    def analyze_day(self, analysis_date) -> Dict:
        """
        Para cada ticker con fundamental OK (>=5):
        - Calcula técnico matemáticamente con datos hasta `analysis_date`
        - Combina con sentimiento neutral
        - Evalúa con el decision_engine (mismo que producción)

        NOTA: el gate se baja a >=5 (en vez de >=6) porque score=5 es el
        valor neutral de fallback cuando el LLM no devuelve JSON parseable.
        En vez de descartar esos tickers por completo, se les deja pasar
        con baja confianza (50%) — el decision_engine ya pondera la
        confianza fundamental al 40%, así que un score=5/confianza=30%
        difícilmente generará BUY_CANDIDATE salvo que técnico+sentimiento
        sean muy fuertes.
        """
        candidates = []

        for ticker in self.tickers:
            fundamental = self.fundamental_cache.get(ticker)
            if not fundamental or fundamental.get("score", 0) < 5:
                continue

            df = self._df_until(ticker, analysis_date)
            if df is None or len(df) < 50:
                continue

            technical = TechnicalIndicators.calculate(df)
            sentiment = NEUTRAL_SENTIMENT

            decision = self.decision_engine.evaluate_buy_opportunity_new(
                ticker, fundamental, technical, sentiment
            )

            if decision.get("decision") == "BUY_CANDIDATE":
                candidates.append(decision)

        return {"candidates": candidates}

    # ── Simulación de un día de trading ──────────────────────────

    @staticmethod
    def _exit_params(conviction: str) -> Dict:
        """
        Parámetros de salida según convicción (Swing + Position Hybrid):

        - VERY_HIGH/HIGH → estilo "position": objetivo más ambicioso (+50%),
          trailing stop se activa tras +15% de ganancia y vende si cae
          10% desde el máximo alcanzado (deja correr ganadores).
        - MEDIUM/LOW → estilo "swing": objetivo +25%, trailing se activa
          antes (+10%) con margen menor (-8%).

        Stop loss siempre activo desde el día 1 (protección de capital).
        """
        if conviction in ("VERY_HIGH", "HIGH"):
            return {
                "stop_loss_pct": -12,
                "take_profit_pct": 50,
                "trailing_trigger_pct": 15,
                "trailing_stop_pct": 10,
            }
        return {
            "stop_loss_pct": -10,
            "take_profit_pct": 25,
            "trailing_trigger_pct": 10,
            "trailing_stop_pct": 8,
        }

    def simulate_day(self, analysis_date, daily_analysis: Dict) -> None:
        # ── Compras ──
        for candidate in daily_analysis.get("candidates", []):
            ticker = candidate.get("ticker")
            conviction = candidate.get("conviction")
            score = candidate.get("combined_score", 0)

            price = self.get_price_at_date(ticker, analysis_date)
            if not price:
                continue

            # Más capital desplegado: convicciones altas usan porciones
            # mayores para aprovechar mejor las tendencias del mercado.
            conviction_pct = {
                "VERY_HIGH": 0.60,
                "HIGH": 0.25,
                "MEDIUM": 0.10,
                "LOW": 0.05,
            }.get(conviction, 0.05)

            amount_to_invest = self.current_capital * conviction_pct
            quantity = int(amount_to_invest / price)

            if quantity > 0 and (quantity * price) <= self.current_capital:
                cost = quantity * price
                self.current_capital -= cost

                self.positions.setdefault(ticker, []).append({
                    "qty": quantity,
                    "entry_price": price,
                    "entry_date": analysis_date,
                    "conviction": conviction,
                    "score": score,
                    "peak_price": price,
                })

                self.trades.append({
                    "date": analysis_date,
                    "ticker": ticker,
                    "action": "BUY",
                    "price": price,
                    "quantity": quantity,
                    "amount": cost,
                    "conviction": conviction,
                })

        # ── Revisión de posiciones abiertas (stop loss / take profit / trailing) ──
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

                # Actualizar máximo alcanzado (para trailing stop)
                lot["peak_price"] = max(lot.get("peak_price", lot["entry_price"]), current_price)
                drawdown_from_peak_pct = (
                    (current_price - lot["peak_price"]) / lot["peak_price"] * 100
                    if lot["peak_price"] > 0 else 0
                )

                params = self._exit_params(lot.get("conviction", "MEDIUM"))

                sell_reason = None
                if pnl_pct <= params["stop_loss_pct"]:
                    sell_reason = "Stop Loss"
                elif pnl_pct >= params["take_profit_pct"]:
                    sell_reason = "Take Profit (objetivo)"
                elif (
                    pnl_pct >= params["trailing_trigger_pct"]
                    and drawdown_from_peak_pct <= -params["trailing_stop_pct"]
                ):
                    sell_reason = "Trailing Stop"

                if sell_reason:
                    self.current_capital += lot_value
                    self.trades.append({
                        "date": analysis_date,
                        "ticker": ticker,
                        "action": "SELL",
                        "price": current_price,
                        "quantity": lot["qty"],
                        "amount": lot_value,
                        "pnl": pnl,
                        "pnl_pct": pnl_pct,
                        "reason": sell_reason,
                    })
                else:
                    remaining_lots.append(lot)

            if remaining_lots:
                self.positions[ticker] = remaining_lots
            else:
                del self.positions[ticker]


        # ── Valor total del portfolio ──
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
        })

    # ── Orquestación ──────────────────────────────────────────────

    def run_backtest(self) -> Dict:
        logger.info(f"\n{'='*70}")
        logger.info(f"INICIANDO BACKTEST: {self.start_date} → {self.end_date}")
        logger.info(f"{'='*70}\n")

        self.preload_data()

        if not self.historical_data:
            return {"error": "No se pudieron descargar datos históricos"}

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
                    f"Portfolio: ${last['total_value']:,.2f} "
                    f"({last['return_pct']:+.2f}%)"
                )

        return self.calculate_metrics()

    # ── Métricas y comparativas ──────────────────────────────────

    def calculate_metrics(self) -> Dict:
        if not self.daily_portfolio_values:
            return {"error": "No data"}

        initial_value = self.initial_capital
        final_value = self.daily_portfolio_values[-1]["total_value"]
        total_return_pct = ((final_value - initial_value) / initial_value) * 100

        # Max drawdown
        peak = initial_value
        max_drawdown = 0.0
        for day in self.daily_portfolio_values:
            value = day["total_value"]
            if value > peak:
                peak = value
            drawdown = ((peak - value) / peak) * 100
            max_drawdown = max(max_drawdown, drawdown)

        # Sharpe ratio (sobre returns diarios)
        values = [d["total_value"] for d in self.daily_portfolio_values]
        daily_returns = pd.Series(values).pct_change().dropna()
        if len(daily_returns) > 1 and daily_returns.std() > 0:
            sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * (252 ** 0.5)
        else:
            sharpe_ratio = 0.0

        # Win rate
        sell_trades = [t for t in self.trades if t["action"] == "SELL"]
        winning_trades = len([t for t in sell_trades if t.get("pnl", 0) > 0])
        win_rate = (winning_trades / len(sell_trades) * 100) if sell_trades else 0.0

        # Comparativas
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
            },
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
        """
        Si se hubiera repartido el capital inicial equitativamente entre
        TODOS los tickers analizados al inicio del periodo y se hubiera
        mantenido (hold) hasta el final.
        """
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
        """
        Máximo return teórico POSIBLE: para cada ticker, la mejor operación
        única de compra-venta posible conociendo todo el futuro
        (clásico "best time to buy/sell stock"). Capital repartido
        equitativamente entre tickers.
        """
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
        """Return del S&P 500 (SPY) durante el mismo periodo, como referencia general."""
        try:
            spy = yf.download(
                "SPY", start=self.start_date, end=self.end_date + timedelta(days=1), progress=False
            )
            if isinstance(spy.columns, pd.MultiIndex):
                spy.columns = spy.columns.get_level_values(0)

            if len(spy) >= 2:
                start_price = float(spy["Close"].iloc[0])
                end_price = float(spy["Close"].iloc[-1])
                return ((end_price - start_price) / start_price) * 100
        except Exception as e:
            logger.warning(f"No se pudo calcular SPY: {e}")

        return 0.0

    # ── Reporte ──────────────────────────────────────────────────

    def print_report(self, metrics: Dict) -> None:
        if "error" in metrics:
            logger.error(f"Error en backtest: {metrics['error']}")
            return

        logger.info(f"\n{'='*70}")
        logger.info("REPORTE DE BACKTEST")
        logger.info(f"{'='*70}\n")

        period = metrics["backtest_period"]
        logger.info(f"📅 Período: {period['start']} → {period['end']}")
        logger.info(f"   ({period['trading_days']} días de trading)")
        logger.info(f"   Tickers: {', '.join(period['tickers'])}\n")

        logger.info("📊 SCORES FUNDAMENTALES (fijos para todo el periodo):")
        for ticker, score in metrics["fundamental_scores"].items():
            estado = "✅ analizado" if score is not None and score >= 6 else "⊘ filtrado (<6)"
            logger.info(f"   {ticker}: {score}/10  {estado}")

        perf = metrics["performance"]
        logger.info(f"\n💰 RENDIMIENTO DEL BOT:")
        logger.info(f"   Capital inicial:  ${perf['initial_capital']:,.2f}")
        logger.info(f"   Capital final:    ${perf['final_value']:,.2f}")
        logger.info(f"   Return Total:     {perf['total_return_pct']:+.2f}%")
        logger.info(f"   Max Drawdown:     -{perf['max_drawdown_pct']:.2f}%")
        logger.info(f"   Sharpe Ratio:     {perf['sharpe_ratio']:.2f}")

        trading = metrics["trading"]
        logger.info(f"\n📈 ACTIVIDAD DE TRADING:")
        logger.info(f"   Compras:             {trading['total_buys']}")
        logger.info(f"   Ventas:              {trading['total_sells']}")
        logger.info(f"   Posiciones abiertas: {trading['open_positions']}")
        logger.info(f"   Win Rate:            {trading['win_rate_pct']:.2f}%")

        comp = metrics["comparison"]
        logger.info(f"\n🏁 COMPARACIÓN:")
        logger.info(f"   Bot (estrategia):        {comp['bot_return_pct']:>8.2f}%")
        logger.info(f"   Buy & Hold (tus tickers):{comp['buyhold_return_pct']:>8.2f}%")
        logger.info(f"   SPY (S&P 500):           {comp['spy_return_pct']:>8.2f}%")
        logger.info(f"   Perfect Timing (máximo): {comp['perfect_timing_return_pct']:>8.2f}%")
        logger.info(f"\n   Bot vs Buy&Hold:   {comp['bot_vs_buyhold_diff']:+.2f} pp")
        logger.info(f"   Bot vs SPY:        {comp['bot_vs_spy_diff']:+.2f} pp")
        logger.info(f"   Gap vs Perfect:    {comp['bot_vs_perfect_diff']:+.2f} pp (margen de mejora)")

        logger.info(f"\n{'='*70}\n")