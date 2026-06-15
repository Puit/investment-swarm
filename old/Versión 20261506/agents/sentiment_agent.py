from crewai import Agent
from tools.news_scraper_tool import NewsScraperTool


def create_sentiment_agent():
    """
    Agente de análisis de sentimiento independiente.
    
    Flujo:
    1. Scrape noticias recientes (últimos 7 días)
    2. Analiza tono: positivo/neutro/negativo
    3. Identifica catalizadores: lanzamientos, earnings, regulación, competencia
    4. Retorna sentimiento + confianza
    5. Detecta red flags de noticias: lawsuits, fraud, CEO change, bankruptcy rumors
    
    Solo se ejecuta si Fundamental score >= 6.
    INDEPENDIENTE del análisis técnico (no depende de signals técnicas).
    """
    
    return Agent(
        role="Market Sentiment Analyst",
        goal="""Evaluar sentimiento del mercado y noticias sobre la empresa.
        
        Busca responder:
        - ¿Qué dice el mercado sobre esta empresa AHORA?
        - ¿Hay catalizadores positivos/negativos próximos?
        - ¿Red flags de noticias (lawsuits, fraud, CEO changes)?
        
        Input: Fundamental es OK (score >= 6)
        Tu trabajo: ¿El sentimiento soporta la compra?
        
        Output: sentimiento (POSITIVO/NEUTRO/NEGATIVO) + confianza + catalizadores""",
        
        backstory="""Eres especialista en análisis de sentimiento financiero.
        
        Fuentes de análisis:
        - Noticias recientes: Finviz, Bloomberg, Reuters (últimos 7 días)
        - Earnings calls: ¿Management está optimista o defensivo?
        - Regulación: Cambios regulatorios a favor/en contra
        - Competencia: Nuevos competidores, pérdida de market share
        - Eventos macro: Fed policy, recession signals, sector trends
        
        RED FLAGS CRÍTICAS (bajan sentimiento):
        - Lawsuit against company
        - Accounting scandal or SEC investigation
        - CEO/CFO departure
        - Product recall or safety issues
        - Major customer loss
        - Bankruptcy rumors
        
        CATALIZADORES POSITIVOS (suben sentimiento):
        - Producto/servicio nuevo
        - Earnings beat expectations
        - Fusión/adquisición estratégica
        - Nuevo contrato importante
        - Cambio regulatorio a favor
        - Recompra de acciones (buyback)
        
        Confianza: Alta si múltiples noticias, Baja si data escasa.
        IMPORTANTE: Independiente del análisis técnico. Reportas sentimiento de noticias, no price action.""",
        
        tools=[NewsScraperTool()],
        verbose=True,
        max_iter=3,
    )