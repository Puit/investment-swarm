"""
Test del bot contra un universo amplio de stocks de distintos perfiles.
Ejecutar: python -m trading.universe_test
Genera: data/universe_results.csv  +  imprime resumen por consola.
"""
import sys
import csv
import logging
from datetime import date, datetime

sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.CRITICAL)
for lib in ('yfinance', 'openai', 'httpx', 'crewai', 'Backtest', 'DecisionEngine',
            'urllib3', 'requests', 'peewee'):
    logging.getLogger(lib).setLevel(logging.CRITICAL)

from trading.backtest_runner import BacktestRunner

CAPITAL = 10_000
CUSTOM_START = date(2020, 1, 1)
CUSTOM_END   = date(2026, 4, 30)

# ── Universo de stocks ──────────────────────────────────────────────────────
# Formato: ticker → (categoría, descripción)
UNIVERSE = {
    # ── Tech / IA — momentum puro ──
    "NVDA":  ("Momentum/AI",          "Nvidia — semiconductores IA"),
    "META":  ("Momentum/Growth",      "Meta — redes sociales + IA"),
    "AMD":   ("Momentum/Semi",        "AMD — semiconductores"),
    "TSLA":  ("High-Volatility",      "Tesla — EV + disruption"),
    "CRWD":  ("Momentum/Cyber",       "CrowdStrike — ciberseguridad"),

    # ── Tech maduro — tendencia estable ──
    "MSFT":  ("Trend/Mature-Tech",    "Microsoft"),
    "GOOG":  ("Trend/Mature-Tech",    "Alphabet / Google"),
    "AAPL":  ("Trend/Mature-Tech",    "Apple"),
    "ORCL":  ("Trend/Enterprise",     "Oracle — cloud enterprise"),
    "ADBE":  ("Trend/Software",       "Adobe — software creativo"),

    # ── Healthcare / Farma ──
    "LLY":   ("Healthcare/Pharma",    "Eli Lilly — GLP-1 / diabetes"),
    "UNH":   ("Healthcare/Insurance", "UnitedHealth — seguros salud"),
    "ABBV":  ("Healthcare/Biopharma", "AbbVie — biopharma"),

    # ── Cíclicos — economía real ──
    "CAT":   ("Cyclical/Industrial",  "Caterpillar — maquinaria pesada"),
    "DE":    ("Cyclical/Industrial",  "Deere — agricultura industrial"),
    "XOM":   ("Cyclical/Energy",      "ExxonMobil — petróleo & gas"),
    "CVX":   ("Cyclical/Energy",      "Chevron — petróleo & gas"),
    "JPM":   ("Cyclical/Finance",     "JPMorgan — banca"),
    "GS":    ("Cyclical/Finance",     "Goldman Sachs — banca inversión"),
    "FCX":   ("Cyclical/Commodity",   "Freeport-McMoRan — cobre"),
    "NUE":   ("Cyclical/Materials",   "Nucor — acero"),

    # ── Pagos / Fintech — tendencia defensiva ──
    "V":     ("Trend/Payments",       "Visa — pagos"),
    "MA":    ("Trend/Payments",       "Mastercard — pagos"),

    # ── Defensivos / Estables ──
    "JNJ":   ("Defensive/Healthcare", "Johnson & Johnson"),
    "PG":    ("Defensive/Staples",    "Procter & Gamble"),
    "KO":    ("Defensive/Staples",    "Coca-Cola"),
    "WMT":   ("Defensive/Retail",     "Walmart"),
    "NEE":   ("Defensive/Utilities",  "NextEra Energy — utilities"),
}

YEARS = ['2020', '2021', '2022', '2023', '2024', '2025']

def run_year(ticker, year, **kwargs):
    r = BacktestRunner.run_backtest(
        year,
        initial_capital=CAPITAL,
        tickers=[ticker],
        progress_callback=None,
        **kwargs,
    )
    if not r['success']:
        return None
    m = r['metrics']
    return {
        'bot':    m['performance']['total_return_pct'],
        'bnh':    m['comparison']['buyhold_return_pct'],
        'spy':    m['comparison']['spy_return_pct'],
        'dd':     m['performance']['max_drawdown_pct'],
        'sharpe': m['performance']['sharpe_ratio'],
        'sl':     m['trading']['stop_loss_count'],
        'buys':   m['trading']['total_buys'],
        'sells':  m['trading']['total_sells'],
        'wr':     m['trading']['win_rate_pct'],
    }

def capture_ratio(bot, bnh):
    """Qué % de los retornos B&H captura el bot. >100 = supera."""
    if abs(bnh) < 0.5:
        return None
    if bnh > 0:
        return round(bot / bnh * 100, 1)
    # En año bajista: bot pierde menos → ratio inverted
    # bot=-1%, bnh=-33%  →  "captura" del riesgo evitado = ratio>100
    return round(bnh / bot * 100, 1) if bot < 0 else None

# ── Ejecución ───────────────────────────────────────────────────────────────
print(f'\n{"="*72}')
print('  UNIVERSE TEST  —  bot vs B&H vs SPY por ticker y año')
print(f'  {len(UNIVERSE)} stocks  |  Capital $10,000 por test  |  2020→2026')
print(f'{"="*72}\n')

all_rows = []  # para CSV

for ticker, (category, description) in UNIVERSE.items():
    print(f'▸ {ticker:<6}  [{category}]  {description}')
    row = {
        'ticker': ticker,
        'category': category,
        'description': description,
    }

    year_results = {}
    for yr in YEARS:
        sys.stdout.write(f'    {yr}... ')
        sys.stdout.flush()
        m = run_year(ticker, yr)
        if m:
            year_results[yr] = m
            cap = capture_ratio(m['bot'], m['bnh'])
            beats_spy = m['bot'] > m['spy']
            beats_bnh = m['bot'] > m['bnh']
            mark = '✓✓' if beats_spy and beats_bnh else ('✓' if beats_spy else '✗')
            cap_str = f'cap={cap:.0f}%' if cap is not None else 'cap=---'
            print(f'bot {m["bot"]:+.1f}%  bnh {m["bnh"]:+.1f}%  spy {m["spy"]:+.1f}%  '
                  f'{mark}  {cap_str}  SL={m["sl"]}')
        else:
            year_results[yr] = None
            print('ERROR')

    # Custom 2020→2026
    sys.stdout.write(f'    Custom... ')
    sys.stdout.flush()
    mc = run_year(ticker, 'Custom', custom_start=CUSTOM_START, custom_end=CUSTOM_END)
    if mc:
        cap = capture_ratio(mc['bot'], mc['bnh'])
        beats_spy = mc['bot'] > mc['spy']
        beats_bnh = mc['bot'] > mc['bnh']
        mark = '✓✓' if beats_spy and beats_bnh else ('✓' if beats_spy else '✗')
        cap_str = f'cap={cap:.0f}%' if cap is not None else 'cap=---'
        print(f'bot {mc["bot"]:+.1f}%  bnh {mc["bnh"]:+.1f}%  spy {mc["spy"]:+.1f}%  '
              f'{mark}  {cap_str}  SL={mc["sl"]}  Sharpe={mc["sharpe"]:.2f}')
    else:
        mc = None
        print('ERROR')

    # Construir fila CSV
    row['bot_custom']    = round(mc['bot'],    2) if mc else None
    row['bnh_custom']    = round(mc['bnh'],    2) if mc else None
    row['spy_custom']    = round(mc['spy'],    2) if mc else None
    row['dd_custom']     = round(mc['dd'],     1) if mc else None
    row['sharpe_custom'] = round(mc['sharpe'], 2) if mc else None
    row['sl_custom']     = mc['sl']                if mc else None
    row['cap_custom']    = capture_ratio(mc['bot'], mc['bnh']) if mc else None
    row['beats_spy_custom'] = mc['bot'] > mc['spy'] if mc else None
    row['beats_bnh_custom'] = mc['bot'] > mc['bnh'] if mc else None

    beats_spy_count = 0
    beats_bnh_count = 0
    for yr in YEARS:
        m = year_results.get(yr)
        row[f'bot_{yr}'] = round(m['bot'], 2) if m else None
        row[f'bnh_{yr}'] = round(m['bnh'], 2) if m else None
        row[f'spy_{yr}'] = round(m['spy'], 2) if m else None
        row[f'sl_{yr}']  = m['sl']            if m else None
        row[f'cap_{yr}'] = capture_ratio(m['bot'], m['bnh']) if m else None
        if m and m['bot'] > m['spy']:
            beats_spy_count += 1
        if m and m['bot'] > m['bnh']:
            beats_bnh_count += 1

    row['years_beat_spy'] = beats_spy_count
    row['years_beat_bnh'] = beats_bnh_count
    all_rows.append(row)
    print()

# ── Guardar CSV ─────────────────────────────────────────────────────────────
out_path = 'data/universe_results.csv'
if all_rows:
    fieldnames = list(all_rows[0].keys())
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(all_rows)
    print(f'\n✓ Resultados guardados en  {out_path}')

# ── Resumen por categoría ────────────────────────────────────────────────────
print(f'\n{"="*72}')
print('  RESUMEN COMBINADO 2020→2026 POR TICKER')
print(f'{"="*72}')
print(f'  {"Ticker":<7} {"Categoría":<26} {"Bot":>7} {"B&H":>8} {"SPY":>7} {"Cap%":>6}  {"BeatSPY":>7}')
print(f'  {"-"*7} {"-"*26} {"-"*7} {"-"*8} {"-"*7} {"-"*6}  {"-"*7}')

# Ordenar por retorno bot descendente
sorted_rows = sorted(all_rows, key=lambda x: x.get('bot_custom') or -999, reverse=True)
for r in sorted_rows:
    bot = r.get('bot_custom')
    bnh = r.get('bnh_custom')
    spy = r.get('spy_custom')
    cap = r.get('cap_custom')
    bs  = f'{r["years_beat_spy"]}/6'
    if bot is None:
        continue
    cap_str = f'{cap:.0f}%' if cap is not None else '---'
    mark = '✓' if r.get('beats_bnh_custom') else ' '
    print(f'  {r["ticker"]:<7} {r["category"]:<26} {bot:>+7.1f}% {bnh:>+7.1f}%  {spy:>+6.1f}%  {cap_str:>5} {mark}  {bs}')

print(f'\n  Cap% = qué % del retorno B&H captura el bot (>100 = supera B&H)')
print(f'  BeatSPY = años (de 6) en que el bot supera al SPY\n')
