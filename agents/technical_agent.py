from crewai import Agent
from tools.yfinance_tool import YFinanceTool


def create_technical_agent():
    """
    Agente de análisis técnico mejorado.
    
    Flujo:
    1. Obtiene datos históricos (3 meses mínimo)
    2. Calcula indicadores: SMA20/50/200, RSI, MACD, Bollinger Bands
    3. Analiza volumen (debe confirmar movimiento)
    4. Genera señal: ALCISTA/LATERAL/BAJISTA con confianza %
    5. Calcula entry/stop/target con R:R ratio
    
    Solo se ejecuta si Fundamental score >= 6.
    """
    
    return Agent(
        role="Technical Analyst",
        goal="""Analizar tendencias técnicas y generar señales de trading.

        Responde SOLO en este JSON:
        {{
            "signal": "BUY/HOLD/SELL",
            "confidence": 0-100,
            "support": "número",
            "resistance": "número",
            "summary": "análisis breve"
        }}

        NO incluyas más texto. Solo JSON válido.""",

        backstory="""Eres analista técnico con experiencia en trading.

        Analiza:
        - Tendencias de precio
        - Niveles de soporte/resistencia
        - Momentum del mercado
        - Patrones de precio

        SEÑALES:
        - BUY: Tendencia alcista con soporte claro
        - HOLD: Lateral o indefinido
        - SELL: Tendencia bajista con resistencia rota

        Confianza: Alta con múltiples confirmaciones.""",

        tools=[YFinanceTool()],
        verbose=False,
        max_iter=1,
    )