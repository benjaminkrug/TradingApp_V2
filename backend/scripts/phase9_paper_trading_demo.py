"""Runs the paper-trading engine (app/paper/engine.py) against synthetic
(NOT real market) demo data for a handful of universe symbols, and prints
the resulting portfolio state and trade metrics. This is what
PHASE9_NOTES.md's numbers come from - run it yourself to reproduce them
exactly (fixed seed, same synthetic generator as the Phase 8 API):

    cd backend && PYTHONPATH=. python3 scripts/phase9_paper_trading_demo.py

(PYTHONPATH=. is required - see phase7_synthetic_gate_run.py's docstring
for why.)

Uses DECISIONS.md's now-confirmed #4 (Alpaca as the eventual real
provider - FakeProvider stands in for it here), #5 (0.25% risk per trade)
and #7 (50,000 USD simulated starting equity). Like every other synthetic
demo run in this codebase (scripts/phase7_synthetic_gate_run.py), this
does not claim any strategy is profitable - it demonstrates that the
engine runs correctly end-to-end and reports whatever comes out, honestly.
"""

from __future__ import annotations

from datetime import date

from app.api.demo_data import generate_demo_bars
from app.data.point_in_time import Bar
from app.data.providers.fake import FakeProvider
from app.paper.engine import run_paper_trading
from app.strategies.vwap_momentum import VwapMomentumStrategy
from app.validation.metrics import compute_metrics, trades_from_fills

SYMBOLS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"]
NUM_TRADING_DAYS = 15
RISK_PCT = 0.0025  # DECISIONS.md #5, confirmed 13.08.2026
STARTING_EQUITY = 50_000.0  # DECISIONS.md #7, confirmed 13.08.2026
FEE_PER_SHARE = 0.005  # illustrative, not a confirmed decision - see PHASE9_NOTES.md


def _bars_by_symbol() -> dict[str, list[Bar]]:
    return {symbol: generate_demo_bars(symbol, num_trading_days=NUM_TRADING_DAYS) for symbol in SYMBOLS}


def main() -> None:
    bars_by_symbol = _bars_by_symbol()
    provider = FakeProvider(bars_by_symbol)
    start = min(b.timestamp.date() for bars in bars_by_symbol.values() for b in bars)
    end = max(b.timestamp.date() for bars in bars_by_symbol.values() for b in bars)

    result = run_paper_trading(
        provider=provider,
        symbols=SYMBOLS,
        strategy_factory=lambda: VwapMomentumStrategy(),
        strategy_name="vwap_momentum",
        start=start,
        end=end,
        timeframe="5Min",
        starting_equity=STARTING_EQUITY,
        risk_pct=RISK_PCT,
        fee_per_share=FEE_PER_SHARE,
        max_daily_loss=STARTING_EQUITY * 0.03,  # illustrative 3%/day kill-switch, not a confirmed decision
    )

    # trades_from_fills() expects a single symbol's fills in order (see its
    # own docstring/ValueError) - portfolio.fills interleaves every traded
    # symbol, so group by symbol first rather than passing the mixed list
    # straight through (caught by trades_from_fills's own pyramiding check
    # when this script first ran with the mixed list directly).
    fills_by_symbol: dict[str, list] = {}
    for fill in result.portfolio.fills:
        fills_by_symbol.setdefault(fill.symbol, []).append(fill)
    trades = [trade for fills in fills_by_symbol.values() for trade in trades_from_fills(fills)]
    metrics = compute_metrics(trades)

    print(f"Symbols: {SYMBOLS}")
    print(f"Period: {start} .. {end} ({NUM_TRADING_DAYS} trading days each, synthetic demo data)")
    print(f"Starting equity: {STARTING_EQUITY:.2f}")
    print(f"Ending cash: {result.portfolio.cash:.2f}")
    print(f"Open positions at end: {list(result.portfolio.positions.keys())}")
    print(f"Total fills: {len(result.portfolio.fills)}")
    print(f"Orders rejected for insufficient buying power: {result.portfolio.rejected_orders}")
    print(f"Daily loss guard tripped at end: {not result.daily_loss_guard.can_trade()}")
    print()
    print(f"Trade count: {metrics.trade_count}")
    print(f"Win rate: {metrics.win_rate:.2%}")
    print(f"Total PnL: {metrics.total_pnl:.2f}")
    print(f"Expectancy: {metrics.expectancy:.4f}")
    print(f"Max consecutive losses: {metrics.max_consecutive_losses}")


if __name__ == "__main__":
    main()
