from crewai import Agent


def create_sentiment_agent():
    """
    Agente de análisis de sentimiento - versión simplificada

    Flujo:
    1. Analiza contexto general de la empresa
    2. Identifica tendencias de mercado
    3. Retorna sentimiento + confianza

    Solo se ejecuta si Fundamental score >= 6.
    """

    return Agent(
        role="Market Sentiment Analyst",
        goal="""Responde SOLO un JSON VÁLIDO. Nada más, nada menos.

        {
            "sentiment": "<POSITIVO|NEUTRO|NEGATIVO>",
            "confidence": <0-100>,
            "score": <-10 a 10>,
            "catalysts": [<catalizadores>],
            "summary": "<análisis breve en 1-2 líneas>",
            "sources": [<fuentes>]
        }""",

        backstory="""Eres especialista en sentimiento financiero. CRÍTICO: Responde SOLO JSON. Cero explicaciones.

        Análisis: Contexto industria, Posición competitiva, Perspectivas, Riesgos macro, Red flags, Catalizadores.""",

        tools=[],
        verbose=False,
        max_iter=1,
    )
