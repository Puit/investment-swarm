# 🎯 Cómo Integrar el Botón "PROGRAMAR"

## ✅ Estado Actual

- ✅ Función `handle_programmed_order()` ya agregada al dashboard
- ✅ Import de `orders_manager` ya agregado
- ✅ Sistema de persistencia JSON listo

## 📋 Dónde Agregar los Botones

### 1. Botón "PROGRAMAR COMPRA"

**Ubicación:** En el módulo de compra, junto al botón "COMPRAR"

```python
if st.button("⚙️ PROGRAMAR", width="stretch", key="btn_program_buy"):
    if not current_price:
        st.error("No hay precio disponible")
    else:
        with st.spinner("Guardando orden programada..."):
            message = handle_programmed_order(
                ticker=ticker,
                quantity=qty_buy,
                action="BUY",
                current_price=current_price,
                analyses=all_analyses
            )
            st.success(message)
```

### 2. Botón "PROGRAMAR VENTA"

**Ubicación:** En el módulo de venta (si hay posición)

```python
if st.button("⚙️ PROGRAMAR VENTA", width="stretch", key="btn_program_sell"):
    if not current_price:
        st.error("No hay precio disponible")
    else:
        with st.spinner("Guardando orden de venta..."):
            message = handle_programmed_order(
                ticker=ticker,
                quantity=qty_sell,
                action="SELL",
                current_price=current_price,
                analyses=all_analyses
            )
            st.success(message)
```

## 🔄 Flujo de Ejecución

1. **Usuario presiona "PROGRAMAR"**
   ↓
2. **Dashboard llama a `handle_programmed_order()`**
   ↓
3. **Función verifica condiciones:**
   - ¿Hay dinero suficiente?
   - ¿Los análisis son positivos?
   ↓
4. **Si SÍ a ambas → Compra INMEDIATAMENTE**
   - Ejecuta con `paper_engine.execute_operation_manual()`
   - Actualiza portfolio
   - Muestra mensaje: "✅ COMPRA EJECUTADA INMEDIATAMENTE"
   ↓
5. **Si NO → Guarda como ORDEN PENDIENTE**
   - Se persiste en `data/programmed_orders.json`
   - Muestra estado: "waiting_for_price" o "waiting_for_signal"
   - El scheduler la ejecutará cuando se cumplan condiciones

## 📊 Archivo de Órdenes Programadas

Ubicación: `data/programmed_orders.json`

```json
[
  {
    "id": "AAPL_BUY_1718649600",
    "ticker": "AAPL",
    "action": "BUY",
    "quantity": 10,
    "max_price": 157.50,
    "status": "waiting_for_price",
    "created_at": "2024-06-17T12:00:00",
    "last_check": "2024-06-17T12:00:00",
    "analyses": {...}
  }
]
```

## 🚀 Próximos Pasos

### 1. Ahora Mismo (Fácil - 5 min)
- Agregar los dos botones en el dashboard (copiar código arriba)
- Probar que funciona

### 2. Después (Medio - 30 min)
- Crear `trading/monitor_programmed_orders.py` que lea el JSON
- Ejecute órdenes cuando se cumplan condiciones

### 3. Final (Integración - 15 min)
- Llamar al monitor desde el scheduler
- O crear un proceso separado que corra continuamente

## ✨ Comportamiento Esperado

### Escenario 1: Compra con dinero + análisis positivos
```
Usuario: Presiona "PROGRAMAR COMPRA"
Dashboard: Verifica análisis → 🟢 POSITIVO + Tiene dinero
Resultado: ✅ COMPRA EJECUTADA INMEDIATAMENTE
```

### Escenario 2: Compra sin dinero
```
Usuario: Presiona "PROGRAMAR COMPRA"
Dashboard: Verifica dinero → ❌ Insuficiente
Resultado: ⏳ ORDEN PENDIENTE (waiting_for_price)
Scheduler: Monitorea cada día hasta que:
  1. Baje el precio
  2. Análisis sigan siendo positivos
  → Ejecuta automáticamente
```

### Escenario 3: Compra con análisis negativos
```
Usuario: Presiona "PROGRAMAR COMPRA"
Dashboard: Verifica análisis → 🔴 NEGATIVO
Resultado: ⏳ ORDEN PENDIENTE (waiting_for_signal)
Scheduler: Re-analiza cada día hasta que:
  1. Mejoren los análisis
  → Ejecuta automáticamente
```

## 📞 Soporte

Si tienes dudas sobre dónde exactamente agregar los botones en tu versión del dashboard, mira la estructura de tu archivo y busca:
- "if st.button" para ver dónde están los otros botones
- Agrega los botones PROGRAMAR justo después de COMPRAR/VENDER
