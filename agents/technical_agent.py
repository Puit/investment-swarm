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
        goal="""Responde SOLO un JSON VÁLIDO. Nada más, nada menos.

        {
            "signal": "<BUY|HOLD|SELL>",
            "confidence": <0-100>,
            "score": <0-10>,
            "support": <número>,
            "resistance": <número>,
            "summary": "<análisis breve en 1-2 líneas>",
            "indicators": {"SMA20": <val>, "RSI": <val>, "MACD": "<pos/neg>"},
            "trend": "<UPTREND|DOWNTREND|SIDEWAYS>"
        }""",

        backstory="""Eres analista técnico senior. CRÍTICO: Responde SOLO JSON. Cero explicaciones.

        Análisis: Tendencias, Soporte/Resistencia, Momentum, Patrones, Indicadores (SMA, RSI, MACD, Volumen).""",

        tools=[YFinanceTool()],
        verbose=False,
        max_iter=1,
    )
