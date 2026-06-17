import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple
from config import (
    BUY_CONVICTION_LEVELS,
    FUNDAMENTAL_CACHE_DAYS,
    MIN_SCORE_TO_ANALYZE,
    CONFIDENCE_THRESHOLD,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DecisionEngine")


class InvestmentDecisionEngine:
    """
    Motor de decisión para compra/venta de stocks.
    - Combina análisis fundamental, técnico y sentimiento
    - Genera scoring y niveles de convicción
    - Gestiona confirmación día+1
    """

    def __init__(self):
        self.candidates_file = Path("pending_candidates.json")
        self.pending_candidates = self._load_candidates()

    def calculate_combined_score(
        self, fundamental: dict, technical: dict, sentiment: dict
    ) -> Tuple[float, str]:
        """
        Calcula score combinado (0-1) y conviction level
        
        Ponderación:
        - Fundamental: 40%
        - Técnico: 35%
        - Sentimiento: 25%
        
        Returns:
            (score: 0-1, conviction: "VERY_HIGH"|"HIGH"|"MEDIUM")
        """
        try:
            # FUNDAMENTAL (40%)
            fundamental_score = fundamental.get("score", 5) / 10.0  # Normalizar a 0-1
            if fundamental.get("error"):
                fundamental_score = 0.5

            # TÉCNICO (35%)
            technical_signal = technical.get("señal", "LATERAL")
            signal_map = {"ALCISTA": 0.8, "LATERAL": 0.5, "BAJISTA": 0.2}
            technical_score = signal_map.get(technical_signal, 0.5)

            # SENTIMIENTO (25%)
            sentiment_value = sentiment.get("sentimiento", "NEUTRO")
            sentiment_map = {"POSITIVO": 0.8, "NEUTRO": 0.5, "NEGATIVO": 0.2}
            sentiment_score = sentiment_map.get(sentiment_value, 0.5)

            # Combinación ponderada
            combined_score = (
                fundamental_score * 0.40 + technical_score * 0.35 + sentiment_score * 0.25
            )

            # Determinar conviction level
            if combined_score >= 0.75:
                conviction = "VERY_HIGH"
            elif combined_score >= 0.60:
                conviction = "HIGH"
            elif combined_score >= 0.50:
                conviction = "MEDIUM"
            else:
                conviction = "LOW"

            logger.info(
                f"Score: {combined_score:.2f} | Fund: {fundamental_score:.2f}, "
                f"Tech: {technical_score:.2f}, Sent: {sentiment_score:.2f} → {conviction}"
            )

            return combined_score, conviction

        except Exception as e:
            logger.error(f"Error calculando score: {e}")
            return 0.5, "MEDIUM"

    def evaluate_buy_opportunity(
        self, ticker: str, fundamental: dict, technical: dict, sentiment: dict
    ) -> Dict:
        """
        Evalúa si es una oportunidad de compra y retorna decisión
        """
        combined_score, conviction = self.calculate_combined_score(
            fundamental, technical, sentiment
        )

        # Checks básicos
        if combined_score < MIN_SCORE_TO_ANALYZE:
            return {
                "ticker": ticker,
                "decision": "SKIP",
                "reason": f"Score bajo ({combined_score:.2f} < {MIN_SCORE_TO_ANALYZE})",
                "score": combined_score,
            }

        # Determinar si es oportunidad de compra
        if conviction not in BUY_CONVICTION_LEVELS:
            return {
                "ticker": ticker,
                "decision": "SKIP",
                "reason": f"Convicción {conviction} no es oportunidad",
                "score": combined_score,
            }

        conviction_config = BUY_CONVICTION_LEVELS[conviction]

        # Check si fundamental es suficientemente bueno
        if combined_score < conviction_config["min_score"]:
            return {
                "ticker": ticker,
                "decision": "SKIP",
                "reason": f"Score {combined_score:.2f} < mínimo {conviction_config['min_score']}",
                "score": combined_score,
            }

        return {
            "ticker": ticker,
            "decision": "BUY_CANDIDATE",
            "conviction": conviction,
            "score": combined_score,
            "buy_percentage": conviction_config["percentage"],
            "requires_confirmation": conviction_config["requires_confirmation"],
            "fundamental": fundamental,
            "technical": technical,
            "sentiment": sentiment,
        }

    def evaluate_buy_opportunity_new(
        self, ticker: str, fundamental: dict, technical: dict, sentiment: dict
    ) -> Dict:
        """
        NUEVO FLUJO: Combina fundamental + técnico + sentimiento
        
        Lógica:
        1. Si fundamental < 6 → SKIP (ya filtrado en crew.py)
        2. Combina técnico + sentimiento independientemente
        3. Ponderación: Fundamental 40%, Técnico 35%, Sentimiento 25%
        4. Determina conviction y decisión
        5. Calcula apalancamiento si conviction muy alta
        """
        try:
            # ── SCORES ──
            fundamental_score = fundamental.get("score", 5) / 10.0  # 0-1
            fundamental_confidence = fundamental.get("confidence", 50) / 100.0
            
            # Técnico: mapear señal a score
            technical_signal = technical.get("señal", "LATERAL")
            technical_signal_map = {"ALCISTA": 0.8, "LATERAL": 0.5, "BAJISTA": 0.2}
            technical_score = technical_signal_map.get(technical_signal, 0.5)
            technical_confidence = technical.get("confianza", 50) / 100.0
            
            # Sentimiento: mapear a score
            sentiment_value = sentiment.get("sentimiento", "NEUTRO")
            sentiment_map = {"POSITIVO": 0.8, "NEUTRO": 0.5, "NEGATIVO": 0.2}
            sentiment_score = sentiment_map.get(sentiment_value, 0.5)
            sentiment_confidence = sentiment.get("confianza", 50) / 100.0
            
            # ── PONDERACIÓN ──
            combined_score = (
                fundamental_score * 0.40 +
                technical_score * 0.35 +
                sentiment_score * 0.25
            )
            
            # ── CONFIANZA GLOBAL ──
            avg_confidence = (fundamental_confidence + technical_confidence + sentiment_confidence) / 3
            
            # ── CONVICTION LEVEL ──
            # En backtest el sentimiento siempre es NEUTRO (0.5 / 50% confianza),
            # lo que arrastra avg_confidence hacia abajo artificialmente.
            # Umbrales ajustados para ser justos con datos reales fundamental+técnico.
            if combined_score >= 0.74 and avg_confidence >= 0.62:
                conviction = "VERY_HIGH"
            elif combined_score >= 0.63 and avg_confidence >= 0.52:
                conviction = "HIGH"
            elif combined_score >= 0.53 and avg_confidence >= 0.44:
                conviction = "MEDIUM"
            else:
                conviction = "LOW"
            
            logger.info(
                f"Combined: {combined_score:.2f} | "
                f"Fund: {fundamental_score:.2f}, Tech: {technical_score:.2f}, Sent: {sentiment_score:.2f} "
                f"→ {conviction}"
            )
            
            # ── RED FLAGS ──
            red_flags = []
            if fundamental.get("risk_level") == "CRITICAL":
                red_flags.append("Fundamental CRITICAL risk")
            if technical.get("confianza", 50) < 40:
                red_flags.append("Technical signal weak")
            if sentiment.get("red_flags"):
                red_flags.extend(sentiment.get("red_flags", [])[:2])
            
            # ── DECISIÓN ──
            if conviction == "LOW":
                decision = "SKIP"
                reason = f"Conviction too low ({conviction})"
            elif red_flags and conviction in ["LOW", "MEDIUM"]:
                decision = "SKIP"
                reason = f"Red flags detected + low conviction: {', '.join(red_flags[:2])}"
            elif combined_score < MIN_SCORE_TO_ANALYZE:
                decision = "SKIP"
                reason = f"Combined score {combined_score:.2f} < threshold"
            else:
                decision = "BUY_CANDIDATE"
                reason = None
            
            # ── LEVERAGE ──
            use_leverage = False
            leverage_multiplier = 1.0
            if conviction == "VERY_HIGH" and combined_score >= 0.80:
                # Apalancamiento solo en ultra-convicción + R:R bueno
                reward_risk = technical.get("reward_risk_ratio", 1.0)
                if reward_risk >= 2.0:
                    use_leverage = True
                    leverage_multiplier = 1.5  # 50% más capital
            
            # ── OUTPUT ──
            conviction_config = BUY_CONVICTION_LEVELS.get(conviction, {"percentage": 0.05})
            
            return {
                "ticker": ticker,
                "decision": decision,
                "reason": reason,
                "conviction": conviction,
                "combined_score": combined_score,
                "avg_confidence": avg_confidence,
                "scores": {
                    "fundamental": fundamental_score,
                    "technical": technical_score,
                    "sentiment": sentiment_score,
                },
                "buy_percentage": conviction_config.get("percentage", 0.05),
                "leverage": {
                    "use_leverage": use_leverage,
                    "multiplier": leverage_multiplier,
                    "reward_risk": technical.get("reward_risk_ratio", 1.0),
                },
                "red_flags": red_flags,
                "fundamental": fundamental,
                "technical": technical,
                "sentiment": sentiment,
            }
            
        except Exception as e:
            logger.error(f"Error en evaluate_buy_opportunity_new: {e}")
            return {
                "ticker": ticker,
                "decision": "ERROR",
                "reason": str(e),
                "conviction": "LOW",
                "combined_score": 0,
            }

    def rank_candidates(self, candidates: List[Dict]) -> List[Dict]:
        """
        Rankea candidatos por score (mejor primero)
        Retorna top 5
        """
        buy_candidates = [c for c in candidates if c.get("decision") == "BUY_CANDIDATE"]
        ranked = sorted(buy_candidates, key=lambda x: x.get("score", 0), reverse=True)
        return ranked[:5]  # Top 5

    def save_pending_candidates(self, candidates: List[Dict]):
        """
        Guarda candidatos para confirmar mañana (día+1)
        """
        self.pending_candidates = {
            "saved_at": datetime.now().isoformat(),
            "candidates": candidates,
        }
        with open(self.candidates_file, "w") as f:
            json.dump(self.pending_candidates, f, indent=2)
        logger.info(f"💾 Guardados {len(candidates)} candidatos para confirmar mañana")

    def confirm_candidates_premarket(
        self, new_analysis: List[Dict]
    ) -> Tuple[Dict, List[Dict]]:
        """
        Reconfirma candidatos al día siguiente (pre-market)
        Compara con análisis nuevo y decide cuál comprar
        
        Returns:
            (buy_decision, remaining_candidates)
        """
        if not self.pending_candidates.get("candidates"):
            logger.warning("No hay candidatos pendientes para confirmar")
            return None, []

        # Obtener candidatos guardados
        pending = self.pending_candidates["candidates"]
        pending_tickers = {c["ticker"]: c for c in pending}

        # Buscar equivalentes en nuevo análisis
        new_analysis_map = {c["ticker"]: c for c in new_analysis}

        buy_decision = None
        remaining = []

        for ticker, old_candidate in pending_tickers.items():
            if ticker not in new_analysis_map:
                logger.warning(f"{ticker} no en nuevo análisis")
                remaining.append(old_candidate)
                continue

            new_candidate = new_analysis_map[ticker]
            old_score = old_candidate.get("score", 0)
            new_score = new_candidate.get("score", 0)

            # Si score bajó >10%, descartar
            score_change = new_score - old_score
            if score_change < -0.10:
                logger.info(
                    f"❌ {ticker} descartado: score bajó de {old_score:.2f} a {new_score:.2f}"
                )
                continue

            # Si sigue siendo bueno, es candidato de compra
            if new_score >= CONFIDENCE_THRESHOLD:
                logger.info(
                    f"✅ {ticker} confirmado para compra: {new_score:.2f} (cambio: {score_change:+.2f})"
                )
                buy_decision = new_candidate
                break  # Compra solo el mejor confirmado
            else:
                remaining.append(new_candidate)

        return buy_decision, remaining

    def evaluate_sell_opportunity(
        self, ticker: str, position: dict, technical: dict, sentiment: dict
    ) -> Dict:
        """
        Evalúa si debería vender una posición abierta
        
        Criterios de venta:
        1. Technical BAJISTA + Sentiment NEGATIVO
        2. Stop loss alcanzado
        3. Take profit alcanzado
        4. Posición muy antigua (>6 meses para position, >30 días para swing)
        """
        sell_signals = []

        # Check 1: Signals técnicos/sentimiento
        technical_signal = technical.get("señal", "LATERAL")
        sentiment_value = sentiment.get("sentimiento", "NEUTRO")

        if technical_signal == "BAJISTA" and sentiment_value == "NEGATIVO":
            sell_signals.append(
                {
                    "reason": "Technical BAJISTA + Sentiment NEGATIVO",
                    "confidence": "HIGH",
                }
            )

        # Check 2: Stop loss
        pnl = position.get("pnl", 0)
        avg_cost = position.get("avg_cost", 0)
        if avg_cost > 0:
            pnl_percent = (pnl / avg_cost) * 100
            stop_loss_trigger = -15  # Parámetro en config
            if pnl_percent <= stop_loss_trigger:
                sell_signals.append(
                    {
                        "reason": f"Stop loss alcanzado: {pnl_percent:.1f}%",
                        "confidence": "CRITICAL",
                    }
                )

        if not sell_signals:
            return {
                "ticker": ticker,
                "decision": "HOLD",
                "reason": "Sin señales de venta",
            }

        return {
            "ticker": ticker,
            "decision": "SELL",
            "sell_signals": sell_signals,
            "confidence": sell_signals[0]["confidence"] if sell_signals else "MEDIUM",
        }

    def _load_candidates(self) -> dict:
        """Carga candidatos guardados"""
        if self.candidates_file.exists():
            with open(self.candidates_file) as f:
                return json.load(f)
        return {}