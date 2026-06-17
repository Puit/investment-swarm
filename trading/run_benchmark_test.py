"""
BENCHMARK TEST: Bot vs SPY — 2020 al 2026
==========================================

Ejecuta el backtest con GOOG y MSFT en cada año individual y el período
completo 2020-2026. El objetivo es que el bot:
  1. Siempre termine en positivo
  2. Siempre supere al SPY

Uso:
    cd investment-swarm
    venv/Scripts/python -m trading.run_benchmark_test

Nota: la primera ejecución llama al LLM para análisis fundamental.
Las siguientes reutilizan el caché en data/fundamental_cache.json.
"""

import sys
import logging
from datetime import date, datetime

# Silenciar logs de yfinance/crewai durante el test
for lib in ("yfinance", "openai", "httpx", "crewai"):
    logging.getLogger(lib).setLevel(logging.ERROR)

from trading.backtest_runner import BacktestRunner

# ── Configuración ────────────────────────────────────────────────
TICKERS  = ["GOOG", "MSFT"]
CAPITAL  = 10_000.0
TX_COST  = 0.001   # 0.1% por operación

# Años individuales + período completo
TESTS = [
    {"name": "2020  (COVID crash + recovery)", "range": "2020"},
    {"name": "2021  (Bull año completo)",       "range": "2021"},
    {"name": "2022  (Bear año completo)",       "range": "2022"},
    {"name": "2023  (Recovery)",                "range": "2023"},
    {"name": "2024  (Bull año completo)",       "range": "2024"},
    {"name": "2025  (Volatilidad / tarifas)",   "range": "2025"},
    {
        "name": "2020→2026 (período completo)",
        "range": "Custom",
        "custom_start": date(2020, 1, 1),
        "custom_end":   date(2026, 4, 30),
    },
]

SEP  = "=" * 72
SEP2 = "-" * 72


def run_test(cfg: dict) -> dict:
    name  = cfg["name"]
    rng   = cfg["range"]
    cust_s = cfg.get("custom_start")
    cust_e = cfg.get("custom_end")

    print(f"\n{SEP}")
    print(f"  {name}")
    print(f"  Tickers: {', '.join(TICKERS)}  |  Capital: ${CAPITAL:,.0f}")
    print(SEP)

    result = BacktestRunner.run_backtest(
        date_range=rng,
        initial_capital=CAPITAL,
        transaction_cost_pct=TX_COST,
        tickers=TICKERS,
        custom_start=cust_s,
        custom_end=cust_e,
        progress_callback=lambda msg: print(f"  >> {msg}"),
    )

    if not result["success"]:
        print(f"  ❌ ERROR: {result.get('error')}")
        return {"name": name, "error": True}

    m     = result["metrics"]
    perf  = m["performance"]
    comp  = m["comparison"]
    trade = m["trading"]
    costs = m["costs"]
    reg   = m.get("regime", {})

    print(f"\n  Período: {m['backtest_period']['start']} → {m['backtest_period']['end']}")

    print(f"\n  {'RENDIMIENTO (neto de comisiones)'}")
    print(f"  {'─'*40}")
    print(f"  Capital inicial : ${perf['initial_capital']:>10,.2f}")
    print(f"  Capital final   : ${perf['final_value']:>10,.2f}")
    print(f"  Return total    : {perf['total_return_pct']:>+9.2f}%")
    print(f"  Max Drawdown    : {perf['max_drawdown_pct']:>9.2f}%")
    print(f"  Sharpe Ratio    : {perf['sharpe_ratio']:>9.2f}")

    print(f"\n  {'ACTIVIDAD DE TRADING'}")
    print(f"  {'─'*40}")
    print(f"  Compras / Ventas: {trade['total_buys']} / {trade['total_sells']}")
    print(f"  Win Rate        : {trade['win_rate_pct']:.1f}%")
    print(f"  Stop Losses     : {trade['stop_loss_count']}")
    print(f"  Comisiones      : ${costs['total_transaction_costs']:,.2f}")
    if trade.get("circuit_breaker_paused_days", 0):
        print(f"  Circuit Breaker : {trade['circuit_breaker_paused_days']} días pausado")

    hedge = m.get("hedge", {})
    if hedge.get("trades", 0):
        sign = "+" if hedge["pnl"] >= 0 else ""
        print(f"  Hedge PSQ       : {hedge['trades']} ops | P&L: {sign}${hedge['pnl']:,.2f}")

    if reg:
        days  = reg.get("days", {})
        buys  = reg.get("buys", {})
        total = max(sum(days.values()), 1)
        print(f"\n  {'RÉGIMEN DE MERCADO (SPY)'}")
        print(f"  {'─'*40}")
        for r in ("BULLISH", "NEUTRAL", "BEAR_RALLY", "BEARISH"):
            d = days.get(r, 0)
            b = buys.get(r, 0)
            print(f"  {r:12s}: {d:4d} d ({d/total*100:4.0f}%) | {b:3d} compras")

    bot = comp["bot_return_pct"]
    spy = comp["spy_return_pct"]
    bnh = comp["buyhold_return_pct"]

    print(f"\n  {'COMPARACIÓN'}")
    print(f"  {'─'*40}")

    mark_spy = "✅ SUPERA SPY" if bot > spy else "❌ POR DEBAJO"
    mark_pos = "✅ POSITIVO"   if bot > 0   else "❌ NEGATIVO"

    print(f"  Bot  : {bot:>+8.2f}%   {mark_pos}  |  {mark_spy}")
    print(f"  SPY  : {spy:>+8.2f}%   (referencia)")
    print(f"  B&H  : {bnh:>+8.2f}%   (buy & hold {'/'.join(TICKERS)})")
    print(f"  Diff vs SPY: {bot-spy:+.2f} pp")

    # Tabla de trades abiertos
    if result.get("simulator") and result["simulator"].positions:
        sim = result["simulator"]
        print(f"\n  POSICIONES ABIERTAS AL CIERRE:")
        for tk, lots in sim.positions.items():
            for lot in lots:
                cur = sim.get_price_at_date(tk, sim.end_date) or lot["entry_price"]
                pnl_pct = (cur - lot["entry_price"]) / lot["entry_price"] * 100
                print(f"    {tk}: {lot['qty']} acc. entry={lot['entry_price']:.2f} "
                      f"now={cur:.2f} P&L={pnl_pct:+.1f}% "
                      f"({lot['conviction']})")

    return {
        "name":       name,
        "bot":        bot,
        "spy":        spy,
        "buyhold":    bnh,
        "diff_spy":   bot - spy,
        "beats_spy":  bot > spy,
        "positive":   bot > 0,
        "drawdown":   perf["max_drawdown_pct"],
        "sharpe":     perf["sharpe_ratio"],
        "win_rate":   trade["win_rate_pct"],
        "error":      False,
    }


def main():
    print(f"\n{SEP}")
    print("  BENCHMARK TEST: Bot vs SPY | GOOG + MSFT | 2020 → 2026")
    print(f"  Ejecutado: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(SEP)

    results = []
    for cfg in TESTS:
        r = run_test(cfg)
        results.append(r)

    # ── Resumen final ────────────────────────────────────────────
    print(f"\n{SEP}")
    print("  RESUMEN FINAL")
    print(SEP)

    header = f"  {'Período':<30} {'Bot':>8} {'SPY':>8} {'Diff':>8} {'Positivo':>10} {'Bate SPY':>10}"
    print(header)
    print(f"  {SEP2}")

    all_beats_spy = True
    all_positive  = True

    for r in results:
        if r.get("error"):
            print(f"  {r['name']:<30} {'ERROR':>8}")
            all_beats_spy = False
            all_positive  = False
            continue

        mark_spy = "✅" if r["beats_spy"] else "❌"
        mark_pos = "✅" if r["positive"]  else "❌"

        print(
            f"  {r['name']:<30} "
            f"{r['bot']:>+7.2f}% "
            f"{r['spy']:>+7.2f}% "
            f"{r['diff_spy']:>+7.2f}pp "
            f"{'Sí' if r['positive'] else 'No':>10} {mark_pos}"
            f"{'Sí' if r['beats_spy'] else 'No':>8} {mark_spy}"
        )

        if not r["beats_spy"]: all_beats_spy = False
        if not r["positive"]:  all_positive  = False

    print(f"\n  {SEP2}")

    if all_beats_spy and all_positive:
        print("  🏆 El bot SUPERA al SPY Y está en POSITIVO en TODOS los períodos.")
    else:
        issues = []
        if not all_positive:  issues.append("algunos períodos negativos")
        if not all_beats_spy: issues.append("algunos períodos por debajo del SPY")
        print(f"  ⚠️  Pendiente: {', '.join(issues)}")
        print("     Ajusta los parámetros de régimen / trailing stop / scoring.")

    print(f"\n  {SEP}\n")


if __name__ == "__main__":
    main()
