# ═══════════════════════════════════════════════════════════════
# INVESTMENT SWARM CONFIG
# ═══════════════════════════════════════════════════════════════

# BROKER INTEGRATION
BROKER = "interactive_brokers"  # "interactive_brokers" o "paper_trading"
IB_ACCOUNT = None  # User proporciona en dashboard (ej: "DU123456")
IB_USE_PAPER = True  # True = paper trading (simulación), False = real money
IB_HOST = "127.0.0.1"  # TWS/Gateway local
IB_PORT = 7497  # TWS port

# MARKET TIMING (Nasdaq/NYSE)
MARKET_TIMEZONE = "America/New_York"
MARKET_OPEN_TIME = "09:30"  # HH:MM
MARKET_CLOSE_TIME = "16:00"
PRE_MARKET_TIME = "08:45"  # Para confirmar candidatos
ANALYSIS_START_TIME = "08:00"  # Cuando empieza la búsqueda

# RUNTIME PARAMETERS (usuario define en dashboard al inicio)
CAPITAL_TO_USE = None  # User proporciona: "usar 60% del capital disponible"
MAX_POSITIONS = None  # None = infinito si hay dinero
STOP_LOSS_PERCENT = -15  # Parámetro ajustable
TAKE_PROFIT_PERCENT_SWING = 20  # Para swings
TAKE_PROFIT_PERCENT_POSITION = 50  # Para positions

# TRADING STRATEGY
STRATEGY = "swing_position_hybrid"
SWING_DURATION_DAYS = 30
POSITION_DURATION_MONTHS = 6

# CONVICTION LEVELS & BUY SIZING
BUY_CONVICTION_LEVELS = {
    "VERY_HIGH": {
        "percentage": 0.50,  # 50% del cash disponible
        "min_score": 0.80,
        "requires_confirmation": False,  # Compra directamente
    },
    "HIGH": {
        "percentage": 0.10,  # 10%
        "min_score": 0.65,
        "requires_confirmation": False,  # Compra directamente
    },
    "MEDIUM": {
        "percentage": 0.05,  # 5%
        "min_score": 0.55,
        "requires_confirmation": True,  # Pide confirmación al usuario
    },
}

# ANALYSIS & EXECUTION WORKFLOW
ANALYSIS_MODE = {
    "search_and_confirm": {
        "enabled": True,
        "day_1_analysis_time": "08:00",  # Análisis completo y ranking
        "day_2_premarket_time": "08:45",  # Confirma top 5
        "execution_at_open": "09:31",  # Ejecuta si confirmed
        "top_candidates_to_confirm": 5,  # Reconfirma top 5 al día siguiente
    }
}

# POSITION REVIEW (posiciones ya abiertas)
POSITION_REVIEW = {
    "enabled": True,
    "frequency": "daily",  # daily, 4h
    "review_time": "16:00",  # Al cierre del mercado
    "check_for_sell_signals": True,
}

# SECTORS TO SEARCH (user selects en dashboard)
# SECTORS TO SEARCH
AVAILABLE_SECTORS = {
    "Technology": ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "TSLA", "AMD", "INTC", "CRM"],
    "Healthcare": ["UNH", "JNJ", "PFE", "ABBV", "MRK", "LLY"],
    "Finance": ["JPM", "BAC", "WFC", "GS", "MS", "BLK"],
    "Consumer Discretionary": ["AMZN", "MCD", "NKE", "SBUX", "HD"],
    "Consumer Staples": ["KO", "PG", "WMT", "PEP", "MO"],
    "Industrials": ["BA", "CAT", "GE", "MMM", "RTX"],
    "Energy": ["XOM", "CVX", "COP", "MPC"],
    "Utilities": ["NEE", "DUK", "SO", "D"],
    "Materials": ["NEM", "FCX", "AA", "CLF"],
    "Real Estate": ["AMT", "CCI", "EQIX", "SPG"],
    "Communication Services": ["DIS", "CMCSA", "CHTR", "FOX"],
    "Transportation": ["UPS", "FDX", "DAL", "LUV"],
    "Aerospace & Defense": ["RTX", "LMT", "BA", "NOC"],
    "Semiconductors": ["NVDA", "AMD", "INTC", "QCOM", "TSM"],
    "Biotech": ["AMGN", "GILD", "BIIB", "VRTX"],
}

SELECTED_SECTORS = ["Technology", "Healthcare"]  # User selecciona cuáles usar

# NOTIFICATIONS
TELEGRAM_ENABLED = False
TELEGRAM_BOT_TOKEN = None  # User provides
TELEGRAM_CHAT_ID = None
SEND_ALERTS_ON = {
    "buy_confirmation": True,
    "buy_execution": True,
    "sell_signal": True,
    "position_closed": True,
    "error": True,
}

# ANALYSIS PARAMETERS
FUNDAMENTAL_CACHE_DAYS = 7  # Reutiliza fundamental durante 7 días
MIN_SCORE_TO_ANALYZE = 0.50  # Solo analiza si score > esto
CONFIDENCE_THRESHOLD = 0.60  # Conforme mínima para comprar

# DATA & SOURCES
DATA_SOURCES = {
    "prices": "yfinance",
    "news": "finviz",  # finviz o newsapi
    "fundamentals": "yfinance",
}

# LOGGING & DEBUG
DEBUG_MODE = False
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
SAVE_ANALYSIS_REPORTS = True  # Guarda JSON con cada análisis

# SIMULATION vs REAL
SIMULATION_MODE = True  # True = no ejecuta compras reales, solo simula