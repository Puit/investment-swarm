"""
TEST DE RENDIMIENTO vs SPY: 2022 (bajista) y 2024 (alcista)
============================================================

Ejecuta el backtest con GOOGL y MSFT en ambos años y compara
contra el índice SPY. El objetivo es que el bot supere al SPY
en AMBOS escenarios: perdiendo menos en 2022 y ganando más en 2024.

Uso:
    cd investment-swarm
    python -m trading.run_benchmark_test
"""

import sys
import logging
from datetime import datetime

# Silenciar logs de yfinance y crewai durante el test
logging.getLogger("yfinance").setLevel(logging.ERROR)
logging.getLogger("openai").setLevel(logging.ERROR)

from trading.backtest_runner import BacktestRunner

TICKERS = ["GOOGL", "MSFT"]
CAPITAL  = 10_000.0

TESTS = [
    {"name": "2022 (mercado BAJISTA)",  "range": "2022"},
    {"name": "2024 (mercado ALCISTA)",  "range": "2024"},
]

SEP = "=" * 70


def run_test(name: str, range_key: str) -> dict:
    print(f"\n{SEP}")
    print(f"  TEST: {name}")
    print(f"  Tickers: {', '.join(TICKERS)}  |  Capital: ${CAPITAL:,.0f}")
    print(SEP)

    result = BacktestRunner.run_backtest(
        date_range=range_key,
        initial_capital=CAPITAL,
        transaction_cost_pct=0.001,
        tickers=TICKERS,
        progress_callback=lambda msg: print(f"  >> {msg}"),
    )

    if not result["success"]:
        print(f"  ERROR: {result.get('error')}")
        return {}

    m = result["metrics"]
    perf  = m["performance"]
    comp  = m["comparison"]
    trade = m["trading"]
    costs = m["costs"]
    reg   = m.get("regime", {})

    print(f"\n  PERÍODO: {m['backtest_period']['start']} → {m['backtest_period']['end']}")
    print(f"\n  RENDIMIENTO (neto de comisiones):")
    print(f"    Capital inicial: ${perf['initial_capital']:>10,.2f}")
    print(f"    Capital final:   ${perf['final_value']:>10,.2f}")
    print(f"    Return total:    {perf['total_return_pct']:>+9.2f}%")
    print(f"    Max Drawdown:    {perf['max_drawdown_pct']:>9.2f}%")
    print(f"    Sharpe Ratio:    {perf['sharpe_ratio']:>9.2f}")

    print(f"\n  TRADING:")
    print(f"    Compras / Ventas:   {trade['total_buys']} / {trade['total_sells']}")
    print(f"    Win Rate:           {trade['win_rate_pct']:.1f}%")
    print(f"    Stop Losses:        {trade['stop_loss_count']}")
    print(f"    Comisiones pagadas: ${costs['total_transaction_costs']:,.2f}")
    if trade.get("circuit_breaker_paused_days", 0) > 0:
        print(f"    Circuit Breaker:    {trade['circuit_breaker_paused_days']} días pausado")

    hedge = m.get("hedge", {})
    if hedge.get("trades", 0) > 0:
        sign = "+" if hedge["pnl"] >= 0 else ""
        print(f"    Hedge ({hedge.get('ticker','PSQ')}):  {hedge['trades']} ops | P&L: {sign}${hedge['pnl']:,.2f}")

    if reg:
        days  = reg.get("days", {})
        buys  = reg.get("buys", {})
        total = sum(days.values()) or 1
        print(f"\n  RÉGIMEN DE MERCADO (SPY):")
        for r in ("BULLISH", "NEUTRAL", "BEAR_RALLY", "BEARISH"):
            d = days.get(r, 0)
            b = buys.get(r, 0)
            print(f"    {r:12s}: {d:4d} días ({d/total*100:5.1f}%) | {b:3d} compras")

    print(f"\n  COMPARACIÓN:")
    bot = comp["bot_return_pct"]
    spy = comp["spy_return_pct"]
    bnh = comp["buyhold_return_pct"]
    diff_spy = comp["bot_vs_spy_diff"]
    diff_bnh = comp["bot_vs_buyhold_diff"]

    mark_spy = "✅ SUPERA SPY" if diff_spy > 0 else "❌ POR DEBAJO DE SPY"
    mark_bnh = "✅ SUPERA B&H" if diff_bnh > 0 else "❌ POR DEBAJO DE B&H"

    print(f"    Bot:              {bot:>+8.2f}%")
    print(f"    SPY:              {spy:>+8.2f}%   Bot vs SPY: {diff_spy:+.2f}pp  {mark_spy}")
    print(f"    Buy & Hold:       {bnh:>+8.2f}%   Bot vs B&H: {diff_bnh:+.2f}pp  {mark_bnh}")

    return {
        "name": name,
        "bot": bot,
        "spy": spy,
        "buyhold": bnh,
        "diff_spy": diff_spy,
        "beats_spy": diff_spy > 0,
        "max_drawdown": perf["max_drawdown_pct"],
        "sharpe": perf["sharpe_ratio"],
        "win_rate": trade["win_rate_pct"],
    }


def main():
    print(f"\n{SEP}")
    print("  BENCHMARK TEST: BOT vs SPY")
    print(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(SEP)

    results = []
    for test in TESTS:
        r = run_test(test["name"], test["range"])
        if r:
            results.append(r)

    if len(results) < 2:
        print("\n  No se obtuvieron suficientes resultados.")
        return

    print(f"\n{SEP}")
    print("  RESUMEN FINAL")
    print(SEP)
    print(f"  {'Año':<28} {'Bot':>8} {'SPY':>8} {'Diff':>8} {'¿Supera?':>12}")
    print(f"  {'-'*64}")
    all_beat = True
    for r in results:
        mark = "✅ SÍ" if r["beats_spy"] else "❌ NO"
        print(f"  {r['name']:<28} {r['bot']:>+7.2f}% {r['spy']:>+7.2f}% {r['diff_spy']:>+7.2f}pp {mark:>12}")
        if not r["beats_spy"]:
            all_beat = False

    print(f"\n  {SEP}")
    if all_beat:
        print("  🏆 El bot SUPERA al SPY en AMBOS escenarios.")
    else:
        print("  ⚠️  El bot NO supera al SPY en todos los escenarios.")
        print("      Revisa los parámetros de régimen y los indicadores técnicos.")
    print(f"  {SEP}\n")


if __name__ == "__main__":
    main()
