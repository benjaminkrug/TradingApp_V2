"""VALIDATION_PROTOCOL.md K2: what changes when the gate grades the rules
that would actually be traded?

Runs each strategy three ways over the same real bars and records every
result to the append-only results store (DECISIONS.md #8):

  1. reference engine  - what the OLD gate measured: no stop, no target,
     no session-end exit, one share per trade
  2. paper engine, intraday exit  - the real rules under the pre-21.09.2026
     version of DECISIONS.md #2
  3. paper engine, holding allowed - the real rules under the current
     DECISIONS.md #2

This implements K2 only. K3 (friction), K4 (block bootstrap), K5 (sample
size), K6 (regime consistency) and K7 (permutation test) are not applied
here, so nothing this script prints is a PASS - `verdict` is recorded as
None deliberately. The `t_naive` column in particular overstates
significance, because it treats clustered trades as independent.

Usage:
    cd backend
    PYTHONPATH=. python scripts/k2_engine_comparison.py [SYMBOL ...]
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
FEE_PER_SHARE = 0.005  # illustrative, not a confirmed decision - see PHASE9_NOTES.md
MAX_DAILY_LOSS = STARTING_EQUITY * 0.03  # same illustrative 3% as the Phase 9 demo
TIMEFRAME = "5Min"
CALENDAR_DAYS_BACK = 200
DATA_SOURCE = "alpaca/iex"  # free tier is IEX-only; see VALIDATION_PROTOCOL.md's data caveat

STRATEGIES = [
    ("VwapMomentum", lambda: VwapMomentumStrategy(), {"fast_period": 9, "slow_period": 20}),
    ("EmaPullback", lambda: EmaPullbackStrategy(), {"fast_period": 9, "slow_period": 20}),
    (
        "OpeningRangeBreakout",
        lambda: OpeningRangeBreakoutStrategy(),
        {"range_bars": 6, "volume_confirmation_multiple": 1.0},
    ),
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
        f"{'strategy':22s} {'sym':5s} {'rules':24s} {'trades':>7s} {'mean_bp':>9s} "
        f"{'t_naive':>8s} {'win%':>6s} {'overnight':>10s} {'maxhold_d':>10s}"
    )
    print(header)
    print("-" * len(header))

    for symbol in symbols:
        bars = provider.get_bars(symbol, start=start, end=end, timeframe=TIMEFRAME)
        if not bars:
            print(f"{symbol}: no bars returned, skipped")
            continue

        for name, factory, params in STRATEGIES:
            evaluations = {
                "paper, intraday exit": evaluate(
                    bars=bars,
                    strategy_factory=factory,
                    strategy_name=name,
                    starting_equity=STARTING_EQUITY,
                    risk_pct=RISK_PCT,
                    fee_per_share=FEE_PER_SHARE,
                    max_daily_loss=MAX_DAILY_LOSS,
                    flatten_at_session_end=True,
                ),
                "paper, holding allowed": evaluate(
                    bars=bars,
                    strategy_factory=factory,
                    strategy_name=name,
                    starting_equity=STARTING_EQUITY,
                    risk_pct=RISK_PCT,
                    fee_per_share=FEE_PER_SHARE,
                    max_daily_loss=MAX_DAILY_LOSS,
                    flatten_at_session_end=False,
                ),
            }

            rows = [("reference (old gate)", evaluations["paper, intraday exit"].reference_stats, "reference")]
            rows += [(label, ev.paper_stats, "paper") for label, ev in evaluations.items()]

            for label, stats, engine in rows:
                print(
                    f"{name:22s} {symbol:5s} {label:24s} {stats.trade_count:7d} {stats.mean_bp:+9.2f} "
                    f"{stats.t_stat_naive:+8.2f} {stats.win_rate * 100:6.1f} "
                    f"{stats.overnight_share * 100:9.0f}% {stats.max_holding_days:10.1f}"
                )
                record_run(
                    RunRecord(
                        strategy=name,
                        strategy_params={**params, "rules": label},
                        symbols=[symbol],
                        data_start=str(start),
                        data_end=str(end),
                        timeframe=TIMEFRAME,
                        data_source=DATA_SOURCE,
                        engine=engine,
                        metrics={
                            "trade_count": stats.trade_count,
                            "mean_bp": stats.mean_bp,
                            "stdev_bp": stats.stdev_bp,
                            "t_stat_naive": stats.t_stat_naive,
                            "win_rate": stats.win_rate,
                            "total_pnl": stats.total_pnl,
                            "overnight_share": stats.overnight_share,
                            "max_holding_days": stats.max_holding_days,
                            "median_holding_hours": stats.median_holding_hours,
                            "buy_and_hold_bp": evaluations["paper, intraday exit"].buy_and_hold_bp.get(symbol),
                            "session_count": evaluations["paper, intraday exit"].session_count,
                        },
                        verdict=None,  # K2 only - the full protocol is not implemented yet
                        note="K2 engine comparison; K3-K7 not applied, t_stat_naive overstates significance",
                    )
                )
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
