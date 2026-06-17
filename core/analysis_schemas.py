"""
ANALYSIS SCHEMAS - Formato estandarizado de JSONs devueltos por agentes

Define exactamente qué estructura JSON espera cada agente de análisis.
Facilita parsing consistente y manejo de errores robusto.
"""

from typing import Dict, Any, Optional, Literal
from dataclasses import dataclass, asdict
import json

# ═══════════════════════════════════════════════════════════════
# FUNDAMENTAL ANALYSIS SCHEMA
# ═══════════════════════════════════════════════════════════════

@dataclass
class FundamentalAnalysis:
    """Schema para análisis fundamental"""
    score: int  # 0-10
    confidence: int  # 0-100
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    recommendation: Literal["BUY", "HOLD", "SELL", "AVOID"]
    summary: str
    ratios: Optional[Dict[str, float]] = None  # P/E, P/B, etc
    growth_metrics: Optional[Dict[str, float]] = None  # YoY growth, etc
    red_flags: Optional[list] = None  # Lista de problemas encontrados

    def to_json(self) -> str:
        """Convierte a JSON para enviar al agente"""
        return json.dumps(asdict(self), ensure_ascii=False)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'FundamentalAnalysis':
        """Crea desde diccionario, rellenando valores por defecto"""
        return FundamentalAnalysis(
            score=int(data.get('score', 5)),
            confidence=int(data.get('confidence', 50)),
            risk_level=data.get('risk_level', 'MEDIUM').upper(),
            recommendation=data.get('recommendation', 'HOLD').upper(),
            summary=str(data.get('summary', 'No hay información')),
            ratios=data.get('ratios', None),
            growth_metrics=data.get('growth_metrics', None),
            red_flags=data.get('red_flags', None),
        )


# ═══════════════════════════════════════════════════════════════
# SENTIMENT ANALYSIS SCHEMA
# ═══════════════════════════════════════════════════════════════

@dataclass
class SentimentAnalysis:
    """Schema para análisis de sentimiento"""
    sentiment: Literal["POSITIVO", "NEUTRO", "NEGATIVO"]
    confidence: int  # 0-100
    score: int  # -10 a +10 (negativo = bajista, positivo = alcista)
    catalysts: list  # Lista de catalizadores identificados
    summary: str
    sources: Optional[list] = None  # Fuentes del análisis

    def to_json(self) -> str:
        """Convierte a JSON para enviar al agente"""
        return json.dumps(asdict(self), ensure_ascii=False)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'SentimentAnalysis':
        """Crea desde diccionario, rellenando valores por defecto"""
        return SentimentAnalysis(
            sentiment=data.get('sentiment', 'NEUTRO').upper(),
            confidence=int(data.get('confidence', 50)),
            score=int(data.get('score', 0)),
            catalysts=data.get('catalysts', []) if isinstance(data.get('catalysts'), list) else [],
            summary=str(data.get('summary', 'No hay información')),
            sources=data.get('sources', None),
        )


# ═══════════════════════════════════════════════════════════════
# TECHNICAL ANALYSIS SCHEMA
# ═══════════════════════════════════════════════════════════════

@dataclass
class TechnicalAnalysis:
    """Schema para análisis técnico"""
    signal: Literal["BUY", "HOLD", "SELL"]
    confidence: int  # 0-100
    score: int  # 0-10 (0=muy bajista, 10=muy alcista, 5=neutro)
    support: float  # Nivel de soporte
    resistance: float  # Nivel de resistencia
    summary: str
    indicators: Optional[Dict[str, Any]] = None  # SMA, RSI, MACD, etc
    trend: Optional[str] = None  # "UPTREND", "DOWNTREND", "SIDEWAYS"

    def to_json(self) -> str:
        """Convierte a JSON para enviar al agente"""
        return json.dumps(asdict(self), ensure_ascii=False)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'TechnicalAnalysis':
        """Crea desde diccionario, rellenando valores por defecto"""
        return TechnicalAnalysis(
            signal=data.get('signal', 'HOLD').upper(),
            confidence=int(data.get('confidence', 50)),
            score=int(data.get('score', 5)),
            support=float(data.get('support', 0)),
            resistance=float(data.get('resistance', 0)),
            summary=str(data.get('summary', 'No hay información')),
            indicators=data.get('indicators', None),
            trend=data.get('trend', 'SIDEWAYS').upper() if data.get('trend') else None,
        )


# ═══════════════════════════════════════════════════════════════
# PARSERS - Funciones robustas para extraer JSON de texto LLM
# ═══════════════════════════════════════════════════════════════

import re

def extract_json_from_text(text: str, analysis_type: str) -> Optional[Dict[str, Any]]:
    """
    Extrae JSON de texto del LLM de forma robusta.

    Intenta en orden:
    1. JSON completo y válido
    2. Busca bloques {} anidados
    3. Busca patrones específicos para cada tipo

    Args:
        text: Texto devuelto por el LLM
        analysis_type: 'fundamental' | 'sentiment' | 'technical'

    Returns:
        Dict con los datos, o None si no se puede extraer
    """
    if not text or not isinstance(text, str):
        print(f"⚠️ extract_json_from_text: text vacío o no es string")
        return None

    print(f"🔍 Extrayendo JSON ({analysis_type}) de texto con {len(text)} chars")
    print(f"   Primeros 500 chars: {text[:500]}")

    # 1. Intenta parsear el texto completo como JSON
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            print(f"✅ JSON válido parseado como texto completo")
            return data
    except Exception as e:
        print(f"   - Intento 1 (texto completo): {type(e).__name__}")

    # 2. Busca el primer {} válido
    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(text):
        idx = text.find('{', idx)
        if idx == -1:
            break

        try:
            obj, end_idx = decoder.raw_decode(text, idx)
            if isinstance(obj, dict):
                print(f"✅ JSON válido encontrado en posición {idx}")
                return obj
        except json.JSONDecodeError as e:
            pass

        idx += 1

    print(f"❌ No se pudo extraer JSON válido de {analysis_type}")
    return None


def parse_fundamental_analysis(text: str) -> FundamentalAnalysis:
    """Parsea análisis fundamental robusto"""
    print(f"\n[FUNDAMENTAL] Parseando respuesta del agente...")
    data = extract_json_from_text(text, 'fundamental')

    if data:
        try:
            print(f"   Datos JSON extraídos: {data}")
            result = FundamentalAnalysis.from_dict(data)
            print(f"   ✅ Análisis fundamental parseado exitosamente")
            return result
        except Exception as e:
            print(f"   ❌ Error en from_dict: {e}")

    # Fallback con valores por defecto
    print(f"   ⚠️ Usando fallback para fundamental analysis")
    return FundamentalAnalysis(
        score=5,
        confidence=30,
        risk_level="MEDIUM",
        recommendation="HOLD",
        summary="Error parseando análisis fundamental",
    )


def parse_sentiment_analysis(text: str) -> SentimentAnalysis:
    """Parsea análisis de sentimiento robusto"""
    print(f"\n[SENTIMENT] Parseando respuesta del agente...")
    data = extract_json_from_text(text, 'sentiment')

    if data:
        try:
            print(f"   Datos JSON extraídos: {data}")
            result = SentimentAnalysis.from_dict(data)
            print(f"   ✅ Análisis de sentimiento parseado exitosamente")
            return result
        except Exception as e:
            print(f"   ❌ Error en from_dict: {e}")

    # Fallback con valores por defecto
    print(f"   ⚠️ Usando fallback para sentiment analysis")
    return SentimentAnalysis(
        sentiment="NEUTRO",
        confidence=30,
        score=0,
        catalysts=[],
        summary="Error parseando análisis de sentimiento",
    )


def parse_technical_analysis(text: str) -> TechnicalAnalysis:
    """Parsea análisis técnico robusto"""
    print(f"\n[TECHNICAL] Parseando respuesta del agente...")
    data = extract_json_from_text(text, 'technical')

    if data:
        try:
            print(f"   Datos JSON extraídos: {data}")
            result = TechnicalAnalysis.from_dict(data)
            print(f"   ✅ Análisis técnico parseado exitosamente")
            return result
        except Exception as e:
            print(f"   ❌ Error en from_dict: {e}")

    # Fallback con valores por defecto
    print(f"   ⚠️ Usando fallback para technical analysis")
    return TechnicalAnalysis(
        signal="HOLD",
        confidence=30,
        score=5,
        support=0,
        resistance=0,
        summary="Error parseando análisis técnico",
    )
