"""Quick strategy validation test — compara universos de tickers"""
import sys
import logging

sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.CRITICAL)
for lib in ('yfinance', 'openai', 'httpx', 'crewai', 'Backtest', 'DecisionEngine'):
    logging.getLogger(lib).setLevel(logging.CRITICAL)

from trading.backtest_runner import BacktestRunner

CAPITAL = 10_000

UNIVERSES = {
    'BASE (GOOG+MSFT)':       ['GOOG', 'MSFT'],
    'AMPLIADO (5 tickers)':   ['GOOG', 'MSFT', 'NVDA', 'META', 'AMZN'],
    'AMPLIADO+ (8 tickers)':  ['GOOG', 'MSFT', 'NVDA', 'META', 'AMZN', 'AAPL', 'TSLA', 'AVGO'],
}

def run(year, tickers, **kwargs):
    r = BacktestRunner.run_backtest(
        year, initial_capital=CAPITAL, tickers=tickers,
        progress_callback=None, **kwargs
    )
    if not r['success']:
        return None
    m = r['metrics']
    p = m['performance']
    c = m['comparison']
    t = m['trading']
    return {
        'bot':     p['total_return_pct'],
        'spy':     c['spy_return_pct'],
        'bnh':     c['buyhold_return_pct'],
        'buys':    t['total_buys'],
        'sells':   t['total_sells'],
        'sl':      t['stop_loss_count'],
        'winrate': t['win_rate_pct'],
        'dd':      p['max_drawdown_pct'],
        'sharpe':  p['sharpe_ratio'],
    }

from datetime import date as ddate

YEARS = ['2020', '2021', '2022', '2023', '2024', '2025']
CUSTOM = dict(custom_start=ddate(2020, 1, 1), custom_end=ddate(2026, 4, 30))

results = {}  # {universe_name: {year: metrics}}

for uname, tickers in UNIVERSES.items():
    print(f'\n{"="*60}')
    print(f'  {uname}  →  {tickers}')
    print(f'{"="*60}')
    results[uname] = {}
    for yr in YEARS:
        sys.stdout.write(f'  {yr}... ')
        sys.stdout.flush()
        m = run(yr, tickers)
        if m:
            results[uname][yr] = m
            beats_spy = m['bot'] > m['spy']
            beats_bnh = m['bot'] > m['bnh']
            mark = ('✓✓' if beats_spy and beats_bnh
                    else '✓ ' if beats_spy
                    else '✗ ')
            print(f'Bot {m["bot"]:+.1f}%  SPY {m["spy"]:+.1f}%  B&H {m["bnh"]:+.1f}%  {mark}  '
                  f'(SL={m["sl"]}  DD={m["dd"]:.0f}%)')
        else:
            print('ERROR')
    sys.stdout.write('  Custom... ')
    sys.stdout.flush()
    m = run('Custom', tickers, **CUSTOM)
    if m:
        results[uname]['Custom'] = m
        beats_spy = m['bot'] > m['spy']
        beats_bnh = m['bot'] > m['bnh']
        mark = ('✓✓' if beats_spy and beats_bnh else '✓ ' if beats_spy else '✗ ')
        print(f'Bot {m["bot"]:+.1f}%  SPY {m["spy"]:+.1f}%  B&H {m["bnh"]:+.1f}%  {mark}  '
              f'(SL={m["sl"]}  DD={m["dd"]:.0f}%)')

# ── Resumen comparativo ──────────────────────────────────────────────
print(f'\n{"="*60}')
print('  RESUMEN COMPARATIVO')
print(f'{"="*60}')
print(f'  {"Año":<8}', end='')
for uname in UNIVERSES:
    short = uname.split('(')[0].strip()[:10]
    print(f'  {short:<12}', end='')
print()
print(f'  {"-"*8}', end='')
for _ in UNIVERSES:
    print(f'  {"-"*12}', end='')
print()

for yr in YEARS + ['Custom']:
    print(f'  {yr:<8}', end='')
    for uname in UNIVERSES:
        m = results.get(uname, {}).get(yr)
        if m:
            beats_spy = m['bot'] > m['spy']
            beats_bnh = m['bot'] > m['bnh']
            mark = '✓✓' if beats_spy and beats_bnh else '✓' if beats_spy else '✗'
            print(f'  {m["bot"]:+.1f}% {mark:<3}     ', end='')
        else:
            print(f'  {"---":<12}', end='')
    print()
