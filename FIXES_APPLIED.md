# Fixes Applied to Investment Swarm - Agent JSON Parsing Issue

## Problem Identified
Agents were returning fallback error structures instead of actual analysis data:
```json
{
  "score": 5,
  "sentiment": NULL,
  "signal": NULL,
  "confidence": 50,
  "summary": "Error en análisis - intenta de nuevo"
}
```

This indicated that the parsers were working (returning structure, not crashing) but agents weren't returning valid JSON in the expected format.

## Root Cause Found
The dashboard's `run_analysis_sync()` function had a critical issue:
- It was using `str(result)` to convert the CrewAI result object to string
- The actual agent output is in `result.raw` attribute, not the string conversion of the entire result object
- The parsers were receiving garbage text instead of the actual JSON from the agents

Reference: `core/crew.py` line 117 shows the correct pattern: `output_str = str(crew_result.raw)`

## Changes Made

### 1. **dashboard/dashboard.py**
- ✅ Imported proper parsers: `parse_fundamental_analysis`, `parse_sentiment_analysis`, `parse_technical_analysis`
- ✅ Imported `asdict` from dataclasses for converting parsed dataclasses to dicts
- ✅ Completely rewrote `run_analysis_sync()` to:
  - Extract `result.raw` instead of `str(result)` 
  - Use the standardized parsers instead of manual JSON extraction
  - Added detailed logging to see what the agents are returning
  - Convert parsed dataclasses to dicts using `asdict()`
- ✅ Added logging at each step:
  ```
  [DASHBOARD] Ejecutando análisis X para TICKER
  [DASHBOARD] String conversion (X chars)
  [DASHBOARD] Primeros 500 chars: ...
  ```

### 2. **agents/fundamental_agent.py**
- ✅ Simplified goal to be more direct and JSON-focused
- ✅ Reduced backstory to essential instructions only
- ✅ Set `verbose=False` (was `True`)
- ✅ Set `max_iter=1` (was `3`) - prevents multiple iterations and extra output

### 3. **agents/sentiment_agent.py**
- ✅ Simplified goal with clear JSON format requirement
- ✅ Reduced backstory to essentials
- ✅ Confirmed `verbose=False` and `max_iter=1`

### 4. **agents/technical_agent.py**
- ✅ Simplified goal with clear JSON format requirement
- ✅ Reduced backstory to essentials
- ✅ Confirmed `verbose=False` and `max_iter=1`

### 5. **core/analysis_schemas.py** - Improved Parsers
- ✅ Enhanced `extract_json_from_text()` with detailed logging:
  ```
  🔍 Extrayendo JSON (tipo) de texto con X chars
  ✅ JSON válido parseado como texto completo
  ❌ No se pudo extraer JSON válido
  ```
- ✅ Enhanced `parse_fundamental_analysis()` with logging
- ✅ Enhanced `parse_sentiment_analysis()` with logging  
- ✅ Enhanced `parse_technical_analysis()` with logging

All parsers now show:
- `[FUNDAMENTAL] Parseando respuesta del agente...`
- `Datos JSON extraídos: {...}`
- `✅ Análisis fundamental parseado exitosamente`
- `⚠️ Usando fallback para fundamental analysis` (if needed)

## Expected Behavior After Fixes

### When Analysis is Requested:
1. Dashboard calls `run_analysis_sync(ticker, "fundamental")`
2. Creates crew with fundamental agent
3. Executes `crew.kickoff()` and extracts `result.raw`
4. Passes raw output to `parse_fundamental_analysis()`
5. Parser logs:
   - Input text length and first 500 chars
   - JSON extraction attempts
   - Final parsed data structure
6. Returns proper FundamentalAnalysis dataclass converted to dict
7. Dashboard displays actual analysis instead of fallback

### Logging Output:
```
============================================================
[DASHBOARD] Ejecutando análisis fundamental para AAPL
============================================================
[DASHBOARD] Tipo de resultado: TaskOutput
[DASHBOARD] Tiene .raw? True
[DASHBOARD] String conversion (250 chars)
[DASHBOARD] Primeros 500 chars: {"score": 8, "confidence": ...

[FUNDAMENTAL] Parseando respuesta del agente...
🔍 Extrayendo JSON (fundamental) de texto con 250 chars
✅ JSON válido parseado como texto completo
   Datos JSON extraídos: {"score": 8, "confidence": 85, ...}
   ✅ Análisis fundamental parseado exitosamente
```

## How to Test

### Quick Dashboard Test:
1. Start the dashboard: `streamlit run dashboard/dashboard.py`
2. Go to "📊 Análisis" tab
3. Enter a ticker (e.g., "AAPL")
4. Select analysis type
5. Check console logs to see the full parsing flow
6. Verify analysis data displays correctly (not fallback)

### Full Agent Test Script:
Created `test_agents_debug.py` for standalone testing:
```bash
python test_agents_debug.py
```

This tests each agent individually and shows the full parsing pipeline.

## Why This Works

1. **Correct data source**: Using `result.raw` gets the actual LLM output
2. **Robust parsing**: `extract_json_from_text()` handles various JSON formats
3. **Clear instructions**: Simplified agent prompts reduce extra text
4. **Single iteration**: `max_iter=1` prevents agents from re-running and adding confusion
5. **Detailed logging**: Every step is logged for debugging
6. **Fallback safety**: Parsers always return valid structure, never crash

## Files Modified
- `dashboard/dashboard.py` - Main fix (run_analysis_sync)
- `agents/fundamental_agent.py` - Simplified instructions
- `agents/sentiment_agent.py` - Simplified instructions  
- `agents/technical_agent.py` - Simplified instructions
- `core/analysis_schemas.py` - Enhanced logging in parsers
- `test_agents_debug.py` - New test script

## Next Steps
1. Run the dashboard and test with a few tickers
2. Check console output to verify JSON is being extracted correctly
3. Adjust agent prompts if needed based on actual output
4. Monitor the logging to ensure parsers are getting valid JSON consistently
