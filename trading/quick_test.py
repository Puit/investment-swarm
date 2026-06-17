"""Quick strategy validation test"""
import sys
import logging

sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.CRITICAL)
for lib in ('yfinance', 'openai', 'httpx', 'crewai', 'Backtest', 'DecisionEngine'):
    logging.getLogger(lib).setLevel(logging.CRITICAL)

from trading.backtest_runner import BacktestRunner

TICKERS = ['GOOG', 'MSFT']
CAPITAL = 10_000

def run(year, **kwargs):
    def cb(msg): print(f'  >> {msg}')
    r = BacktestRunner.run_backtest(
        year, initial_capital=CAPITAL, tickers=TICKERS,
        progress_callback=cb, **kwargs
    )
    if not r['success']:
        print(f'ERROR {year}:', r.get('error'))
        return
    m = r['metrics']
    p = m['performance']
    c = m['comparison']
    t = m['trading']
    reg = m.get('regime', {})
    days = reg.get('days', {})
    total = max(sum(days.values()), 1)

    beats_spy = c['bot_return_pct'] > c['spy_return_pct']
    beats_bnh = c['bot_return_pct'] > c['buyhold_return_pct']
    mark = ('SUPERA SPY+BH' if beats_spy and beats_bnh
            else 'SUPERA SPY' if beats_spy
            else 'BAJO SPY')

    print()
    print(f'=== {year} === [{mark}]')
    print(f'  Bot:   {p["total_return_pct"]:+.2f}%   DD={p["max_drawdown_pct"]:.1f}%  Sharpe={p["sharpe_ratio"]:.2f}')
    print(f'  SPY:   {c["spy_return_pct"]:+.2f}%')
    print(f'  B&H:   {c["buyhold_return_pct"]:+.2f}%')
    print(f'  Buys/Sells: {t["total_buys"]}/{t["total_sells"]}  StopLoss={t["stop_loss_count"]}  WinRate={t["win_rate_pct"]:.0f}%')
    if t.get('circuit_breaker_paused_days', 0):
        print(f'  CB paused: {t["circuit_breaker_paused_days"]} days')
    if days:
        parts = [f'{k}={v}d({v/total*100:.0f}%)' for k, v in days.items() if v > 0]
        print(f'  Regime: {" ".join(parts)}')

from datetime import date as ddate

for yr in ['2020', '2021', '2022', '2023', '2024', '2025']:
    run(yr)

run('Custom', custom_start=ddate(2020, 1, 1), custom_end=ddate(2026, 4, 30))
