from crewai import Agent
from tools.yfinance_tool import YFinanceTool
import logging

logger = logging.getLogger("FundamentalAgent")


def create_fundamental_agent():
    """
    Agente de análisis fundamental mejorado.

    IMPORTANTE: SIEMPRE devuelve un JSON en el EXACTO formato especificado.
    No importa qué pase, el JSON devuelto DEBE tener esta estructura.
    """

    return Agent(
        role="Senior Fundamental Analyst",
        goal="""Responde SOLO un JSON VÁLIDO. Nada más, nada menos.

        {
            "score": <0-10>,
            "confidence": <0-100>,
            "risk_level": "<LOW|MEDIUM|HIGH|CRITICAL>",
            "recommendation": "<BUY|HOLD|SELL|AVOID>",
            "summary": "<análisis breve en 1-2 líneas>",
            "ratios": {"P/E": <valor>, "P/B": <valor>},
            "growth_metrics": {"revenue_yoy": <valor>},
            "red_flags": [<problemas>]
        }""",

        backstory="""Eres analista fundamental senior. CRÍTICO: Responde SOLO JSON. Cero explicaciones, cero texto adicional.

        Análisis: Ratios (P/E, P/B, Deuda/Equity), Crecimiento (YoY), Rentabilidad (ROE, ROIC), Solidez (FCF, Deuda).""",

        tools=[YFinanceTool()],
        verbose=False,
        max_iter=1,
    )
