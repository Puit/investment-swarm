# 📚 DOCUMENTACIÓN COMPLETA DEL INVESTMENT SWARM

## Tabla de Contenidos
1. [Arquitectura General](#arquitectura-general)
2. [Flujo de Datos](#flujo-de-datos)
3. [Componentes del Sistema](#componentes-del-sistema)
4. [Dashboard - Todos los Botones](#dashboard---todos-los-botones)
5. [Bot de Telegram](#bot-de-telegram)
6. [Agentes de IA](#agentes-de-ia)
7. [Lógica de Órdenes Programadas](#lógica-de-órdenes-programadas)
8. [Ejemplos JSON](#ejemplos-json)

---

## Arquitectura General

```
┌─────────────────────────────────────────────────────────────────┐
│                     INVESTMENT SWARM SYSTEM                      │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ FRONTEND (Interfaces de Usuario)                                 │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────┐      ┌──────────────────────┐        │
│  │  DASHBOARD           │      │  TELEGRAM BOT        │        │
│  │  (Streamlit)         │      │  (Python-telegram)   │        │
│  │                      │      │                      │        │
│  │ • Paper Trading      │      │ • /fundamental AAPL  │        │
│  │ • Live Trading       │      │ • /sentiment MSFT    │        │
│  │ • Search Ticker      │      │ • /technical GOOGL   │        │
│  │ • Buy/Sell           │      │ • /portfolio         │        │
│  │ • Analyze            │      │ • /positions         │        │
│  │ • Programar Orden    │      │ • /paper_trading     │        │
│  │                      │      │ • /live_trading      │        │
│  └──────────────────────┘      └──────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ CORE LOGIC (Motores y Orquestadores)                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────┐  ┌────────────────────┐                │
│  │ Paper Trading      │  │ Scheduler          │                │
│  │ Engine             │  │                    │                │
│  │                    │  │ • Daily Analysis   │                │
│  │ • Buy/Sell         │  │ • Monitor Orders   │                │
│  │ • Portfolio Track  │  │ • Execute Trades   │                │
│  │ • PnL Calc         │  │ • Notifications    │                │
│  │ • Commission       │  │                    │                │
│  └────────────────────┘  └────────────────────┘                │
│                                                                  │
│  ┌────────────────────────────────────────────┐                │
│  │ Programmed Orders Manager                   │                │
│  │                                             │                │
│  │ • Save Orders → data/programmed_orders.json │                │
│  │ • Track Status (waiting/executed)           │                │
│  │ • Execute when conditions met               │                │
│  └────────────────────────────────────────────┘                │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ AI AGENTS (CrewAI)                                               │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │ Fundamental      │  │ Sentiment        │  │ Technical    │ │
│  │ Agent            │  │ Agent            │  │ Agent        │ │
│  │                  │  │                  │  │              │ │
│  │ Analyzes:        │  │ Analyzes:        │  │ Analyzes:    │ │
│  │ • P/E Ratio      │  │ • News Sentiment │  │ • Trends     │ │
│  │ • Debt/Equity    │  │ • Social Media   │  │ • Indicators │ │
│  │ • ROE            │  │ • Market Mood    │  │ • Support    │ │
│  │ • Growth         │  │ • Catalysts      │  │ • Resistance │ │
│  │                  │  │                  │  │              │ │
│  │ Returns: Score   │  │ Returns: Sentiment  │ Returns:     │ │
│  │ 0-10 + Risk      │  │ + Confidence     │  │ Signal + %   │ │
│  └──────────────────┘  └──────────────────┘  └──────────────┘ │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ BROKERS & DATA (Conexiones Externas)                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │ Freedom24        │  │ YFinance         │                    │
│  │ (Live Trading)   │  │ (Price Data)     │                    │
│  │                  │  │                  │                    │
│  │ • Execute Orders │  │ • Stock Prices   │                    │
│  │ • Get Portfolio  │  │ • Historical     │                    │
│  │ • Monitor        │  │ • Indicators     │                    │
│  │   Positions      │  │                  │                    │
│  └──────────────────┘  └──────────────────┘                    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ STORAGE (Persistencia de Datos)                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  • data/paper_trading_state.json                                │
│    └─ Portfolio, Positions, Trade History                       │
│                                                                  │
│  • data/programmed_orders.json                                  │
│    └─ Órdenes pendientes de ejecución                          │
│                                                                  │
│  • data/analysis_storage/                                       │
│    └─ Análisis cacheados por ticker                            │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Flujo de Datos

### 1. FLUJO COMPLETO DE UN ANÁLISIS (Dashboard)

```
┌─────────────────────────────────────────────────────────────────┐
│ USUARIO INGRESA TICKER EN DASHBOARD (ej: AAPL)                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ USUARIO PRESIONA BOTÓN "🔎 BUSCAR"                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ DASHBOARD → Verificar si análisis ya existen en caché           │
│              (data/analysis_storage/AAPL/)                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────┴──────────┐
                    │                    │
              SÍ (Caché)         NO (Ejecutar)
                    │                    │
                    ↓                    ↓
         ┌──────────────────┐ ┌──────────────────────────┐
         │ Usar análisis    │ │ Ejecutar 3 agentes en   │
         │ guardados        │ │ paralelo:                │
         └──────────────────┘ └──────────────────────────┘
                    │                    │
                    │          ┌─────────┼──────────┐
                    │          │         │          │
                    │          ↓         ↓          ↓
                    │      FUNDAMENTAL  SENTIMENT  TECHNICAL
                    │      Agent        Agent      Agent
                    │      (LLM)        (LLM)      (LLM)
                    │          │         │          │
                    │          └─────────┼──────────┘
                    │                    │
                    └────────────┬───────┘
                                 ↓
                    ┌────────────────────────┐
                    │ Parsear 3 JSONs        │
                    │ y combinar resultados  │
                    └────────────────────────┘
                                 ↓
                    ┌────────────────────────┐
                    │ Guardar en caché       │
                    │ data/analysis_storage/ │
                    └────────────────────────┘
                                 ↓
                    ┌────────────────────────┐
                    │ Mostrar en Dashboard:  │
                    │ - 3 Scores             │
                    │ - Recomendación Final  │
                    │ - Botones COMPRAR etc  │
                    └────────────────────────┘
```

### 2. FLUJO DE COMPRA NORMAL (Usuario Presiona "COMPRAR")

```
USUARIO PRESIONA BOTÓN "🟢 COMPRAR"
                    ↓
┌─────────────────────────────────────────────────────────────────┐
│ VALIDACIONES PREVIAS                                            │
├─────────────────────────────────────────────────────────────────┤
│ ✓ ¿Hay precio actual?                                           │
│ ✓ ¿Hay cantidad especificada?                                   │
│ ✓ ¿Cash >= Costo Total?                                         │
└─────────────────────────────────────────────────────────────────┘
                    ↓
         ┌────────────────────────┐
         │ Todas validadas OK?    │
         └────────────────────────┘
              ↙                ↘
            SÍ                  NO
            ↓                   ↓
         EJECUTAR         MOSTRAR ERROR
         COMPRA           "❌ Cash insuficiente"
            ↓
┌─────────────────────────────────────────────────────────────────┐
│ paper_engine.execute_operation_manual(                           │
│   ticker="AAPL",                                                │
│   action="BUY",                                                 │
│   quantity=10,                                                  │
│   price=150.25,                                                 │
│   note="Compra manual desde dashboard"                          │
│ )                                                               │
└─────────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────────┐
│ ENGINE: Calcula comisión                                        │
│ comisión = quantity * price * TRANSACTION_COST_PCT (0.1%)       │
│ total_outflow = (10 * 150.25) + comisión                        │
│ total_outflow = $1502.50 + $1.50 = $1504.00                    │
└─────────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────────┐
│ ENGINE: Actualiza estado interno                                │
│ • state["cash"] -= $1504.00                                     │
│ • state["positions"]["AAPL"].append({                           │
│     "qty": 10,                                                  │
│     "entry_price": 150.25,                                      │
│     "entry_date": "2024-06-17T14:30:00",                       │
│     "conviction": "MANUAL",                                     │
│     "entry_fee": 1.50                                           │
│   })                                                             │
│ • state["trade_history"].append({...})                          │
└─────────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────────┐
│ ENGINE: Guarda cambios                                          │
│ paper_engine.save()                                             │
│ → data/paper_trading_state.json                                 │
└─────────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────────┐
│ DASHBOARD: Muestra confirmación                                 │
│ "✓ Compra ejecutada: 10 x AAPL @ $150.25"                      │
│ Dashboard se refresca (st.rerun())                              │
└─────────────────────────────────────────────────────────────────┘
```

### 3. FLUJO DE ORDEN PROGRAMADA (Usuario Presiona "PROGRAMAR")

```
USUARIO PRESIONA BOTÓN "⚙️ PROGRAMAR COMPRA"
                    ↓
┌─────────────────────────────────────────────────────────────────┐
│ handle_programmed_order() verifica:                             │
│ 1. ¿Hay dinero suficiente?                                      │
│ 2. ¿Los análisis son positivos?                                 │
│                                                                 │
│ fund_score = analyses["fundamental"]["score"]                   │
│ sentiment = analyses["sentiment"]["sentiment"]                  │
│ signal = analyses["technical"]["signal"]                        │
│                                                                 │
│ is_bullish = (fund_score >= 7 AND sentiment == "POSITIVO"       │
│              AND signal in ["BUY", "HOLD"])                     │
│              OR (fund_score >= 5 AND sentiment != "NEGATIVO"    │
│              AND signal == "BUY")                               │
└─────────────────────────────────────────────────────────────────┘
                    ↓
        ┌───────────────────────────────────┐
        │ ¿Dinero + Análisis Positivos?     │
        └───────────────────────────────────┘
           ↙              |              ↘
         SÍ              PARCIAL        NO
         ↓               ↓               ↓
    COMPRA         ORDEN          ORDEN
    INMEDIATA      PENDIENTE      PENDIENTE
    (¡AHORA!)      (precio)       (señal)


RAMA SÍ (COMPRA INMEDIATA):
──────────────────────────
   ↓
execute_operation_manual(...)
   ↓
Mostrar: "✅ COMPRA EJECUTADA INMEDIATAMENTE"


RAMA PARCIAL - SIN DINERO (waiting_for_price):
──────────────────────────────────────────────
   ↓
orders_manager.add_order(
  ticker="AAPL",
  action="BUY",
  quantity=10,
  max_price=157.50,
  status="waiting_for_price",
  analyses={...}
)
   ↓
Guardar → data/programmed_orders.json
   ↓
Mostrar: "⏳ ORDEN PENDIENTE (esperando dinero)
         Costo: $1502.50 | Cash: $1000.00
         El scheduler monitoreará el precio"


RAMA PARCIAL - ANÁLISIS NEGATIVOS (waiting_for_signal):
────────────────────────────────────────────────────────
   ↓
orders_manager.add_order(
  status="waiting_for_signal",
  ...
)
   ↓
Mostrar: "⏳ ORDEN PENDIENTE (esperando señal)
         El scheduler reanalizar diariamente"
```

---

## Componentes del Sistema

### 1. Dashboard (dashboard.py)

**Propósito:** Interfaz web para operaciones manuales y seguimiento

**Estructura Principal:**
```
📊 INVESTMENT SWARM DASHBOARD
├── 💰 PAPER TRADING
│   ├── 📊 Cartera (Total, Cash)
│   ├── 📍 Posiciones (tabla)
│   └── 🔍 Buscar Ticker
│       ├── [TEXT INPUT] Ingresa ticker
│       ├── [🔎 BOTÓN] Buscar
│       │
│       ├── 📋 Resultados:
│       │   ├── Fundamental (Score, Confidence, Risk)
│       │   ├── Sentimiento (+ - / N)
│       │   ├── Técnico (BUY/HOLD/SELL)
│       │   └── Recomendación Final
│       │
│       └── 💹 Módulo Compra/Venta:
│           ├── [Cantidad] [Total] [Botones] [Status]
│           ├── [🟢 COMPRAR] [⚙️ PROGRAMAR]
│           │
│           └── (Si hay posición)
│               ├── [Cantidad Venta] [Total] [Botones] [Status]
│               └── [🔴 VENDER] [⚙️ PROGRAMAR VENTA]
│
├── 🔴 LIVE TRADING
│   ├── Conexión Freedom24
│   └── 📍 Posiciones Live
│
└── 📊 ANÁLISIS
    └── (Análisis adicionales guardados)
```

---

## Dashboard - Todos los Botones

### Botón 1: "🔎 BUSCAR"

**Ubicación:** En el buscador de tickers

**Qué hace:**
1. Obtiene el ticker ingresado
2. Verifica si existen análisis en caché
3. Si NO existen: Ejecuta 3 análisis
4. Muestra resultados en pantalla

**Flujo:**
```
Usuario escribe: AAPL
       ↓
Usuario presiona: 🔎 BUSCAR
       ↓
Dashboard verifica caché
       ↓
SI existen → Muestra análisis guardados
NO existen → Ejecuta agentes:
            • Fundamental Agent
            • Sentiment Agent
            • Technical Agent
       ↓
Guarda en caché → data/analysis_storage/AAPL/
       ↓
Muestra en dashboard
```

### Botón 2: "🟢 COMPRAR"

**Ubicación:** En el módulo de compra

**Qué hace:**
1. Valida que haya precio y cantidad
2. Valida que haya cash suficiente
3. Ejecuta compra en el paper engine
4. Actualiza portfolio
5. Muestra confirmación

**Resultado:**
```
✓ Compra ejecutada: 10 x AAPL @ $150.25

Estado updated:
- Cash: $5000 → $3496 (después de comisión)
- Positions: [] → [{"ticker": "AAPL", "qty": 10, ...}]
- Trade History: se agrega registro
```

### Botón 3: "⚙️ PROGRAMAR"

**Ubicación:** Junto al botón COMPRAR

**Qué hace:**
1. Ejecuta nuevamente los 3 análisis
2. Verifica si hay dinero + análisis positivos
3. Si SÍ → Compra inmediatamente
4. Si NO → Guarda como orden pendiente

**Estados posibles:**
- `waiting_for_price`: Esperando que baje el precio
- `waiting_for_signal`: Esperando mejores análisis
- `executed`: Ya fue ejecutada

**Guardado:**
```json
{
  "id": "AAPL_BUY_1718649600",
  "ticker": "AAPL",
  "action": "BUY",
  "quantity": 10,
  "max_price": 157.50,
  "status": "waiting_for_price",
  "created_at": "2024-06-17T14:30:00",
  "analyses": {...}
}
```

### Botón 4: "🔴 VENDER"

**Ubicación:** En el módulo de venta (solo si hay posición)

**Qué hace:**
1. Valida que haya posición del ticker
2. Valida cantidad a vender
3. Ejecuta venta en el paper engine
4. Actualiza portfolio (rest cash + elimina/reduce posición)

**Resultado:**
```
✓ Venta ejecutada: 5 x AAPL @ $152.50

Estado updated:
- Cash: $3496 → $5256 (recibe dinero de venta)
- Positions: [{"qty": 10}] → [{"qty": 5}] (reduce cantidad)
- PnL: Se calcula (152.50 - 150.25) * 5 = $11.25
```

### Botón 5: "⚙️ PROGRAMAR VENTA"

**Ubicación:** Junto al botón VENDER

**Qué hace:**
1. Ejecuta nuevamente los 3 análisis
2. Verifica si análisis recomiendan vender
3. Si SÍ → Vende inmediatamente
4. Si NO → Guarda como orden pendiente de venta

**Criterios para vender:**
- `fund_score < 4` (fundamental muy bajo) O
- `sentiment == "NEGATIVO"` O
- `signal == "SELL"` (señal técnica de venta)

---

## Bot de Telegram

### Comandos Disponibles

#### 1. `/fundamental TICKER`

**Qué hace:**
1. Ejecuta solo el análisis fundamental
2. Retorna score, confidence, risk, recomendación

**Ejemplo de entrada:**
```
/fundamental AAPL
```

**Salida:**
```
📊 Análisis Fundamental: AAPL

Score: 7.5/10
Confianza: 85%
Riesgo: MEDIUM
Recomendación: BUY

Resumen: Strong fundamentals with solid growth...
```

**Flujo interno:**
```
Bot recibe: /fundamental AAPL
            ↓
Crea Crew con Fundamental Agent
            ↓
Agent analiza: P/E ratio, Debt/Equity, ROE, Growth
            ↓
LLM devuelve JSON:
{
  "score": 7.5,
  "confidence": 85,
  "risk_level": "MEDIUM",
  "recommendation": "BUY",
  "summary": "..."
}
            ↓
Bot parsea JSON y formatea respuesta HTML
            ↓
Envía a Telegram
```

#### 2. `/sentiment TICKER`

**Qué hace:**
1. Ejecuta solo análisis de sentimiento
2. Retorna sentiment (POSITIVO/NEUTRO/NEGATIVO), catalysts

**Salida:**
```
📰 Análisis de Sentimiento: AAPL

Sentimiento: POSITIVO 🟢
Confianza: 78%

Catalizadores: Nuevo iPhone, Earnings beat

Resumen: Market sentiment is strong on recent news...
```

#### 3. `/technical TICKER`

**Qué hace:**
1. Ejecuta solo análisis técnico
2. Retorna signal, support, resistance

**Salida:**
```
📈 Análisis Técnico: AAPL

Señal: BUY 🟢
Confianza: 82%

Soporte: $148.50
Resistencia: $155.00

Resumen: Breaking above 50-day MA with bullish momentum...
```

#### 4. `/portfolio`

**Qué hace:**
1. Obtiene cartera del paper engine
2. Muestra totales y posiciones

**Salida:**
```
💰 PAPER TRADING PORTFOLIO

Total: $4,850.25
Cash: $2,500.00
Posiciones Valor: $2,350.25

Posiciones:
├─ AAPL: 10 acc | Entry: $150.25 | Actual: $152.50 | PnL: +$22.50
├─ MSFT: 5 acc | Entry: $380.00 | Actual: $385.00 | PnL: +$25.00
└─ GOOG: 2 acc | Entry: $2800.00 | Actual: $2850.00 | PnL: +$100.00

Return: +2.5%
```

#### 5. `/positions`

**Qué hace:**
1. Igual que portfolio pero enfocado en posiciones

#### 6. `/paper_trading`

**Qué hace:**
1. Muestra solo estadísticas de paper trading
2. Totales, cash, return %

#### 7. `/live_trading`

**Qué hace:**
1. Si broker está conectado: muestra posiciones live
2. Si no: muestra "No disponible - Configura Freedom24"

---

## Agentes de IA

### 1. Fundamental Agent (create_fundamental_agent)

**Modelo:** LLM (GPT-4 o local Mistral)

**Inputs:**
```
Analiza los fundamentos de {TICKER}

Responde SOLO en este JSON:
{
  "score": 0-10,
  "confidence": 0-100,
  "risk_level": "LOW/MEDIUM/HIGH",
  "recommendation": "BUY/HOLD/SELL",
  "summary": "análisis breve"
}
```

**Proceso Interno:**

```
1. ANÁLISIS FUNDAMENTAL
   ↓
   Busca datos públicos de:
   • P/E Ratio (Price to Earnings)
   • PEG Ratio (Price/Earnings to Growth)
   • Debt to Equity
   • ROE (Return on Equity)
   • Growth Rate
   • Market Cap
   • Dividend Yield
   
2. EVALUACIÓN
   ↓
   Asigna score basado en:
   
   SCORE 9-10:   Excelentes fundamentales, muy bajo riesgo
   SCORE 7-8:    Buenos fundamentales, riesgo bajo
   SCORE 5-6:    Neutral, riesgo medio
   SCORE 3-4:    Débiles, riesgo alto
   SCORE 0-2:    Muy débiles, riesgo muy alto
   
3. RISK ASSESSMENT
   ↓
   LOW:    score >= 8
   MEDIUM: 5 <= score < 8
   HIGH:   score < 5
   
4. RECOMENDACIÓN
   ↓
   BUY:  score >= 7
   HOLD: 5 <= score < 7
   SELL: score < 5
   
5. OUTPUT JSON
   ↓
   Retorna estructura JSON con todos los campos
```

**Ejemplo de salida:**
```json
{
  "score": 7.5,
  "confidence": 85,
  "risk_level": "MEDIUM",
  "recommendation": "BUY",
  "summary": "Apple shows strong P/E ratio of 28.5 with robust ROE of 89%. The company maintains healthy balance sheet with low debt (Debt/Equity: 1.2). Expected growth of 8% YoY positions it well."
}
```

### 2. Sentiment Agent (create_sentiment_agent)

**Modelo:** LLM (GPT-4 o local Mistral)

**Inputs:**
```
Analiza sentimiento de mercado para {TICKER}

Responde SOLO en este JSON:
{
  "sentiment": "POSITIVO/NEUTRO/NEGATIVO",
  "confidence": 0-100,
  "catalysts": "lista de catalizadores",
  "summary": "análisis breve"
}
```

**Proceso Interno:**

```
1. RECOPILACIÓN DE DATOS
   ↓
   Busca:
   • Últimas noticias
   • Reportes de analistas
   • Social media sentiment
   • Institucional flows
   • Options market
   
2. ANÁLISIS DE SENTIMIENTO
   ↓
   Procesamiento natural del lenguaje:
   • Positive keywords
   • Negative keywords
   • Neutral stance
   
3. IDENTIFICACIÓN DE CATALIZADORES
   ↓
   Eventos próximos:
   • Earnings report
   • FDA approval
   • Partnership announcements
   • Regulatory news
   
4. CÁLCULO DE CONFIANZA
   ↓
   0-100%: Based on consistency of signals
   
5. OUTPUT JSON
```

**Ejemplo de salida:**
```json
{
  "sentiment": "POSITIVO",
  "confidence": 82,
  "catalysts": "Earnings beat, new product launch, institutional buying",
  "summary": "Market sentiment is strongly positive. Recent earnings exceeded expectations, analyst upgrades are common, and institutional investors are accumulating shares."
}
```

### 3. Technical Agent (create_technical_agent)

**Modelo:** LLM (GPT-4 o local Mistral)

**Inputs:**
```
Analiza técnico de {TICKER}

Responde SOLO en este JSON:
{
  "signal": "BUY/HOLD/SELL",
  "confidence": 0-100,
  "support": "número",
  "resistance": "número",
  "summary": "análisis breve"
}
```

**Proceso Interno:**

```
1. ANÁLISIS TÉCNICO
   ↓
   Calcula indicadores:
   • SMA (Simple Moving Average) 20, 50, 200
   • RSI (Relative Strength Index)
   • MACD (Moving Average Convergence Divergence)
   • Bollinger Bands
   • Volume
   • Trend
   
2. EVALUACIÓN DE TENDENCIA
   ↓
   Uptrend:    Price > SMA50 > SMA200
   Downtrend:  Price < SMA50 < SMA200
   Neutral:    Cruzando promedios
   
3. IDENTIFICA NIVELES
   ↓
   Support:     Nivel donde compradores entran
   Resistance:  Nivel donde vendedores entran
   
4. GENERA SEÑAL
   ↓
   BUY:  Breakout above resistance, RSI oversold
   HOLD: Price entre support y resistance
   SELL: Breakdown below support, RSI overbought
   
5. CÁLCULO DE CONFIANZA
   ↓
   Based on: Número de confirmaciones, volumen, divergencias
   
6. OUTPUT JSON
```

**Ejemplo de salida:**
```json
{
  "signal": "BUY",
  "confidence": 78,
  "support": "148.50",
  "resistance": "155.00",
  "summary": "Price has broken above 50-day MA with increasing volume. RSI shows momentum without overbought conditions. Support at 148.50 provides good risk/reward entry."
}
```

---

## Lógica de Órdenes Programadas

### Estado Machine

```
                    ┌──────────────────────┐
                    │   NUEVA ORDEN        │
                    │  (Creada)            │
                    └──────┬───────────────┘
                           │
              ┌────────────┴──────────────┐
              │                          │
         waiting_for_price      waiting_for_signal
         (sin dinero)            (análisis negativos)
              │                          │
              │                          │
          Monitoring                Monitoring
          Precio                    Análisis
              │                          │
              └───────┬──────────────────┘
                      │
              ┌───────▼──────────┐
              │  CONDICIONES OK  │
              │  (Ejecutar)      │
              └───────┬──────────┘
                      │
                      ↓
              ┌──────────────────┐
              │    EXECUTED      │
              │  (Completada)    │
              └──────────────────┘
```

### Flujo de Monitoreo

```
SCHEDULER SE EJECUTA CADA 5 MINUTOS:
       ↓
┌───────────────────────────────────────────┐
│ Lee: data/programmed_orders.json          │
├───────────────────────────────────────────┤
│ Para cada orden con status "waiting_*"    │
└───────────────────────────────────────────┘
       ↓
   ┌───┴────┬──────────────┐
   │        │              │
WAITING_FOR_PRICE    WAITING_FOR_SIGNAL
   │                      │
   ↓                      ↓
¿Precio bajó?        ¿Análisis mejoraron?
¿Todavía dinero?     ¿Señal es positiva?
   │                      │
   SÍ                      SÍ
   ↓                       ↓
EJECUTAR COMPRA ←───────→ EJECUTAR COMPRA
       │                      │
       └──────────┬───────────┘
                  ↓
           UPDATE STATUS
           executed
           
           GUARDAR EN JSON
```

### Ejemplo Completo de Ejecución

```
1. USUARIO PRESIONA "PROGRAMAR COMPRA"
   - Ticker: AAPL
   - Cantidad: 10
   - Precio actual: $150.25
   - Cash disponible: $1000
   - Costo necesario: $1502.50 (con comisión)
   
2. handle_programmed_order() analiza:
   - Fundamental: 7.5/10 ✓
   - Sentiment: POSITIVO ✓
   - Technical: BUY ✓
   - Dinero: NO ✗
   
3. RESULTADO: waiting_for_price
   
4. ORDEN GUARDADA EN JSON:
   {
     "id": "AAPL_BUY_1718649600",
     "ticker": "AAPL",
     "action": "BUY",
     "quantity": 10,
     "max_price": 157.50,
     "status": "waiting_for_price",
     "created_at": "2024-06-17T14:30:00"
   }

5. SCHEDULER MONITOREA:
   - DÍA 1: Precio = $150.00 (bajó), pero cash aún insuficiente
   - DÍA 2: Precio = $148.50 (bajó más), cash = $2000 ← YA HAY DINERO!
   - DÍA 3: Scheduler re-analiza (daily analysis)
     • Fundamental: 7.2/10 ✓
     • Sentiment: POSITIVO ✓
     • Technical: BUY ✓
     • Dinero: SÍ ✓
   
6. ✅ CONDICIONES CUMPLIDAS: EJECUTA COMPRA
   - Compra 10 x AAPL @ $148.50
   - Comisión: $14.85
   - Total: $1498.35
   - Cash nuevo: $2000 - $1498.35 = $501.65
   - Status: executed
```

---

## Ejemplos JSON

### 1. Análisis Fundamental (Almacenado)

**Ubicación:** `data/analysis_storage/AAPL/fundamental.json`

```json
{
  "ticker": "AAPL",
  "analysis_type": "fundamental",
  "timestamp": "2024-06-17T14:30:00",
  "data": {
    "score": 7.5,
    "confidence": 85,
    "risk_level": "MEDIUM",
    "recommendation": "BUY",
    "summary": "Apple demonstrates strong financial health with P/E ratio of 28.5 (reasonable for growth profile), solid ROE of 89%, and manageable debt levels. Growth projected at 8% YoY with strong cash generation."
  }
}
```

### 2. Análisis Sentimiento (Almacenado)

**Ubicación:** `data/analysis_storage/AAPL/sentiment.json`

```json
{
  "ticker": "AAPL",
  "analysis_type": "sentiment",
  "timestamp": "2024-06-17T14:32:00",
  "data": {
    "sentiment": "POSITIVO",
    "confidence": 82,
    "catalysts": [
      "Q3 earnings beat expectations",
      "New AI features in iOS 18",
      "Goldman Sachs upgrade to $220",
      "Institutional buying pressure"
    ],
    "summary": "Market sentiment strongly positive. Recent earnings results exceeded analyst expectations by 8%, new product announcements generating buzz, and major institutions have been accumulating shares."
  }
}
```

### 3. Análisis Técnico (Almacenado)

**Ubicación:** `data/analysis_storage/AAPL/technical.json`

```json
{
  "ticker": "AAPL",
  "analysis_type": "technical",
  "timestamp": "2024-06-17T14:31:00",
  "data": {
    "signal": "BUY",
    "confidence": 78,
    "support": "148.50",
    "resistance": "155.00",
    "summary": "Price recently broke above the 50-day moving average with strong volume confirmation. RSI at 58 indicates momentum without overbought conditions. Strong support at 148.50 recent low provides favorable risk/reward entry."
  }
}
```

### 4. Portfolio State (Guardado en Tiempo Real)

**Ubicación:** `data/paper_trading_state.json`

```json
{
  "cash": 3496.25,
  "positions": {
    "AAPL": [
      {
        "qty": 10,
        "entry_price": 150.25,
        "entry_date": "2024-06-17T14:35:00",
        "conviction": "MANUAL",
        "score": 7.5,
        "peak_price": 152.50,
        "entry_regime": "BULLISH",
        "entry_fee": 15.03
      }
    ],
    "MSFT": [
      {
        "qty": 5,
        "entry_price": 380.00,
        "entry_date": "2024-06-16T10:00:00",
        "conviction": "HIGH",
        "score": 8.2,
        "peak_price": 385.50,
        "entry_regime": "BULLISH",
        "entry_fee": 19.00
      }
    ]
  },
  "total_transaction_costs": 45.30,
  "trade_history": [
    {
      "date": "2024-06-17T14:35:00",
      "ticker": "AAPL",
      "action": "BUY",
      "price": 150.25,
      "quantity": 10,
      "amount": 1502.50,
      "fee": 15.03,
      "origin": "MANUAL_DASHBOARD",
      "bot_opinion": "SÍ",
      "note": "Compra manual desde dashboard"
    }
  ],
  "created_at": "2024-06-15T09:00:00"
}
```

### 5. Órdenes Programadas (Esperando Ejecución)

**Ubicación:** `data/programmed_orders.json`

```json
[
  {
    "id": "AAPL_BUY_1718649600",
    "ticker": "AAPL",
    "action": "BUY",
    "quantity": 10,
    "max_price": 157.50,
    "created_at": "2024-06-17T14:30:00",
    "last_check": "2024-06-17T14:35:00",
    "status": "waiting_for_price",
    "analyses": {
      "fundamental": {
        "score": 7.5,
        "confidence": 85,
        "risk_level": "MEDIUM",
        "recommendation": "BUY"
      },
      "sentiment": {
        "sentiment": "POSITIVO",
        "confidence": 82
      },
      "technical": {
        "signal": "BUY",
        "confidence": 78
      }
    },
    "execution_attempts": 0
  },
  {
    "id": "GOOGL_SELL_1718650800",
    "ticker": "GOOGL",
    "action": "SELL",
    "quantity": 5,
    "max_price": 2750.00,
    "created_at": "2024-06-17T15:00:00",
    "last_check": "2024-06-17T15:05:00",
    "status": "waiting_for_signal",
    "analyses": {
      "fundamental": {
        "score": 6.5
      },
      "sentiment": {
        "sentiment": "NEUTRO"
      },
      "technical": {
        "signal": "HOLD"
      }
    },
    "execution_attempts": 1
  }
]
```

### 6. Respuesta de Telegram Bot (JSON interno)

```json
{
  "chat_id": "12345678",
  "message_type": "fundamental",
  "ticker": "AAPL",
  "timestamp": "2024-06-17T14:30:00",
  "result": {
    "success": true,
    "analysis": {
      "score": 7.5,
      "confidence": 85,
      "risk_level": "MEDIUM",
      "recommendation": "BUY",
      "summary": "..."
    },
    "formatted_message": "📊 Análisis Fundamental: AAPL\n\nScore: 7.5/10\nConfianza: 85%\nRiesgo: MEDIUM\nRecomendación: BUY\n\nResumen: Apple demonstrates strong..."
  }
}
```

---

## Orden de Ejecución de los Agentes

### Cuando se Busca un Ticker en Dashboard

```
USUARIO PRESIONA "🔎 BUSCAR" EN AAPL
│
├─ VERIFICAR CACHÉ
│  └─ ¿data/analysis_storage/AAPL/ existe?
│     │
│     ├─ SÍ → Usar análisis guardado (saltar a paso 3)
│     │
│     └─ NO → Continuar a paso 1
│
├─ 1️⃣ EJECUTAR FUNDAMENTAL AGENT
│  ├─ Input: "Analiza fundamentos de AAPL"
│  ├─ Procesa datos públicos
│  └─ Output: JSON con score 0-10
│
├─ 2️⃣ EJECUTAR SENTIMENT AGENT (en paralelo con 3️⃣)
│  ├─ Input: "Analiza sentimiento de AAPL"
│  ├─ Procesa noticias, social media
│  └─ Output: JSON con sentiment (POS/NEU/NEG)
│
├─ 3️⃣ EJECUTAR TECHNICAL AGENT (en paralelo con 2️⃣)
│  ├─ Input: "Analiza técnico de AAPL"
│  ├─ Procesa precios, indicadores
│  └─ Output: JSON con signal (BUY/HOLD/SELL)
│
├─ 4️⃣ COMBINAR RESULTADOS
│  ├─ Calcular recomendación final:
│  │  ├─ IF (Fund >= 7 AND Sent = POS AND Tech = BUY) → 🟢 COMPRAR
│  │  ├─ IF (Fund >= 5 AND Sent != NEG AND Tech = BUY) → 🟡 CONSIDERAR
│  │  ├─ IF (Fund < 5 OR Sent = NEG OR Tech = SELL) → 🔴 NO COMPRAR
│  │  └─ ELSE → ⚪ MANTENER
│  │
│  └─ Guardar en caché: data/analysis_storage/AAPL/
│
├─ 5️⃣ MOSTRAR EN DASHBOARD
│  ├─ 3 Cards con scores
│  ├─ Recomendación final
│  ├─ Módulo de compra/venta
│  └─ Botones: COMPRAR | ⚙️ PROGRAMAR
│
└─ FIN
```

### Cuando Scheduler Ejecuta Daily Analysis

```
SCHEDULER SE EJECUTA DIARIAMENTE A LAS 09:30
│
├─ 1️⃣ OBTENER WATCHLIST
│  └─ watchlist = ["AAPL", "MSFT", "GOOGL"]
│
├─ 2️⃣ PARA CADA TICKER:
│  │
│  ├─ 📊 FUNDAMENTAL ANALYSIS
│  │  └─ Retorna: score (0-10)
│  │
│  ├─ 📰 SENTIMENT ANALYSIS
│  │  └─ Retorna: sentiment score (0-10)
│  │
│  ├─ 📈 TECHNICAL ANALYSIS
│  │  └─ Retorna: signal (BUY/HOLD/SELL)
│  │
│  ├─ 🤖 MAKE DECISION
│  │  ├─ Combina los 3 scores
│  │  ├─ Genera decision {action: BUY/SELL, confidence: X}
│  │  │
│  │  └─ IF decision = "BUY":
│  │     └─ EJECUTAR OPERACIÓN
│  │
│  └─ NOTIFICAR POR TELEGRAM
│
└─ FIN
```

### Cuando Usuario Presiona "PROGRAMAR"

```
USUARIO PRESIONA "⚙️ PROGRAMAR COMPRA" EN AAPL
│
├─ 1️⃣ RE-EJECUTAR 3 AGENTES (análisis frescos)
│  ├─ Fundamental Agent
│  ├─ Sentiment Agent
│  └─ Technical Agent
│
├─ 2️⃣ EVALUAR CONDICIONES EN handle_programmed_order()
│  │
│  ├─ Condición 1: ¿Hay dinero?
│  │  └─ total_cost = qty * price
│  │  └─ cash_available >= total_cost?
│  │
│  ├─ Condición 2: ¿Análisis positivos?
│  │  └─ is_bullish = (Fund >= 7 AND Sent = POS AND Tech = BUY)
│  │            OR (Fund >= 5 AND Sent != NEG AND Tech = BUY)
│  │
│  └─ Decisión Final:
│     │
│     ├─ IF Dinero YES AND Bullish YES
│     │  └─ ✅ EJECUTAR COMPRA INMEDIATAMENTE
│     │
│     ├─ IF Dinero NO AND Bullish YES
│     │  └─ ⏳ GUARDAR COMO: waiting_for_price
│     │
│     ├─ IF Dinero YES AND Bullish NO
│     │  └─ ⏳ GUARDAR COMO: waiting_for_signal
│     │
│     └─ IF Dinero NO AND Bullish NO
│        └─ ⏳ GUARDAR COMO: waiting_for_price (prioritario)
│
├─ 3️⃣ GUARDAR EN JSON
│  └─ data/programmed_orders.json
│
├─ 4️⃣ MOSTRAR MENSAJE
│  ├─ SI EJECUTADA: "✅ COMPRA EJECUTADA INMEDIATAMENTE"
│  └─ SI PENDIENTE: "⏳ ORDEN PROGRAMADA (esperando X)"
│
└─ FIN
```

---

## Resumen de Flujos

| Acción | Agentes Usados | Persistencia | Resultado |
|--------|-----------------|---------------|-----------|
| 🔎 Buscar Ticker | Fundamental + Sentiment + Technical | `analysis_storage/` | Muestra análisis en dashboard |
| 🟢 Comprar | Ninguno (usa análisis existentes) | `paper_trading_state.json` | Compra inmediata |
| ⚙️ Programar | Fundamental + Sentiment + Technical | `programmed_orders.json` | Compra inmediata O orden pendiente |
| 🔴 Vender | Ninguno (usa análisis existentes) | `paper_trading_state.json` | Venta inmediata |
| 📊 /fundamental AAPL | Fundamental | `analysis_storage/` | Respuesta Telegram |
| 📰 /sentiment AAPL | Sentiment | `analysis_storage/` | Respuesta Telegram |
| 📈 /technical AAPL | Technical | `analysis_storage/` | Respuesta Telegram |
| 💰 /portfolio | Ninguno | Lee `paper_trading_state.json` | Respuesta Telegram |
| 🤖 Scheduler Daily | Fundamental + Sentiment + Technical | `paper_trading_state.json` | Ejecuta operaciones automáticas |

