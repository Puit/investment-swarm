# 🎨 GUÍA VISUAL DE INTERFACES

## Dashboard - Pantalla Completa

```
┌─────────────────────────────────────────────────────────────────────┐
│                 📈 INVESTMENT SWARM DASHBOARD                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│  │ 📚 Paper Trading │  │ 🔴 Live Trading  │  │ 📊 Análisis      │ │
│  │   $4,850.25      │  │   No disponible  │  │ (Guardados)      │ │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘ │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│ TAB: 💰 PAPER TRADING                                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ ┌─ CARTERA ─────────────────┐  ┌─ POSICIONES ───────────────────┐ │
│ │ Total: $4,850.25          │  │ Ticker │ Qty │Entrada│Actual│ │
│ │ Cash:  $2,500.00          │  │ AAPL   │ 10  │$150.25│$152.5│ │
│ │ Inv:   $2,350.25          │  │ MSFT   │ 5   │$380.00│$385.0│ │
│ │ Return: +2.5%             │  │ GOOG   │ 2   │$2800  │$2850 │ │
│ └───────────────────────────┘  └────────────────────────────────┘ │
│                                                                     │
├─ BUSCADOR DE TICKERS ──────────────────────────────────────────────┤
│                                                                     │
│  [____________________AAPL__________] [🔎 BUSCAR]                 │
│                                                                     │
├─ RESULTADOS DE ANÁLISIS ───────────────────────────────────────────┤
│                                                                     │
│ 📊 ANÁLISIS COMPLETO: AAPL                                         │
│                                                                     │
│ ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│ │ 📊 Fund.     │  │ 📰 Sentim.   │  │ 📈 Técnico   │              │
│ │ Score: 7/10  │  │ 🟢 POSITIVO  │  │ 🟢 BUY       │              │
│ │ Conf: 85%    │  │ Conf: 82%    │  │ Conf: 78%    │              │
│ │ Risk: MED    │  │              │  │              │              │
│ └──────────────┘  └──────────────┘  └──────────────┘              │
│                                                                     │
│ RECOMENDACIÓN FINAL: 🟢 COMPRAR                                    │
│                                                                     │
├─ MÓDULO DE COMPRA ─────────────────────────────────────────────────┤
│                                                                     │
│  Cantidad      │ Total Invest  │     BOTONES      │ Posición       │
│  ┌──────────┐  │ $1,502.50     │ [⚙️ PROGRAMAR]  │ ⚪ Sin posición │
│  │    10    │  │ 🟢 Tienes cash│ [🟢 COMPRAR]    │ (primera compra)
│  └──────────┘  │               │                 │                │
│                │               │                 │                │
│ ($150.25/acc)  │ (+ $15.03 com) │                 │                │
│                │               │                 │                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Flujo Visual: Búsqueda de Ticker

```
START: Usuario ingresa AAPL y presiona 🔎
│
└─→ Verificar caché (data/analysis_storage/AAPL/)
    │
    ├─ CACHE EXISTE (< 7 días)
    │  └─→ Cargar análisis guardados
    │      └─→ Mostrar resultados inmediatamente ✅
    │
    └─ CACHE NO EXISTE
       └─→ EJECUTAR ANÁLISIS PARALELOS
           │
           ├─→ Thread 1: FUNDAMENTAL AGENT
           │   ├─ Procesar: P/E, Debt/Equity, ROE
           │   └─ Return: {score: 7.5, ...}
           │
           ├─→ Thread 2: SENTIMENT AGENT
           │   ├─ Procesar: News, Social Media
           │   └─ Return: {sentiment: "POSITIVO", ...}
           │
           ├─→ Thread 3: TECHNICAL AGENT
           │   ├─ Procesar: SMA, RSI, MACD
           │   └─ Return: {signal: "BUY", ...}
           │
           └─→ ESPERAR TODOS (max 30s timeout)
               └─→ COMBINAR RESULTADOS
                   └─→ Calcular Recomendación
                       ├─ IF (Fund >= 7 AND Sent = POS AND Tech = BUY)
                       │  └─ 🟢 COMPRAR
                       └─ ...
                   └─→ GUARDAR EN CACHÉ
                       └─ data/analysis_storage/AAPL/fundamental.json
                       └─ data/analysis_storage/AAPL/sentiment.json
                       └─ data/analysis_storage/AAPL/technical.json
                   └─→ MOSTRAR EN DASHBOARD
```

---

## Flujo Visual: Compra Inmediata

```
START: Usuario presiona 🟢 COMPRAR (qty=10)
│
├─ VALIDACIONES
│  ├─ ¿Precio disponible? ✓ $150.25
│  ├─ ¿Cantidad > 0? ✓ 10
│  └─ ¿Cash suficiente? ✓ $2500 > $1502.50
│
├─ EJECUTAR OPERACIÓN
│  └─ paper_engine.execute_operation_manual(
│       ticker="AAPL",
│       action="BUY",
│       quantity=10,
│       price=150.25
│     )
│
├─ MOTOR PROCESA
│  ├─ Calcula: cost = 10 * $150.25 = $1502.50
│  ├─ Calcula: fee = $1502.50 * 0.001 = $1.50
│  ├─ Total:    $1502.50 + $1.50 = $1504.00
│  │
│  ├─ ACTUALIZA STATE
│  │  ├─ cash: $2500.00 → $995.25
│  │  ├─ positions["AAPL"].append({
│  │  │   qty: 10,
│  │  │   entry_price: 150.25,
│  │  │   entry_date: "2024-06-17T14:30:00",
│  │  │   conviction: "MANUAL",
│  │  │   entry_fee: 1.50
│  │  │ })
│  │  │
│  │  └─ trade_history.append({
│  │      date: "2024-06-17T14:30:00",
│  │      ticker: "AAPL",
│  │      action: "BUY",
│  │      price: 150.25,
│  │      quantity: 10,
│  │      amount: 1502.50,
│  │      fee: 1.50,
│  │      origin: "MANUAL_DASHBOARD"
│  │    })
│  │
│  └─ GUARDAR A DISCO
│     └─ data/paper_trading_state.json
│
├─ DASHBOARD ACTUALIZA
│  └─ Mostrar:
│     ✓ Compra ejecutada: 10 x AAPL @ $150.25
│     ✓ Cartera: Cash $995.25 | Inv $1502.50 | Total $2497.75
│     ✓ Posiciones: AAPL 10 unidades
│
└─ END: st.rerun() para refrescar pantalla
```

---

## Flujo Visual: Orden Programada (Escenario 1)

### Dinero + Análisis Positivos = Compra Inmediata

```
START: Usuario presiona ⚙️ PROGRAMAR (qty=10, fund=7.5, sent=POS, tech=BUY)
│
├─ RE-EJECUTAR ANÁLISIS (frescos)
│  ├─ Fundamental Agent → 7.5/10
│  ├─ Sentiment Agent → POSITIVO
│  └─ Technical Agent → BUY
│
├─ EVALUAR CONDICIONES
│  ├─ is_bullish = (7.5 >= 7 AND POS AND BUY) → TRUE ✓
│  ├─ cash = $2500.00
│  ├─ total_cost = 10 * $150.25 = $1502.50
│  └─ cash >= total_cost? → $2500 >= $1502.50 → TRUE ✓
│
├─ AMBAS CONDICIONES OK
│  └─ handle_programmed_order() retorna:
│     └─ Llamar directamente: execute_operation_manual(...)
│
├─ RESULTADO
│  └─ COMPRA INMEDIATA
│     └─ (Mismo flujo que "COMPRAR" normal)
│
└─ MOSTRAR: ✅ COMPRA EJECUTADA INMEDIATAMENTE
           10 x AAPL @ $150.25
```

---

## Flujo Visual: Orden Programada (Escenario 2)

### Sin Dinero = waiting_for_price

```
START: Usuario presiona ⚙️ PROGRAMAR
       (qty=10, dinero=$1000, costo=$1502.50)
│
├─ RE-EJECUTAR ANÁLISIS
│  └─ Fundamental: 7.5 ✓
│     Sentiment: POSITIVO ✓
│     Technical: BUY ✓
│
├─ EVALUAR CONDICIONES
│  ├─ is_bullish? → TRUE ✓
│  ├─ cash >= total_cost? → $1000 >= $1502.50 → FALSE ✗
│
├─ RESULTADO: SIN DINERO
│  └─ handle_programmed_order() retorna:
│     └─ status = "waiting_for_price"
│
├─ GUARDAR ORDEN
│  └─ orders_manager.add_order(
│       ticker="AAPL",
│       action="BUY",
│       quantity=10,
│       max_price=157.50,  (150.25 * 1.05)
│       status="waiting_for_price",
│       analyses={...}
│     )
│
├─ GUARDAR EN DISCO
│  └─ data/programmed_orders.json
│
├─ MOSTRAR MENSAJE
│  └─ ⏳ ORDEN PROGRAMADA (esperando dinero)
│     Costo: $1,502.50
│     Cash: $1,000.00
│     Deficit: $502.50
│     El scheduler monitoreará el precio
│
└─ END: Esperando que scheduler ejecute

SCHEDULER MONITOREA (cada 5 minutos):
│
├─ Lee: data/programmed_orders.json
│  └─ Encontró: AAPL_BUY_waiting_for_price
│
├─ DÍA 1, 14:35
│  ├─ Precio AAPL: $150.00
│  ├─ Cash usuario: $1000.00
│  └─ ¿Ejecutar? → NO (aún no hay dinero)
│
├─ DÍA 1, 18:00
│  ├─ Usuario recibe dividendo: +$600
│  └─ Cash: $1600.00
│
├─ DÍA 2, 09:30 (Daily Analysis)
│  ├─ Precio AAPL: $148.50
│  ├─ Re-analiza:
│  │  ├─ Fundamental: 7.2 ✓
│  │  ├─ Sentiment: POSITIVO ✓
│  │  └─ Technical: BUY ✓
│  │
│  ├─ Verificar condiciones:
│  │  ├─ cash >= total_cost? → $1600 >= $1485 → TRUE ✓
│  │  └─ Análisis positivos? → TRUE ✓
│  │
│  ├─ ✅ AMBAS CONDICIONES CUMPLIDAS
│  │
│  └─ EJECUTAR COMPRA
│     ├─ execute_operation_manual(...)
│     ├─ Compra: 10 x AAPL @ $148.50
│     ├─ Total: $1,485.00 (incluida comisión)
│     ├─ Cash nuevo: $1600 - $1485 = $115.00
│     │
│     ├─ UPDATE ORDER STATUS
│     │  └─ status: "executed"
│     │  └─ executed_at: "2024-06-18T09:35:00"
│     │
│     └─ NOTIFICAR
│        └─ (Si Telegram está configurado)
│           "✅ Orden Programada Ejecutada
│            Compra: 10 x AAPL @ $148.50
│            Originalmente programada: 2024-06-17 14:30"
```

---

## Flujo Visual: Orden Programada (Escenario 3)

### Análisis Negativos = waiting_for_signal

```
START: Usuario presiona ⚙️ PROGRAMAR
       (dinero OK, pero análisis malos)
│
├─ RE-EJECUTAR ANÁLISIS
│  └─ Fundamental: 4.5 ✗ (muy bajo)
│     Sentiment: NEGATIVO ✗
│     Technical: SELL ✗
│
├─ EVALUAR CONDICIONES
│  ├─ is_bullish? → FALSE ✗
│  ├─ cash >= total_cost? → TRUE ✓ (pero no importa)
│
├─ RESULTADO: ANÁLISIS NO POSITIVOS
│  └─ handle_programmed_order() retorna:
│     └─ status = "waiting_for_signal"
│
├─ GUARDAR ORDEN
│  └─ orders_manager.add_order(
│       status="waiting_for_signal",
│       ...
│     )
│
├─ MOSTRAR MENSAJE
│  └─ ⏳ ORDEN PROGRAMADA (esperando señal)
│     Tienes dinero suficiente
│     Análisis actual: F(4.5) + NEGATIVO + SELL
│     El scheduler reanalizar diariamente
│
└─ END: Esperando mejora en análisis

SCHEDULER MONITOREA:
│
├─ DÍA 2, 09:30 (Daily Analysis)
│  ├─ Re-analiza AAPL:
│  │  ├─ Noticias mejoraron
│  │  ├─ Fundamental: 6.5 ✓
│  │  ├─ Sentiment: POSITIVO ✓
│  │  └─ Technical: BUY ✓
│  │
│  ├─ ✅ ANÁLISIS MEJORARON
│  │
│  └─ EJECUTAR COMPRA
│     └─ (Mismo proceso que Escenario 2)
│
└─ SI ANÁLISIS NO MEJORAN
   └─ Continuar monitoreando diariamente
```

---

## Telegram Bot - Flujo de Comandos

### Comando: /fundamental AAPL

```
USER TYPES: /fundamental AAPL
│
├─ BOT RECIBE COMANDO
│  ├─ Parse: action="fundamental", ticker="AAPL"
│  └─ Enviar typing indicator a Telegram
│
├─ EJECUTAR FUNDAMENTAL AGENT
│  ├─ create_fundamental_agent()
│  ├─ Create Task: "Analiza fundamentos de AAPL"
│  ├─ Create Crew: agents=[agent], tasks=[task]
│  └─ crew.kickoff()
│
├─ PROCESAR OUTPUT
│  ├─ Intenta parsear JSON directamente
│  │  └─ Si falla: Usa regex fallback
│  │
│  └─ Extrae:
│     ├─ score (0-10)
│     ├─ confidence (0-100)
│     ├─ risk_level (LOW/MEDIUM/HIGH)
│     ├─ recommendation (BUY/HOLD/SELL)
│     └─ summary (texto)
│
├─ GUARDAR EN CACHÉ
│  └─ data/analysis_storage/AAPL/fundamental.json
│
├─ FORMATEAR RESPUESTA
│  └─ HTML parse_mode:
│     📊 <b>Análisis Fundamental: AAPL</b>
│     
│     Score: 7.5/10
│     Confianza: 85%
│     Riesgo: MEDIUM
│     Recomendación: BUY
│     
│     Resumen: Apple demonstrates strong...
│
└─ ENVIAR A TELEGRAM
   └─ chat.send_message(response_text)
```

---

## Pantalla de Cartera en Telegram

```
/portfolio

💰 CARTERA DE PAPER TRADING

Total: $4,850.25
Cash: $2,500.00
Invertido: $2,350.25

┌─ POSICIONES ─────────────────────────────┐
│                                          │
│ AAPL  │ 10 acc                          │
│ Entrada: $150.25                        │
│ Actual: $152.50                         │
│ PnL: +$22.50 (+1.5%)                   │
│                                          │
│ MSFT  │ 5 acc                           │
│ Entrada: $380.00                        │
│ Actual: $385.00                         │
│ PnL: +$25.00 (+1.3%)                   │
│                                          │
│ GOOG  │ 2 acc                           │
│ Entrada: $2,800.00                      │
│ Actual: $2,850.00                       │
│ PnL: +$100.00 (+1.8%)                  │
│                                          │
└──────────────────────────────────────────┘

Return Total: +2.5%
Comisiones Pagadas: $45.30
```

---

## Pantalla de Órdenes Programadas Pendientes

```
/programmed_orders

⏳ ÓRDENES PROGRAMADAS PENDIENTES

┌─ ORDEN 1 ────────────────────────────────┐
│ ID: AAPL_BUY_1718649600                 │
│ Acción: BUY 🟢                          │
│ Cantidad: 10                            │
│ Ticker: AAPL                            │
│ Precio Objetivo: <= $157.50             │
│ Status: waiting_for_price               │
│ Creada: 2024-06-17 14:30                │
│ Análisis:                               │
│  • Fund: 7.5/10                         │
│  • Sentiment: POSITIVO 🟢               │
│  • Technical: BUY                       │
│                                         │
│ Dinero requerido: $1,502.50             │
│ Cash disponible: $1,000.00              │
│ Deficit: $502.50 (esperando)            │
└─────────────────────────────────────────┘

┌─ ORDEN 2 ────────────────────────────────┐
│ ID: MSFT_BUY_1718650200                 │
│ Acción: BUY 🟢                          │
│ Cantidad: 5                             │
│ Status: waiting_for_signal              │
│ Análisis actuales:                      │
│  • Fund: 5.5/10 (neutral)               │
│  • Sentiment: NEUTRO ⚪                 │
│  • Technical: HOLD                      │
│                                         │
│ Esperando: Mejora en análisis            │
│ Esperando desde: 2024-06-17 15:00       │
└─────────────────────────────────────────┘

Total Órdenes Pendientes: 2
Dinero Reservado: $3,500.00
```

---

## Estructura de Persistencia en Disco

```
project-root/
│
├── data/
│   │
│   ├── paper_trading_state.json
│   │   └─ {
│   │       "cash": 2500.00,
│   │       "positions": {...},
│   │       "trade_history": [...],
│   │       "total_transaction_costs": 45.30
│   │     }
│   │
│   ├── programmed_orders.json
│   │   └─ [
│   │       {
│   │         "id": "AAPL_BUY_1718649600",
│   │         "status": "waiting_for_price",
│   │         "analyses": {...}
│   │       },
│   │       ...
│   │     ]
│   │
│   └── analysis_storage/
│       │
│       ├── AAPL/
│       │   ├── fundamental.json
│       │   ├── sentiment.json
│       │   └── technical.json
│       │
│       ├── MSFT/
│       │   ├── fundamental.json
│       │   ├── sentiment.json
│       │   └── technical.json
│       │
│       └── GOOG/
│           ├── fundamental.json
│           ├── sentiment.json
│           └── technical.json
```

---

## Resumen de Estados Posibles

```
┌─────────────────────────────────────────┐
│  ORDEN PROGRAMADA - MÁQUINA DE ESTADOS  │
├─────────────────────────────────────────┤
│                                         │
│       NUEVA (Creada)                   │
│            │                            │
│    ┌───────┴────────┐                  │
│    │                │                  │
│  waiting_for_price  waiting_for_signal │
│  (sin dinero)       (análisis negativos)
│    │                │                  │
│    ├─ Precio baja   ├─ Análisis     │
│    │  + Dinero ✓    │  mejoran ✓    │
│    │                │                  │
│    └────────┬───────┘                  │
│             │                          │
│          EJECUTAR COMPRA                │
│             │                          │
│          EXECUTED ✅                   │
│                                         │
└─────────────────────────────────────────┘
```

