"""OVERNIGHT_SELECTION_PROTOCOL.md — the actual test run.

Loads cached S&P 500 daily bars (scripts/fetch_sp500_daily_bars.py must
have run first), builds the daily volume-based selection, constructs
overnight trades (close of day N -> open of day N+1) for the selected
names, and applies K3/K4/K5/K6 (reusing the already-verified
app/validation/criteria.py machinery) plus the new selection-vs-random
permutation test from app/validation/overnight_selection.py.

Two declared configurations are run, not one picked after the fact:
top-20 and top-5 by relative volume (see the protocol for why both).

This is exploratory in the sense that it is the first run against real
data, but every parameter, criterion and the two configurations were
fixed in OVERNIGHT_SELECTION_PROTOCOL.md before this script existed.

Usage:
    cd backend
    PYTHONPATH=. python scripts/overnight_selection_analysis.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from app.data.point_in_time import Bar
from app.validation.criteria import (
    MIN_OOS_PERIODS,
    MIN_TRADES_PER_FOLD,
    MIN_TRADES_TOTAL,
    MIN_T_STAT,
    REFERENCE_FRICTION_BP,
    cluster_bootstrap,
    net_mean_bp,
    split_into_periods,
)
from app.validation.metrics import Trade
from app.validation.overnight_selection import (
    DailyBars,
    eligible_symbols_by_day,
    overnight_returns_by_day,
    select_top_by_relative_volume,
    selection_vs_random_permutation_test,
)
from app.validation.results_store import RunRecord, record_run

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_ROOT / "backend" / "data_cache" / "daily_bars_split_adjusted"

LOOKBACK = 20  # trading days, relative-volume baseline
MIN_PRICE = 5.0
CONFIGS = [("top20", 20), ("top5", 5)]  # both declared in the protocol, neither picked after seeing results
DATA_SOURCE = "alpaca/iex"


def load_all_daily_bars() -> dict[str, DailyBars]:
    out: dict[str, DailyBars] = {}
    for path in sorted(CACHE_DIR.glob("*.json")):
        symbol = path.stem
        raw = json.loads(path.read_text(encoding="utf-8"))
        if len(raw) < LOOKBACK + 5:
            continue  # too little history to ever be eligible, not worth carrying around
        bars = [
            Bar(symbol=r["symbol"], timestamp=datetime.fromisoformat(r["t"]), open=r["o"], high=r["h"],
                low=r["l"], close=r["c"], volume=r["v"])
            for r in raw
        ]
        out[symbol] = DailyBars(symbol, bars)
    return out


def build_trades_for_selection(
    selected_by_day, daily_bars_by_symbol: dict[str, DailyBars]
) -> list[Trade]:
    """One Trade per (day, selected symbol): entry at that day's close,
    exit at the next available day's open for that symbol."""
    bars_by_symbol_and_date = {
        sym: {b.timestamp.date(): (i, b) for i, b in enumerate(d.bars)} for sym, d in daily_bars_by_symbol.items()
    }
    trades: list[Trade] = []
    for day, symbols in selected_by_day.items():
        for sym in symbols:
            date_index = bars_by_symbol_and_date.get(sym)
            if date_index is None or day not in date_index:
                continue
            i, entry_bar = date_index[day]
            bars = daily_bars_by_symbol[sym].bars
            if i + 1 >= len(bars):
                continue
            exit_bar = bars[i + 1]
            trades.append(Trade(
                symbol=sym, entry_time=entry_bar.timestamp, exit_time=exit_bar.timestamp,
                entry_price=entry_bar.close, exit_price=exit_bar.open, quantity=1.0,
                pnl=exit_bar.open - entry_bar.close,
            ))
    return sorted(trades, key=lambda t: t.entry_time)


def run_config(name: str, top_n: int, daily_bars_by_symbol: dict[str, DailyBars]) -> None:
    print(f"\n===== Config: {name} (top {top_n} by {LOOKBACK}-day relative volume) =====")

    selected_by_day = select_top_by_relative_volume(daily_bars_by_symbol, lookback=LOOKBACK, top_n=top_n, min_price=MIN_PRICE)
    eligible_by_day = eligible_symbols_by_day(daily_bars_by_symbol, lookback=LOOKBACK, min_price=MIN_PRICE)
    returns_by_day = overnight_returns_by_day(daily_bars_by_symbol)

    trades = build_trades_for_selection(selected_by_day, daily_bars_by_symbol)
    print(f"  {len(trades)} trades across {len(selected_by_day)} trading days")

    if not trades:
        print("  no trades - skipping criteria")
        return

    gross = net_mean_bp(trades, 0.0)
    net = net_mean_bp(trades, REFERENCE_FRICTION_BP)
    print(f"  K3: gross={gross:+.2f}bp  net@{REFERENCE_FRICTION_BP}bp={net:+.2f}bp  "
          f"{'PASS' if net > 0 else 'FAIL'}"
          + ("  FRAGILE (breakeven<4bp)" if 0 < gross < 4 else ""))

    boot = cluster_bootstrap(trades, friction_bp=REFERENCE_FRICTION_BP, samples=10_000, seed=12345)
    print(f"  K4: day-block bootstrap t={boot.t_stat:+.2f} (need >={MIN_T_STAT}), p={boot.p_value:.4f}, "
          f"over {boot.day_count} trading days -> {'PASS' if boot.t_stat >= MIN_T_STAT else 'FAIL'}")

    periods = split_into_periods(trades, MIN_OOS_PERIODS)
    per_period_counts = [len(p) for p in periods]
    enough_total = len(trades) >= MIN_TRADES_TOTAL
    enough_per_fold = bool(periods) and all(c >= MIN_TRADES_PER_FOLD for c in per_period_counts)
    print(f"  K5: {len(trades)} total (need >={MIN_TRADES_TOTAL}), per period {per_period_counts} "
          f"(need >={MIN_TRADES_PER_FOLD} each) -> {'PASS' if enough_total and enough_per_fold else 'FAIL'}")

    if periods:
        period_nets = [net_mean_bp(p, REFERENCE_FRICTION_BP) for p in periods]
        all_positive = all(m > 0 for m in period_nets)
        print(f"  K6: net by period {[round(m, 2) for m in period_nets]} -> "
              f"{'PASS' if all_positive else 'FAIL'} (spans {len(periods)} calendar sub-periods)")
    else:
        print("  K6: not enough calendar span to split")

    perm = selection_vs_random_permutation_test(
        selected_by_day, eligible_by_day, returns_by_day, permutations=10_000, seed=12345
    )
    print(f"  K-neu (selection vs. random): observed={perm.observed_mean_bp:+.2f}bp, p={perm.p_value:.4f} "
          f"(need <0.05), random selection matched/beat real in {perm.better_or_equal}/{perm.permutations} draws "
          f"-> {'PASS' if perm.p_value < 0.05 else 'FAIL'}")

    record_run(RunRecord(
        strategy="OvernightSelection",
        strategy_params={"config": name, "top_n": top_n, "lookback_days": LOOKBACK, "min_price": MIN_PRICE},
        symbols=sorted(daily_bars_by_symbol.keys()),
        data_start=str(min(selected_by_day)) if selected_by_day else "",
        data_end=str(max(selected_by_day)) if selected_by_day else "",
        timeframe="1Day",
        data_source=DATA_SOURCE,
        engine="overnight_selection",
        metrics={
            "trade_count": len(trades), "gross_mean_bp": gross, "net_mean_bp": net,
            "bootstrap_t": boot.t_stat, "bootstrap_p": boot.p_value, "trading_days": boot.day_count,
            "per_period_counts": per_period_counts,
            "selection_permutation_p": perm.p_value, "selection_observed_bp": perm.observed_mean_bp,
        },
        verdict=None,  # printed per-criterion above; not composed into one PASS/FAIL yet
        note="OVERNIGHT_SELECTION_PROTOCOL.md first real-data run, S&P 500 (survivorship-biased, K8 unresolved)",
    ))


def main() -> int:
    if not CACHE_DIR.exists() or not any(CACHE_DIR.glob("*.json")):
        print(f"No cached data in {CACHE_DIR} - run scripts/fetch_sp500_daily_bars.py first.")
        return 1

    daily_bars_by_symbol = load_all_daily_bars()
    print(f"Loaded {len(daily_bars_by_symbol)} symbols with sufficient history.")

    for name, top_n in CONFIGS:
        run_config(name, top_n, daily_bars_by_symbol)

    return 0


if __name__ == "__main__":
    sys.exit(main())
