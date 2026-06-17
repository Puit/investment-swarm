# 📖 CASOS DE USO Y EJEMPLOS PASO A PASO

## Tabla de Contenidos
1. [Caso 1: Compra Manual desde Dashboard](#caso-1-compra-manual-desde-dashboard)
2. [Caso 2: Análisis por Telegram](#caso-2-análisis-por-telegram)
3. [Caso 3: Orden Programada sin Dinero](#caso-3-orden-programada-sin-dinero)
4. [Caso 4: Monitoreo Automático del Scheduler](#caso-4-monitoreo-automático-del-scheduler)
5. [Caso 5: Venta Programada](#caso-5-venta-programada)

---

## Caso 1: Compra Manual desde Dashboard

### Escenario
Usuario quiere comprar 10 acciones de Apple (AAPL) directamente desde el dashboard después de revisar el análisis.

### Paso a Paso

#### Paso 1: Acceder a Dashboard
```
URL: http://localhost:8501
Pantalla: 💰 PAPER TRADING TAB
```

#### Paso 2: Buscar Ticker
```
INPUT: AAPL
CLICK: 🔎 BUSCAR

SISTEMA:
1. Verifica: ¿Análisis en caché?
   → NO existen (primera búsqueda de hoy)
   
2. Ejecuta 3 agentes EN PARALELO:
   
   ⏱️ FUNDAMENTAL AGENT
   Input: "Analiza P/E, Debt/Equity, ROE de AAPL"
   Output: {
     "score": 7.5,
     "confidence": 85,
     "risk_level": "MEDIUM",
     "recommendation": "BUY",
     "summary": "Strong fundamentals, solid growth trajectory"
   }
   Duración: ~5 segundos
   
   ⏱️ SENTIMENT AGENT
   Input: "Analiza sentimiento de AAPL en noticias"
   Output: {
     "sentiment": "POSITIVO",
     "confidence": 82,
     "catalysts": ["Earnings beat", "New product launch"],
     "summary": "Market highly positive on AAPL"
   }
   Duración: ~5 segundos
   
   ⏱️ TECHNICAL AGENT
   Input: "Analiza technical de AAPL"
   Output: {
     "signal": "BUY",
     "confidence": 78,
     "support": "148.50",
     "resistance": "155.00",
     "summary": "Breaking above 50-day MA"
   }
   Duración: ~5 segundos

3. Espera a que TODOS terminen (timeout 30s)

4. Combina resultados:
   • Fund: 7.5 ✓
   • Sentiment: POSITIVO ✓
   • Technical: BUY ✓
   
   → is_bullish = TRUE
   
5. Calcula recomendación:
   IF (Fund >= 7 AND Sent = POS AND Tech = BUY)
   THEN Recomendación = "🟢 COMPRAR"

6. Guarda en caché:
   data/analysis_storage/AAPL/fundamental.json
   data/analysis_storage/AAPL/sentiment.json
   data/analysis_storage/AAPL/technical.json

7. Renderiza en Dashboard:
```

#### Paso 3: Ver Análisis en Dashboard
```
PANTALLA MUESTRA:

📊 ANÁLISIS COMPLETO: AAPL

┌─────────────────────┬─────────────────────┬──────────────────┐
│ 📊 FUNDAMENTAL      │ 📰 SENTIMIENTO      │ 📈 TÉCNICO       │
├─────────────────────┼─────────────────────┼──────────────────┤
│ Score: 7.5/10       │ 🟢 POSITIVO         │ 🟢 BUY           │
│ Conf: 85%           │ Conf: 82%           │ Conf: 78%        │
│ Risk: MEDIUM        │                     │                  │
│ Recom: BUY          │                     │                  │
└─────────────────────┴─────────────────────┴──────────────────┘

RECOMENDACIÓN FINAL: 🟢 COMPRAR
```

#### Paso 4: Ingresa Cantidad
```
[INPUT] Cantidad a comprar: 10

DASHBOARD CALCULA:
• Precio actual: $150.25 (obtenido de yfinance)
• Cantidad: 10
• Costo: 10 × $150.25 = $1,502.50
• Comisión (0.1%): $1.50
• Total: $1,504.00

[OUTPUT] Total a invertir: $1,504.00 🟢 (tienes cash)
```

#### Paso 5: Presiona COMPRAR
```
CLICK: [🟢 COMPRAR]

SISTEMA VALIDA:
✓ Precio disponible? → $150.25
✓ Cantidad > 0? → 10
✓ Cash suficiente? → $2500 >= $1504 ✓

EJECUTA:
paper_engine.execute_operation_manual(
  ticker="AAPL",
  action="BUY",
  quantity=10,
  price=150.25,
  note="Compra manual desde dashboard"
)

MOTOR ACTUALIZA STATE:
• cash: $2500.00 → $2500 - $1504 = $996.00
• positions["AAPL"] = [{
    "qty": 10,
    "entry_price": 150.25,
    "entry_date": "2024-06-17T14:35:00",
    "conviction": "MANUAL",
    "entry_fee": 1.50
  }]
• trade_history.append({
    "date": "2024-06-17T14:35:00",
    "ticker": "AAPL",
    "action": "BUY",
    "quantity": 10,
    "price": 150.25,
    "amount": 1502.50,
    "fee": 1.50,
    "origin": "MANUAL_DASHBOARD"
  })

GUARDA A DISCO:
data/paper_trading_state.json
```

#### Paso 6: Confirmación en Dashboard
```
DASHBOARD MUESTRA:

✓ Compra ejecutada: 10 x AAPL @ $150.25

CARTERA ACTUALIZADA:
Total: $2,497.75 (era $4850.25)
Cash: $996.00 (era $2500)
Posiciones: AAPL (10), MSFT (5), GOOG (2)

MÓDULO CAMBIA:
(Ahora permite VENDER porque tiene posición)

[Cantidad Venta: 5]
[Total a recibir: $751.25]
[⚙️ PROGRAMAR VENTA] [🔴 VENDER]
```

#### Paso 7: Verificación en Portfolio
```
/portfolio (en Telegram)

💰 CARTERA ACTUALIZADA

AAPL │ 10 acc │ Entrada: $150.25 │ Actual: $150.25 │ PnL: $0
MSFT │ 5 acc  │ Entrada: $380.00 │ Actual: $385.00 │ PnL: +$25
GOOG │ 2 acc  │ Entrada: $2800   │ Actual: $2850   │ PnL: +$100

Total: $2,497.75
Cash: $996.00
Return: +2.4%
```

---

## Caso 2: Análisis por Telegram

### Escenario
Usuario quiere analizar Microsoft (MSFT) usando Telegram Bot.

### Paso a Paso

#### Paso 1: Enviar Comando al Bot
```
CHAT DE TELEGRAM:
User: /fundamental MSFT
```

#### Paso 2: Bot Recibe y Procesa
```
SISTEMA:
1. Parse comando:
   action = "fundamental"
   ticker = "MSFT"

2. Busca análisis en caché:
   ¿data/analysis_storage/MSFT/fundamental.json existe?
   → SÍ (fue analizado hace 3 horas)
   → Usar caché
   
3. Si NO existiera:
   └─ Ejecutar FUNDAMENTAL AGENT
      └─ Procesar datos públicos
      └─ Guardar en caché
```

#### Paso 3: Bot Formatea Respuesta
```
FUNDAMENTAL AGENT DEVUELVE:
{
  "score": 8.2,
  "confidence": 90,
  "risk_level": "LOW",
  "recommendation": "BUY",
  "summary": "Microsoft shows exceptional fundamentals with strong cloud growth, 
             solid balance sheet, and consistent earnings growth. P/E ratio 
             justified by growth trajectory."
}

BOT FORMATEA:
📊 <b>Análisis Fundamental: MSFT</b>

Score: 8.2/10
Confianza: 90%
Riesgo: LOW
Recomendación: BUY

Resumen: Microsoft shows exceptional fundamentals with 
strong cloud growth, solid balance sheet, and consistent 
earnings growth. P/E ratio justified by growth trajectory.
```

#### Paso 4: Bot Envía a Telegram
```
TELEGRAM RECIBE:

📊 Análisis Fundamental: MSFT

Score: 8.2/10
Confianza: 90%
Riesgo: LOW
Recomendación: BUY

Resumen: Microsoft shows exceptional fundamentals...
```

#### Paso 5: Usuario Solicita Análisis Adicional
```
User: /sentiment MSFT

BOT EJECUTA SENTIMENT AGENT:
Output: {
  "sentiment": "POSITIVO",
  "confidence": 88,
  "catalysts": ["Strong Azure growth", "AI investments", "Enterprise deals"],
  "summary": "Overwhelmingly positive market sentiment"
}

TELEGRAM RESPUESTA:
📰 Análisis de Sentimiento: MSFT

Sentimiento: POSITIVO 🟢
Confianza: 88%

Catalizadores: Strong Azure growth, AI investments, Enterprise deals

Resumen: Overwhelmingly positive market sentiment on Microsoft's 
strategic positioning and execution.
```

#### Paso 6: Usuario Solicita Técnico
```
User: /technical MSFT

BOT EJECUTA TECHNICAL AGENT:
Output: {
  "signal": "BUY",
  "confidence": 85,
  "support": "378.50",
  "resistance": "395.00",
  "summary": "Breaking out above key resistance"
}

TELEGRAM RESPUESTA:
📈 Análisis Técnico: MSFT

Señal: BUY 🟢
Confianza: 85%

Soporte: $378.50
Resistencia: $395.00

Resumen: Breaking out above key resistance with strong 
volume confirmation.
```

#### Paso 7: Usuario Decide Comprar
```
User: Basado en los análisis, voy a comprar MSFT

USER ABRE DASHBOARD:
1. Ingresa MSFT
2. Ve análisis (ya en caché, muy rápido)
3. Ingresa cantidad: 5
4. Presiona COMPRAR
5. Confirma en Telegram: ✓ Compra ejecutada

RESULTADO:
- Posición MSFT: 5 acciones
- Total portfolio: $2,850.25
```

---

## Caso 3: Orden Programada sin Dinero

### Escenario
Usuario quiere comprar Tesla (TSLA) pero actualmente no tiene dinero suficiente. Programa la compra para ejecutarse automáticamente cuando baje el precio.

### Paso a Paso

#### Paso 1: Buscar y Analizar TSLA
```
DASHBOARD:
[TSLA] [🔎 BUSCAR]

ANÁLISIS RESULTADOS:
• Fundamental: 6.8/10 ✓
• Sentiment: POSITIVO ✓
• Technical: BUY ✓

RECOMENDACIÓN: 🟡 CONSIDERAR COMPRA
Precio actual: $245.50
Cantidad deseada: 20
Costo total: 20 × $245.50 = $4,910.00
Comisión: $4.91
Total: $4,914.91

CASH DISPONIBLE: $1,200.00
DEFICIT: $3,714.91 ❌
```

#### Paso 2: Usuario Presiona PROGRAMAR
```
CLICK: [⚙️ PROGRAMAR]

SISTEMA:
1. Re-ejecuta análisis frescos:
   ✓ Fundamental: 6.8
   ✓ Sentiment: POSITIVO
   ✓ Technical: BUY
   
2. Evalúa condiciones:
   • is_bullish? → TRUE (6.8 >= 5 AND POSITIVO AND BUY)
   • Dinero suficiente? → FALSE ($1200 < $4914.91)
   
3. Resultado: waiting_for_price
   (Tiene análisis positivos pero falta dinero)

4. Crea orden:
   {
     "id": "TSLA_BUY_1718652000",
     "ticker": "TSLA",
     "action": "BUY",
     "quantity": 20,
     "max_price": 257.78,  (245.50 * 1.05)
     "status": "waiting_for_price",
     "created_at": "2024-06-17T15:30:00",
     "analyses": {
       "fundamental": {"score": 6.8, ...},
       "sentiment": {"sentiment": "POSITIVO", ...},
       "technical": {"signal": "BUY", ...}
     }
   }

5. Guarda en: data/programmed_orders.json
```

#### Paso 3: Dashboard Muestra Confirmación
```
⏳ ORDEN PROGRAMADA (esperando dinero)

Ticker: TSLA
Cantidad: 20
Precio actual: $245.50
Costo total: $4,914.91
Cash disponible: $1,200.00
Deficit: $3,714.91

Análisis: F(6.8) + POSITIVO + BUY

El scheduler monitoreará el precio y ejecutará cuando:
1. Baje el precio (hasta máximo $257.78)
2. Tengas dinero suficiente
3. Los análisis sigan siendo positivos
```

#### Paso 4: Scheduler Monitorea (Diariamente)

##### DÍA 1, 14:35
```
SCHEDULER EJECUTA: process_user_pending_operations()

Lee orden: TSLA_BUY_waiting_for_price
Verifica:
• Precio TSLA: $245.50 (sin cambio)
• Cash: $1,200.00 (sin cambio)
• ¿Ejecutar? → NO

Resultado: Continuar esperando
```

##### DÍA 1, 18:00
```
EVENTO: Usuario recibe salario
Cash: $1,200 + $3,500 = $4,700.00

AÚN INSUFICIENTE: $4,700 < $4,914.91
Deficit: $214.91
```

##### DÍA 2, 09:30
```
SCHEDULER EJECUTA DAILY ANALYSIS:

Para cada ticker, incluida TSLA:

FUNDAMENTAL AGENT:
• Análisis nuevos
• Output: score = 6.9 (mejoró ligeramente)

SENTIMENT AGENT:
• Noticias positivas sobre Tesla
• Output: sentiment = "POSITIVO"

TECHNICAL AGENT:
• Precio bajó
• Output: signal = "BUY"

SCHEDULER VERIFICA CONDICIONES:
• is_bullish? → 6.9 + POSITIVO + BUY → TRUE ✓
• Dinero ahora? → $4,700 >= $4,914.91 → FALSE (aún falta $214.91)
• ¿Ejecutar? → NO

ACTUALIZA ORDEN:
status sigue siendo: waiting_for_price
last_check: "2024-06-18T09:35:00"
```

##### DÍA 2, 15:00
```
EVENTO: Usuario vende algunas posiciones
Venta: 5 × MSFT @ $388.00
Recibe: ~$1,940.00 (menos comisión)

Cash NUEVO: $4,700 + $1,940 - $1.94 = $6,638.06

AHORA: $6,638 >= $4,914.91 ✓ (Dinero OK!)
```

##### DÍA 3, 09:30
```
SCHEDULER EJECUTA DAILY ANALYSIS (otra vez):

Re-analiza TSLA:
✓ Fundamental: 7.1 (sigue mejorando)
✓ Sentiment: POSITIVO
✓ Technical: BUY
✓ Precio: $242.00 (bajó más, favorable)
✓ Cash: $6,638.06 ✓ AHORA SÍ HAY DINERO!

TODAS LAS CONDICIONES CUMPLIDAS:
1. Análisis positivos? → YES
2. Dinero suficiente? → YES ($6,638 > $4,914)
3. Precio dentro de límite? → YES ($242 < $257.78)

✅ EJECUTAR COMPRA

execute_operation_manual(
  ticker="TSLA",
  action="BUY",
  quantity=20,
  price=242.00
)

RESULTADO:
• Compra: 20 × TSLA @ $242.00
• Total: $4,840.00 (incluida comisión)
• Cash nuevo: $6,638.06 - $4,840 = $1,798.06
• Posición: 20 acciones de TSLA

ACTUALIZA ORDEN:
status: "executed"
executed_at: "2024-06-18T09:40:00"

NOTIFICACIÓN (si Telegram está conectado):
✅ Orden Programada Ejecutada

Acción: COMPRA
Ticker: TSLA
Cantidad: 20
Precio: $242.00
Total: $4,840.00

Originalmente programada: 2024-06-17 15:30
Ejecutada: 2024-06-18 09:40
Espera total: 18 horas 10 minutos
```

#### Paso 5: Verificar en Dashboard
```
DASHBOARD ACTUALIZADO:

POSICIONES:
TSLA   │ 20 acc │ Entrada: $242.00 │ Actual: $242.00 │ PnL: $0
MSFT   │ 0 acc  │ (vendidas)
AAPL   │ 10 acc │ Entrada: $150.25 │ Actual: $152.50 │ PnL: +$22.50
GOOG   │ 2 acc  │ Entrada: $2800   │ Actual: $2850   │ PnL: +$100

CARTERA:
Total: $6,680.00
Cash: $1,798.06
Return: +2.8%
```

---

## Caso 4: Monitoreo Automático del Scheduler

### Escenario
Explicación de cómo el Scheduler monitorea automáticamente todas las órdenes programadas sin intervención del usuario.

### Proceso Continuo

```
SCHEDULER INICIA (11:00 AM)
│
├─ LOOP INFINITO:
│
│  CADA 5 MINUTOS:
│  ┌──────────────────────────────────────┐
│  │ process_user_pending_operations()    │
│  │                                      │
│  │ 1. Lee: data/programmed_orders.json │
│  │ 2. Para cada orden con status ≠ exe:│
│  │    a) Obtiene precio actual (Yahoo) │
│  │    b) Verifica condiciones          │
│  │    c) Si OK → EJECUTA               │
│  │ 3. Actualiza JSON                   │
│  └──────────────────────────────────────┘
│  ↓
│  ESPERA 5 MINUTOS
│  ↓
│  REPITE
│
│  A LAS 09:30 CADA DÍA:
│  ┌──────────────────────────────────────┐
│  │ run_daily_analysis()                 │
│  │                                      │
│  │ 1. Obtiene watchlist                │
│  │ 2. Para cada ticker:                │
│  │    a) FUNDAMENTAL AGENT             │
│  │    b) SENTIMENT AGENT               │
│  │    c) TECHNICAL AGENT               │
│  │ 3. Toma decisiones (auto-trade)     │
│  │ 4. Ejecuta si se cumplen criterios  │
│  │ 5. Notifica por Telegram            │
│  └──────────────────────────────────────┘
│
└─ CONTINÚA INDEFINIDAMENTE (hasta que se detenga)
```

### Ejemplo de Ejecución

```
06:00 AM - Scheduler inicia

14:35 - Check #1
  Órdenes pendientes: 2 (TSLA, GOOGL)
  • TSLA: waiting_for_price
    Precio: $245.00 (sin cambio relevante)
    Cash: $1,200 (insuficiente)
    Resultado: CONTINUAR ESPERANDO
  • GOOGL: waiting_for_signal
    Análisis: Fundamental 5.5 (bajo)
    Resultado: CONTINUAR ESPERANDO

14:40 - Check #2
  (Sin cambios significativos)

14:45 - Check #3
  (Sin cambios significativos)

... (repite cada 5 min)

09:30 AM (DÍA 2) - DAILY ANALYSIS
  
  Ejecuta análisis frescos de watchlist
  TSLA:
  • Fundamental: 7.1 ✓
  • Sentiment: POSITIVO ✓
  • Technical: BUY ✓
  • Dinero: $6,638 ✓
  
  ACCIÓN: EJECUTAR COMPRA
  └─ 20 × TSLA @ $242.00
  
  GOOGL:
  • Fundamental: 6.8 ✓
  • Sentiment: POSITIVO ✓
  • Technical: BUY ✓
  • Dinero: $2,000 (insuficiente para 50)
  
  ACCIÓN: CREAR NUEVA ORDEN PROGRAMADA
  └─ waiting_for_price

10:00 AM - Check
  TSLA: status = "executed" (skip)
  GOOGL: waiting_for_price
    Precio: $2,850 (sin cambio)
    Resultado: CONTINUAR

12:00 PM - Check
  (Sin cambios)

... (repite toda la noche)
```

---

## Caso 5: Venta Programada

### Escenario
Usuario tiene 10 acciones de Apple con ganancia y quiere vender si los análisis se vuelven negativos.

### Paso a Paso

#### Paso 1: Actualizar Análisis
```
Actualmente:
• AAPL Fundamental: 7.5 ✓
• AAPL Sentiment: POSITIVO ✓
• AAPL Technical: BUY ✓

Usuario piensa: "Si esto se vuelve negativo, debo vender"
```

#### Paso 2: Presiona "PROGRAMAR VENTA"
```
DASHBOARD (Módulo de Venta):
[Cantidad: 5]
[Total a recibir: $751.25]
[⚙️ PROGRAMAR VENTA] ← CLICK

SISTEMA:
1. Re-ejecuta análisis frescos
2. Verifica condiciones de venta:
   • Fundamental: 7.5 (✓ aún bueno)
   • Sentiment: POSITIVO (✓ aún positivo)
   • Technical: BUY (✓ aún buy)
   
   ¿Recomiendan vender?
   • fundamental < 4? NO
   • sentiment = NEGATIVO? NO
   • signal = SELL? NO
   
   RESULTADO: NO VENDER AHORA
   
3. Status = "waiting_for_signal"
   (Esperando que análisis empeoren)
```

#### Paso 3: Dashboard Muestra
```
⏳ ORDEN PROGRAMADA VENTA (esperando señal)

Ticker: AAPL
Cantidad: 5
Precio actual: $152.50
Ingresos estimados: $762.50

Análisis actual:
• Fund: 7.5 (bueno)
• Sentiment: POSITIVO
• Technical: BUY

El scheduler monitoreará los análisis y venderá cuando:
1. Fundamental cae < 4, O
2. Sentiment = NEGATIVO, O
3. Technical = SELL
```

#### Paso 4: Scheduler Monitorea (Scenario: Análisis se deterioran)

##### DÍA 1
```
Status: OK, análisis siguen positivos
```

##### DÍA 2, 09:30 - DAILY ANALYSIS
```
AAPL análisis frescos:

FUNDAMENTAL AGENT:
• Noticia negativa: Bajas ventas
• Output: score = 3.5 (cayó drásticamente!)

SENTIMENT AGENT:
• Reacciones negativas en redes
• Output: sentiment = "NEGATIVO"

TECHNICAL AGENT:
• Precio quebró soporte
• Output: signal = "SELL"

SCHEDULER VERIFICA:
¿Vender?
• Fundamental < 4? → 3.5 < 4 ✓ SÍ
• O Sentiment = NEG? → SÍ
• O Signal = SELL? → SÍ

✅ AL MENOS UNO CUMPLIDO → EJECUTAR VENTA

execute_operation_manual(
  ticker="AAPL",
  action="SELL",
  quantity=5,
  price=151.00  (bajó por malas noticias)
)

RESULTADO:
• Venta: 5 × AAPL @ $151.00
• Ingresos: $755.00 (menos comisión $0.76)
• Neto: $754.24
• Ganancia en esta venta: ($151.00 - $150.25) × 5 = $3.75

ORDEN ACTUALIZADA:
status: "executed"
executed_at: "2024-06-18T09:42:00"

NOTIFICACIÓN TELEGRAM:
✅ Venta Automática Ejecutada

Acción: VENTA
Ticker: AAPL
Cantidad: 5
Precio: $151.00
Ingresos: $754.24

Motivo: Fundamental deteriorado + Sentimiento negativo + Señal SELL
```

#### Paso 5: Nuevo Estado
```
POSICIONES ACTUALIZADAS:

AAPL │ 5 acc (de 10) │ Entrada: $150.25 │ PnL: +$1.88
TSLA │ 20 acc        │ Entrada: $242.00 │ PnL: $0

CARTERA:
Total: $6,439.12
Cash: $2,552.30 (fue $1,798, +$754 de venta)
Return: +2.9%

Análisis: El sistema automáticamente redujo riesgo al detectar
         deterioro fundamental, evitando mayores pérdidas.
```

---

## Resumen de Procesos Automáticos

```
SISTEMA FUNCIONA 24/7:

Cada 5 minutos:
└─ Checkea órdenes pendientes
   └─ Si condiciones OK → Ejecuta

Diariamente a las 09:30:
└─ Análisis frescos de watchlist
   └─ Toma decisiones automáticas
   └─ Notifica por Telegram

En cualquier momento:
└─ Usuario puede interactuar manualmente
   └─ Comprar, vender, programar desde Dashboard
   └─ Solicitar análisis por Telegram

RESULTADO: Combinación de control manual + automatización inteligente
```

