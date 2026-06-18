from crewai import Agent
from tools.news_scraper_tool import NewsScraperTool


def create_sentiment_agent():
    """
    Agente de análisis de sentimiento con acceso a noticias reales.

    Flujo:
    1. Llama a news_scraper con el ticker para obtener titulares recientes.
    2. Analiza el tono, catalizadores y red flags de esas noticias reales.
    3. Retorna sentimiento en JSON con claves en español.

    Solo se ejecuta si Fundamental score >= 6.
    """

    return Agent(
        role="Market Sentiment Analyst",
        goal="""Proceso OBLIGATORIO en dos pasos:

        PASO 1 — Llama a la herramienta news_scraper con el ticker exacto para
        obtener noticias reales de las últimas 72h. SIEMPRE llama la herramienta
        primero. Sin noticias reales no puedes dar un sentimiento fiable.

        PASO 2 — Analiza los titulares obtenidos y responde SOLO este JSON:

        {
            "sentimiento": "<POSITIVO|NEUTRO|NEGATIVO>",
            "confianza": <0-100>,
            "catalizadores_positivos": [<lista de catalizadores positivos identificados>],
            "catalizadores_negativos": [<lista de catalizadores negativos identificados>],
            "red_flags": [<problemas críticos si los hay>],
            "noticias_clave": [<2-3 titulares más relevantes>],
            "resumen": "<análisis basado en las noticias reales obtenidas, 1-2 líneas>"
        }

        Si news_scraper no devuelve noticias, usa confianza=20 y sentimiento=NEUTRO.""",

        backstory="""Eres especialista en sentimiento financiero con acceso a noticias en tiempo real.
        CRÍTICO: Usa SIEMPRE la herramienta news_scraper antes de responder. Nunca generes
        sentimiento basado solo en conocimiento histórico — los mercados cambian día a día.

        Al analizar titulares busca: earnings surprises, guidance changes, M&A, regulatory actions,
        executive changes, product launches, analyst upgrades/downgrades, macro catalysts.

        Red flags que bajan el sentimiento: lawsuits, accounting fraud, SEC investigations,
        CEO/CFO departure inesperado, product recalls, major customer losses.""",

        tools=[NewsScraperTool()],
        verbose=False,
        max_iter=3,
    )
