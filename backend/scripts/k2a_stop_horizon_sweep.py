"""VALIDATION_PROTOCOL.md K2a: the declared stop-horizon grid.

Runs every strategy over three stop volatility horizons (ATR measured on
the strategy's own 5-minute bars, on hourly bars, on daily bars) with the
20% position cap applied and multi-day holding permitted (DECISIONS.md #2
as of 21.09.2026).

This is explicitly NOT a search for the best horizon. The decision rule
was fixed in VALIDATION_PROTOCOL.md before any of these numbers existed:
a result only counts if it survives at two adjacent grid points, and a
candidate that works at exactly one setting is recorded as fragile and
fails. Printing all three is how fragility becomes visible.

Still not a PASS: K3-K7 are not implemented, so `verdict` stays None and
the t-statistic shown is the naive one, which overstates significance.

Usage:
    cd backend
    PYTHONPATH=. python scripts/k2a_stop_horizon_sweep.py [SYMBOL ...]
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

from app.data.providers.alpaca import AlpacaProvider
from app.strategies.ema_pullback import EmaPullbackStrategy
from app.strategies.opening_range_breakout import OpeningRangeBreakoutStrategy
from app.strategies.vwap_momentum import VwapMomentumStrategy
from app.validation.evaluate import evaluate
from app.validation.results_store import RunRecord, record_run

STARTING_EQUITY = 50_000.0  # DECISIONS.md #7
RISK_PCT = 0.0025  # DECISIONS.md #5
MAX_POSITION_PCT = 0.20  # VALIDATION_PROTOCOL.md K2a, fixed by principle, not tested
FEE_PER_SHARE = 0.005
MAX_DAILY_LOSS = STARTING_EQUITY * 0.03
TIMEFRAME = "5Min"
CALENDAR_DAYS_BACK = 200
DATA_SOURCE = "alpaca/iex"
HORIZONS = ["bar", "hour", "day"]  # the declared grid; adjacency is in this order

STRATEGIES = [
    ("VwapMomentum", lambda: VwapMomentumStrategy()),
    ("EmaPullback", lambda: EmaPullbackStrategy()),
    ("OpeningRangeBreakout", lambda: OpeningRangeBreakoutStrategy()),
]


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() and key.strip() not in os.environ:
            os.environ[key.strip()] = value.strip()


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    _load_dotenv(repo_root / ".env")
    api_key = os.environ.get("ALPACA_API_KEY", "")
    api_secret = os.environ.get("ALPACA_SECRET_KEY", "")
    if not api_key or not api_secret:
        print("ALPACA_API_KEY / ALPACA_SECRET_KEY not set - fill them into .env first.")
        return 1

    symbols = sys.argv[1:] or ["AAPL", "MSFT", "NVDA"]
    end = date.today()
    start = end - timedelta(days=CALENDAR_DAYS_BACK)
    provider = AlpacaProvider(api_key=api_key, api_secret=api_secret, timeout=60.0)

    header = (
        f"{'strategy':22s} {'sym':5s} {'stop horizon':13s} {'trades':>7s} {'mean_bp':>9s} "
        f"{'t_naive':>8s} {'win%':>6s} {'avg_notional%':>14s}"
    )
    print(header)
    print("-" * len(header))

    positive_at: dict[tuple[str, str], list[str]] = {}

    for symbol in symbols:
        bars = provider.get_bars(symbol, start=start, end=end, timeframe=TIMEFRAME)
        if not bars:
            print(f"{symbol}: no bars returned, skipped")
            continue

        for name, factory in STRATEGIES:
            for horizon in HORIZONS:
                ev = evaluate(
                    bars=bars,
                    strategy_factory=factory,
                    strategy_name=name,
                    starting_equity=STARTING_EQUITY,
                    risk_pct=RISK_PCT,
                    fee_per_share=FEE_PER_SHARE,
                    max_daily_loss=MAX_DAILY_LOSS,
                    flatten_at_session_end=False,
                    atr_horizon=horizon,
                    max_position_pct=MAX_POSITION_PCT,
                )
                stats = ev.paper_stats
                avg_notional_pct = (
                    sum(t.entry_price * t.quantity for t in ev.paper_trades)
                    / len(ev.paper_trades)
                    / STARTING_EQUITY
                    * 100
                    if ev.paper_trades
                    else 0.0
                )
                print(
                    f"{name:22s} {symbol:5s} {horizon:13s} {stats.trade_count:7d} {stats.mean_bp:+9.2f} "
                    f"{stats.t_stat_naive:+8.2f} {stats.win_rate * 100:6.1f} {avg_notional_pct:13.1f}%"
                )
                if stats.mean_bp > 0:
                    positive_at.setdefault((name, symbol), []).append(horizon)

                record_run(
                    RunRecord(
                        strategy=name,
                        strategy_params={
                            "atr_horizon": horizon,
                            "max_position_pct": MAX_POSITION_PCT,
                            "flatten_at_session_end": False,
                        },
                        symbols=[symbol],
                        data_start=str(start),
                        data_end=str(end),
                        timeframe=TIMEFRAME,
                        data_source=DATA_SOURCE,
                        engine="paper",
                        metrics={
                            "trade_count": stats.trade_count,
                            "mean_bp": stats.mean_bp,
                            "stdev_bp": stats.stdev_bp,
                            "t_stat_naive": stats.t_stat_naive,
                            "win_rate": stats.win_rate,
                            "total_pnl": stats.total_pnl,
                            "overnight_share": stats.overnight_share,
                            "max_holding_days": stats.max_holding_days,
                            "avg_notional_pct_of_equity": avg_notional_pct,
                            "buy_and_hold_bp": ev.buy_and_hold_bp.get(symbol),
                        },
                        verdict=None,  # K2a only; K3-K7 not implemented
                        note="K2a stop-horizon grid, 20% position cap, holding allowed",
                    )
                )
        print()

    print("Two-neighbour check (VALIDATION_PROTOCOL.md K2a) - PROVISIONAL FORM")
    print("  K2a's rule is that a candidate must survive at two adjacent grid points.")
    print("  'Surviving' is supposed to mean passing the full criteria, but K3-K7 do not")
    print("  exist yet, so all this can test right now is whether the mean is positive -")
    print("  a much weaker bar that almost anything clears. Do not read it as a pass.")
    adjacent = {("bar", "hour"), ("hour", "day")}
    for (name, symbol), horizons in sorted(positive_at.items()):
        pairs = {(a, b) for a in horizons for b in horizons if (a, b) in adjacent}
        status = "positive at adjacent points" if pairs else "FRAGILE - single grid point only"
        print(f"  {name:22s} {symbol:5s} positive at {horizons} -> {status}")
    if not positive_at:
        print("  no strategy/symbol had a positive mean at any grid point")

    return 0


if __name__ == "__main__":
    sys.exit(main())
