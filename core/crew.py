import os
from dotenv import load_dotenv
load_dotenv()

import logging
import json
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import time

from crewai import Crew, Task, Process
from agents.fundamental_agent import create_fundamental_agent
from agents.technical_agent import create_technical_agent
from agents.sentiment_agent import create_sentiment_agent
from brokers.broker_manager import BrokerManager
from core.investment_decision_engine import InvestmentDecisionEngine
from core.storage import AnalysisStorage
from config import (
    AVAILABLE_SECTORS,
    SELECTED_SECTORS,
    BUY_CONVICTION_LEVELS,
    SIMULATION_MODE,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("InvestmentCrew")

# ── INSTANCIAS GLOBALES ──
broker = BrokerManager()
decision_engine = InvestmentDecisionEngine()
storage = AnalysisStorage()


def analyze_stock_new_flow(ticker: str) -> dict:
    """
    NUEVO FLUJO DE ANÁLISIS:
    
    1. FUNDAMENTAL: ¿Es buena empresa? (score >= 6 para continuar)
    2. Si NO → SKIP
    3. Si SÍ → TÉCNICO + SENTIMIENTO EN PARALELO
    4. Decisión final combinando los tres
    
    Caching: Si el stock ya está comprado, NO repite fundamental.
    """
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Analizando {ticker}")
    logger.info(f"{'='*60}")
    
    result = {
        "ticker": ticker,
        "timestamp": datetime.now().isoformat(),
        "fundamental": None,
        "technical": None,
        "sentiment": None,
        "final_decision": None,
        "error": None,
    }
    
    # ── STEP 1: ANÁLISIS FUNDAMENTAL ──
    logger.info(f"\n📊 STEP 1: Análisis Fundamental")
    
    # Check si ya está comprado (reutilizar fundamental)
    open_positions = broker.get_open_positions()
    if ticker in open_positions:
        logger.info(f"  ✓ {ticker} ya comprado - usando fundamental cacheado")
        cached_fundamental = storage.get_fundamental(ticker)
        if cached_fundamental:
            fundamental_analysis = cached_fundamental
        else:
            logger.warning(f"  ⚠️ No hay fundamental cacheado para {ticker}")
            fundamental_analysis = {"score": 6, "confidence": 50, "error": "No cached"}
    else:
        # Análisis fundamental nuevo
        try:
            logger.info(f"  → Ejecutando análisis fundamental...")
            fundamental_agent = create_fundamental_agent()
            
            task = Task(
                description=f"""Analiza los fundamentos de {ticker}:
                - Ratios: P/E, P/B, deuda/equity, liquidez, ROE
                - Crecimiento: revenue YoY, earnings growth
                - Rentabilidad: márgenes brutos, operativos, netos
                - Riesgos: Altman Z-Score, free cash flow, deuda creciente
                
                Red flags críticas que bajan rating:
                - Free cash flow negativo → -3 puntos
                - Deuda/Equity > 2.0 → -2 puntos
                - Revenue declining > 10% → -2 puntos
                - Current ratio < 1.0 → -2 puntos
                - Z-Score < 1.23 → rating máximo 4
                
                Responde en JSON:
                {{
                    "score": 0-10,
                    "confidence": 0-100,
                    "risk_level": "LOW/MEDIUM/HIGH/CRITICAL",
                    "recommendation": "BUY/HOLD/SELL/AVOID",
                    "key_metrics": {{}},
                    "red_flags": [],
                    "summary": "..."
                }}
                """,
                agent=fundamental_agent,
                expected_output="JSON con análisis fundamental",
            )
            
            crew = Crew(
                agents=[fundamental_agent],
                tasks=[task],
                process=Process.sequential,
                verbose=False,
            )
            
            crew_result = crew.kickoff()
            output_str = str(crew_result.raw)
            
            # Parse JSON
            start = output_str.find("{")
            end = output_str.rfind("}") + 1
            if start >= 0 and end > start:
                fundamental_analysis = json.loads(output_str[start:end])
                storage.save_fundamental(ticker, fundamental_analysis)
            else:
                fundamental_analysis = {"score": 5, "confidence": 30, "error": "Parse error"}
                
        except Exception as e:
            logger.error(f"  ❌ Error en fundamental: {e}")
            fundamental_analysis = {"score": 5, "confidence": 0, "error": str(e)}
    
    result["fundamental"] = fundamental_analysis
    score = fundamental_analysis.get("score", 0)
    confidence = fundamental_analysis.get("confidence", 0)
    
    logger.info(f"  ✓ Score: {score}/10 | Confidence: {confidence}%")
    
    # ── GATE 1: ¿Fundamental OK? ──
    if score < 6:
        logger.info(f"  ❌ Score {score} < 6 → SKIP (no pasa al análisis técnico/sentimiento)")
        result["final_decision"] = {
            "decision": "SKIP",
            "reason": f"Fundamental score bajo ({score}/10)",
            "score": 0,
        }
        return result
    
    logger.info(f"  ✅ Score {score} >= 6 → Continuar a análisis técnico + sentimiento")
    
    # ── STEP 2: TÉCNICO + SENTIMIENTO EN PARALELO ──
    logger.info(f"\n📈 STEP 2: Análisis Técnico + Sentimiento (en paralelo)")
    
    technical_analysis = None
    sentiment_analysis = None
    
    def run_technical():
        try:
            logger.info(f"  → Ejecutando análisis técnico...")
            technical_agent = create_technical_agent()
            
            task = Task(
                description=f"""Analiza el gráfico técnico de {ticker}:
                - Tendencia: SMA20/50/200
                - RSI (14): Sobrecompra/Sobreventa
                - MACD: Momentum
                - Bollinger Bands: Volatilidad
                - Volumen: Confirmación
                - Soportes/Resistencias: Niveles entrada/salida
                
                Señal debe tener múltiples confirmaciones (mínimo 3 de 5 indicadores):
                - Trend (SMA20 > SMA50 > SMA200 = ALCISTA)
                - RSI < 30 (oversold, potencial compra)
                - MACD bullish crossover
                - Volumen confirmando movimiento
                - Precio en soporte técnico
                
                Responde en JSON:
                {{
                    "señal": "ALCISTA/LATERAL/BAJISTA",
                    "confianza": 0-100,
                    "rsi": numero,
                    "rsi_interpretacion": "oversold/neutral/overbought",
                    "tendencia": "descripcion",
                    "entrada_sugerida": precio,
                    "stop_loss": precio,
                    "target_price": precio,
                    "reward_risk_ratio": numero,
                    "confirmaciones": {{"trend": bool, "rsi": bool, "macd": bool, "volumen": bool}},
                    "resumen": "..."
                }}
                """,
                agent=technical_agent,
                expected_output="JSON con análisis técnico",
            )
            
            crew = Crew(
                agents=[technical_agent],
                tasks=[task],
                process=Process.sequential,
                verbose=False,
            )
            
            crew_result = crew.kickoff()
            output_str = str(crew_result.raw)
            
            start = output_str.find("{")
            end = output_str.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(output_str[start:end])
            return {"señal": "LATERAL", "confianza": 0, "error": "Parse error"}
            
        except Exception as e:
            logger.error(f"  ❌ Error en técnico: {e}")
            return {"señal": "LATERAL", "confianza": 0, "error": str(e)}
    
    def run_sentiment():
        try:
            logger.info(f"  → Ejecutando análisis de sentimiento...")
            sentiment_agent = create_sentiment_agent()
            
            task = Task(
                description=f"""Analiza el sentimiento de mercado para {ticker}:
                - Noticias recientes (últimos 7 días)
                - Red flags: Lawsuits, fraud, CEO changes, bankruptcy rumors
                - Catalizadores positivos: Producto nuevo, earnings beat, adquisición
                - Regulación: Cambios a favor/en contra
                - Competencia: Nuevos competidores, pérdida de market share
                
                Red flags que bajan sentimiento:
                - Lawsuit against company
                - Accounting fraud or SEC investigation
                - CEO/CFO departure
                - Product recall or safety issues
                - Major customer loss
                
                Catalizadores positivos:
                - Producto/servicio nuevo
                - Earnings beat
                - Fusión/adquisición estratégica
                - Nuevo contrato importante
                - Cambio regulatorio a favor
                - Buyback de acciones
                
                Responde en JSON:
                {{
                    "sentimiento": "POSITIVO/NEUTRO/NEGATIVO",
                    "confianza": 0-100,
                    "catalizadores_positivos": [],
                    "catalizadores_negativos": [],
                    "red_flags": [],
                    "noticias_clave": ["..."],
                    "resumen": "..."
                }}
                """,
                agent=sentiment_agent,
                expected_output="JSON con análisis de sentimiento",
            )
            
            crew = Crew(
                agents=[sentiment_agent],
                tasks=[task],
                process=Process.sequential,
                verbose=False,
            )
            
            crew_result = crew.kickoff()
            output_str = str(crew_result.raw)
            
            start = output_str.find("{")
            end = output_str.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(output_str[start:end])
            return {"sentimiento": "NEUTRO", "confianza": 0, "error": "Parse error"}
            
        except Exception as e:
            logger.error(f"  ❌ Error en sentimiento: {e}")
            return {"sentimiento": "NEUTRO", "confianza": 0, "error": str(e)}
    
    # Ejecutar en paralelo
    with ThreadPoolExecutor(max_workers=2) as executor:
        tech_future = executor.submit(run_technical)
        sent_future = executor.submit(run_sentiment)
        
        technical_analysis = tech_future.result()
        sentiment_analysis = sent_future.result()
    
    result["technical"] = technical_analysis
    result["sentiment"] = sentiment_analysis
    
    logger.info(f"  ✓ Técnico: {technical_analysis.get('señal', '?')} ({technical_analysis.get('confianza', 0)}%)")
    logger.info(f"  ✓ Sentimiento: {sentiment_analysis.get('sentimiento', '?')} ({sentiment_analysis.get('confianza', 0)}%)")
    
    # ── STEP 3: DECISIÓN FINAL ──
    logger.info(f"\n🎯 STEP 3: Decisión Final")
    
    final_decision = decision_engine.evaluate_buy_opportunity_new(
        ticker,
        fundamental_analysis,
        technical_analysis,
        sentiment_analysis,
    )
    
    result["final_decision"] = final_decision
    
    logger.info(f"  ✓ Decision: {final_decision.get('decision', '?')}")
    logger.info(f"  ✓ Score final: {final_decision.get('combined_score', 0):.2f}")
    logger.info(f"  ✓ Conviction: {final_decision.get('conviction', '?')}")
    
    return result


def search_phase(selected_sectors: list = None) -> dict:
    """
    FASE 1: Búsqueda completa con nuevo flujo.
    - Analiza todos los stocks secuencialmente
    - Cada stock: Fundamental → si OK → Técnico + Sentimiento
    - Rankea por score final
    - Guarda top 5 para confirmar mañana
    """
    if not selected_sectors:
        selected_sectors = SELECTED_SECTORS

    logger.info(f"\n{'='*70}")
    logger.info(f"FASE 1: BÚSQUEDA COMPLETA - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    logger.info(f"Sectores: {', '.join(selected_sectors)}")
    logger.info(f"{'='*70}\n")

    # Obtener todos los stocks
    all_stocks = []
    for sector in selected_sectors:
        if sector in AVAILABLE_SECTORS:
            stocks = AVAILABLE_SECTORS[sector]
            all_stocks.extend(stocks)

    logger.info(f"📊 Analizando {len(all_stocks)} stocks...")

    candidates = []
    errors = []

    # Analizar cada stock con nuevo flujo
    for i, ticker in enumerate(all_stocks):
        try:
            logger.info(f"\n[{i+1}/{len(all_stocks)}] {ticker}")
            result = analyze_stock_new_flow(ticker)
            
            final_decision = result.get("final_decision", {})
            if final_decision.get("decision") == "BUY_CANDIDATE":
                candidates.append(final_decision)
                logger.info(f"  ✅ CANDIDATO: {final_decision.get('conviction')} (score: {final_decision.get('combined_score', 0):.2f})")
            else:
                logger.info(f"  ⊘ No es candidato: {final_decision.get('reason', 'N/A')}")

        except Exception as e:
            logger.error(f"  ❌ Error: {e}")
            errors.append({"ticker": ticker, "error": str(e)})

    # Ranking
    ranked = decision_engine.rank_candidates(candidates)
    
    logger.info(f"\n{'='*70}")
    logger.info(f"RANKING FINAL - TOP {len(ranked)} CANDIDATOS:")
    logger.info(f"{'='*70}")
    for i, candidate in enumerate(ranked, 1):
        logger.info(f"{i}. {candidate['ticker']} - Score: {candidate.get('combined_score', 0):.2f} | {candidate['conviction']}")

    # Guardar para confirmar mañana
    decision_engine.save_pending_candidates(ranked)

    return {
        "phase": "SEARCH",
        "timestamp": datetime.now().isoformat(),
        "candidates_found": len(candidates),
        "top_candidates": ranked,
        "errors": errors,
    }


def scheduled_search():
    try:
        result = search_phase(SELECTED_SECTORS)
        logger.info(f"✅ Búsqueda completada: {result['candidates_found']} candidatos")
    except Exception as e:
        logger.error(f"❌ Error en búsqueda: {e}")


def scheduled_confirm():
    try:
        pending = decision_engine.pending_candidates.get("candidates", [])
        if not pending:
            logger.warning("No hay candidatos pendientes")
            return
        
        logger.info(f"\n{'='*70}")
        logger.info(f"FASE 2a: CONFIRMACIÓN PRE-MARKET")
        logger.info(f"{'='*70}\n")
        
        logger.info(f"Reconfirmando {len(pending)} candidatos...")
        # TODO: Implementar reconfirmación
        
    except Exception as e:
        logger.error(f"❌ Error en confirmación: {e}")


def scheduled_execute():
    try:
        logger.info(f"\n{'='*70}")
        logger.info(f"FASE 3: EJECUCIÓN")
        logger.info(f"{'='*70}\n")
        # TODO: Implementar ejecución
    except Exception as e:
        logger.error(f"❌ Error en ejecución: {e}")


def scheduled_review():
    try:
        logger.info(f"\n{'='*70}")
        logger.info(f"FASE 4: REVISIÓN DE POSICIONES")
        logger.info(f"{'='*70}\n")
        # TODO: Implementar revisión
    except Exception as e:
        logger.error(f"❌ Error en revisión: {e}")