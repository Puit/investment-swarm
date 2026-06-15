# 📊 Investment Swarm

**AI-powered multi-agent investment analysis bot** con paper trading, análisis técnico/fundamental/sentimiento, y control via Telegram.

Sistema automático de análisis de inversiones que ayuda a tomar decisiones de trading informadas.

---

## 🎯 Características

### 📈 Análisis Multi-Agente
- **Análisis Fundamental**: LLM con CrewAI evaluando empresa (score 0-10)
- **Análisis Técnico**: Indicadores matemáticos (SMA, RSI, MACD, Bollinger Bands)
- **Análisis de Sentimiento**: Noticias y tendencias del mercado
- **Decision Engine**: Combina los tres análisis con pesos configurables (40% fundamental, 35% técnico, 25% sentimiento)

### 🤖 Automatización
- Scheduler diario para análisis automáticos
- Telegram Bot para operaciones manuales y notificaciones
- Timeout de 2h: si no confirmas, reanaliza y ejecuta automáticamente
- Circuit breaker: pausa trading en drawdowns > 15%

### 📊 Dashboard Interactivo
- Streamlit dashboard accesible via Tailscale (desde cualquier dispositivo)
- Watchlist configurable
- Histórico de operaciones con origen (AUTO / MANUAL_TELEGRAM / MANUAL_DASHBOARD)
- Bot opinion en cada operación (SÍ/NO)

### 💰 Paper Trading
- Simula operaciones reales sin dinero
- Comisiones realistas (0.05% IBKR)
- P&L tracking por posición
- Análisis de regime (BULLISH / NEUTRAL / BEARISH / BEAR_RALLY)

### 🔐 Seguridad
- `.env` para credenciales sensibles
- Operaciones confirmadas en Telegram
- Estado persistente en JSON

---

## 📋 Estructura del Proyecto

```
investment-swarm/
├── paper_trading_engine.py          # Motor de trading (paper trading)
├── telegram_bot.py                  # Bot de Telegram
├── investment_decision_engine.py    # Engine de decisiones
├── dashboard.py                     # Dashboard Streamlit
├── main.py                          # Scheduler (próximo)
├── config_improved.py               # Configuración
├── backtest.py                      # Backtesting
│
├── agents/                          # Agentes de análisis (CrewAI)
│   ├── __init__.py
│   ├── fundamental_agent.py
│   └── sentiment_agent.py
│
├── data/                            # Datos persistentes (NO commitear)
│   ├── paper_trading_state.json
│   └── pending_operations.json
│
├── docs/                            # Documentación
│   ├── OPERACIONES_MANUALES.md
│   ├── TELEGRAM_BOT_SETUP.md
│   ├── ARCHITECTURE.md
│   └── ROADMAP.md
│
├── requirements.txt                 # Dependencias
├── .env.example                     # Template para .env
├── .gitignore
└── README.md                        # Este archivo
```

---

## 🚀 Quick Start

### 1. Configuración inicial

```bash
# Clonar el repositorio
git clone https://github.com/tu-usuario/investment-swarm.git
cd investment-swarm

# Crear entorno virtual (Python 3.12)
python3.12 -m venv venv
.\venv\Scripts\Activate.ps1  # Windows PowerShell

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Configurar credenciales

Copia `.env.example` a `.env` y completa:

```bash
# .env
TELEGRAM_BOT_TOKEN=tu_token_de_botfather
TELEGRAM_CHAT_ID=tu_chat_id

# OpenAI (opcional, para LLM)
OPENAI_API_KEY=tu_key

# Ollama (si usas local)
OLLAMA_MODEL=mistral
```

### 3. Lanzar el dashboard

```bash
python -m streamlit run dashboard.py
```

Accede a `http://localhost:8501`

### 4. Lanzar el bot de Telegram

```bash
python telegram_bot.py
```

En Telegram: `/start` para ver comandos

---

## 📱 Uso

### Dashboard (Streamlit)

**Tab 1: Paper Trading**
- Agregar/quitar tickers del watchlist
- Escanear (automático) o invertir ahora (fuerza entrada)
- Ver posiciones abiertas y P&L
- Histórico de trades con origen y bot_opinion

**Tab 2: Análisis Fundamental**
- Botón "Analizar" para cada ticker
- Score 0-10, recomendación (BUY/HOLD/SELL)
- Cached 7 días

**Tab 3: Análisis de Sentimiento**
- Análisis de noticias
- Sentiment positivo/negativo/neutral
- Cached 6 horas

---

### Telegram Bot

```
/buy MSFT 100       → Compra 100 MSFT (pide confirmación)
/sell GOOG 50       → Vende 50 GOOG (pide confirmación)
/positions          → Posiciones abiertas
/portfolio          → Resumen (total, P&L, regime)
/analysis           → Análisis disponibles
/help               → Ver comandos
```

**Notificaciones automáticas:**
- Cuando el scheduler encuentra oportunidad → Telegram te notifica
- Tienes 2h para confirmar
- Si no respondes → Reanaliza y ejecuta automáticamente
- Si el mercado cierra → Orden pendiente para mañana

---

## 🔧 Configuración Avanzada

### Preferencias de análisis por ticker

```python
# Desde el dashboard o código
engine.set_analysis_preference(
    ticker="MSFT",
    daily_fundamental=True,    # ¿Análisis fundamental diarios?
    daily_sentiment=False,      # ¿Análisis sentimiento diarios?
    analysis_time="09:30"       # ¿A qué hora?
)
```

### Regime profiles (personalizable)

Edit `investment_decision_engine.py` para ajustar comportamiento por régimen:

```python
REGIME_PROFILES = {
    "BULLISH": {
        "min_fundamental_score": 6.0,
        "take_profit_pct": 50.0,
        "stop_loss_pct": -10.0,
        ...
    }
}
```

---

## 📊 Arquitectura

```
┌─────────────────────────────────────┐
│     Telegram Bot                    │
│  (Operaciones manuales)             │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│   Paper Trading Engine              │
│  • execute_operation_manual()       │
│  • run_technical_scan()             │
│  • Calculate bot_opinion            │
└──────────────────┬──────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
┌──────────────────┐  ┌──────────────────┐
│ Decision Engine  │  │ Streamlit UI     │
│ (combina análisis)  │ (Dashboard)      │
└──────────────────┘  └──────────────────┘
        ▲                     ▲
        │                     │
   ┌────┴───────────┬────────┴──┐
   ▼                ▼           ▼
Fundamental    Technical    Sentiment
  Agent         Analysis      Agent
 (LLM)         (ta-lib)      (LLM)
```

---

## 📈 Backtesting

Prueba estrategia antes de live trading:

```bash
python backtest.py
```

Resultado ejemplo: +124.57% en 5 años (MSFT+GOOG, con comisiones)

---

## 🛣️ Roadmap

- [x] Paper Trading Engine
- [x] Operaciones manuales + bot_opinion
- [x] Telegram Bot
- [ ] **Paso 3**: Dashboard mejorado (operaciones manuales desde UI)
- [ ] **Paso 4**: Scheduler completo (análisis automáticos + timeouts)
- [ ] **Paso 5**: Live Trading (Interactive Brokers)
- [ ] **Paso 6**: Database (MongoDB)
- [ ] Base de datos histórica
- [ ] Gráficos interactivos avanzados
- [ ] Alertas SMS/Email
- [ ] Web dashboard (FastAPI)

---

## 🔒 Seguridad

- **Nunca commitear** `.env` (credenciales sensibles)
- **Operaciones confirmadas** en Telegram (no automáticas por defecto)
- **Circuit breaker** previene pérdidas en drawdowns
- **Estado persistente** en `data/` (respaldo diario recomendado)

---

## 📚 Documentación

- **[OPERACIONES_MANUALES.md](./docs/OPERACIONES_MANUALES.md)** - Estructura de operaciones con origin y bot_opinion
- **[TELEGRAM_BOT_SETUP.md](./docs/TELEGRAM_BOT_SETUP.md)** - Configurar BotFather y credenciales
- **[ARCHITECTURE.md](./docs/ARCHITECTURE.md)** - Diseño detallado del sistema
- **[ROADMAP.md](./docs/ROADMAP.md)** - Plan de desarrollo

---

## 🤝 Contributing

Este es un proyecto personal. Cambios principales requieren backtest antes de merging.

---

## 📝 License

Proyecto personal. Uso educativo.

---

## ⚠️ Disclaimer

**NO es asesoría financiera.** Usa en paper trading first. Backtestea antes de live trading. Riesgo de pérdidas reales.

---

## 📞 Contacto

Josep - Spain (El Prat de Llobregat)

---

**Última actualización**: Junio 2026

Progreso: Paper Trading + Telegram Bot ✅ | Dashboard UI ⏳ | Scheduler ⏳ | Live Trading ⏳