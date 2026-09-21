"""Runs the 3 manually-coded strategies (Phase 4: VwapMomentumStrategy,
EmaPullbackStrategy, OpeningRangeBreakoutStrategy) through the full
validation pipeline against REAL historical market data (Alpaca, IEX
feed) for the first time.

Why this exists: Phase 5/6/7 already built and hermetically verified this
exact pipeline (scripts/phase7_synthetic_gate_run.py) - but every gate run
before this one used synthetic/fake data, because AlpacaProvider was a
stub until 21.09.2026. That answered "does the pipeline work" (yes),
never "does any strategy actually hold up on markets that really
happened". This script is the first attempt at the second question.

Why this comes BEFORE forward testing, not after: ROADMAP.md's own
pipeline order is In-Sample -> Validation -> OOS -> Forward Test. Forward
testing (app/forward_test/session.py) is meant to *confirm* an
already-passed OOS/gate result over real elapsed time - there is nothing
to confirm from a strategy that has never passed on real data. See
CLAUDE.md's 21.09.2026 update for why this script was written before the
Phase C forward-test cron job, reversing the order CLAUDE.md previously
listed.

Like every gate run in this codebase, this does not decide whether a
strategy is "good" - it reports whatever the gate says, honestly. Both
Phase 7 strategies failed the gate on synthetic data; a FAIL here would
not be surprising and must be reported as such, not massaged.

Needs real Alpaca keys in .env. First run (21.09.2026, AAPL, 2026-03-05 to
2026-09-21, 11,459 real 5-Min bars) - result honestly reported in
PHASE3_NOTES.md / PHASE7_NOTES.md: VwapMomentumStrategy FAILED
(walk_forward_stable), EmaPullbackStrategy and OpeningRangeBreakoutStrategy
PASSED every automatable check. Re-run any time to check with a fresh date
range or a different symbol - results will differ as more/different real
data comes in.

Usage:
    cd backend
    PYTHONPATH=. python scripts/real_data_gate_run.py [SYMBOL]

Defaults to AAPL (first entry in app/signals/scanner.py's static
universe) if no symbol is given.
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

from app.data.point_in_time import Bar
from app.data.providers.alpaca import AlpacaProvider
from app.strategies.ema_pullback import EmaPullbackStrategy
from app.strategies.opening_range_breakout import OpeningRangeBreakoutStrategy
from app.strategies.vwap_momentum import VwapMomentumStrategy
from app.validation.gate import evaluate_candidate
from app.validation.leakage import detect_leakage
from app.validation.oos import OosSplit
from app.validation.walk_forward import walk_forward_windows

FEE_PER_SHARE = 0.005  # illustrative, not a confirmed decision - see PHASE9_NOTES.md
TIMEFRAME = "5Min"
CALENDAR_DAYS_BACK = 200  # targets 120+ trading days after weekends/holidays, matching phase7_synthetic_gate_run.py's synthetic run
MIN_TRADES = 10  # loosened from gate.py's default of 30, same precedent as phase7_synthetic_gate_run.py - the real count is printed either way, not hidden
WALK_FORWARD_TRAIN_DAYS = 40
WALK_FORWARD_TEST_DAYS = 10
WALK_FORWARD_STEP_DAYS = 10
MIN_BARS_TO_ATTEMPT = 50


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def _print_gate(name: str, report) -> None:
    print(f"\n=== {name} ===")
    for r in report.results:
        print(f"  [{r.status:13s}] {r.name}: {r.detail}")
    print(f"  passed={report.passed} fully_automated={report.fully_automated}")


def run_gate_for_symbol(symbol: str, all_bars: list[Bar], name: str, strategy_factory) -> None:
    if len(all_bars) < MIN_BARS_TO_ATTEMPT:
        print(
            f"\n=== {name} on {symbol} ===\n  SKIPPED - only {len(all_bars)} bars, "
            "too little data to split into in-sample/OOS/walk-forward windows meaningfully"
        )
        return

    split_index = int(len(all_bars) * 0.7)
    cutoff = all_bars[split_index].timestamp.date()

    # Standalone check on the full series, independent of the cut point
    # evaluate_candidate uses below - same belt-and-suspenders pattern as
    # phase7_synthetic_gate_run.py.
    leakage_report = detect_leakage(all_bars, strategy_factory, cut_index=len(all_bars) // 2, fee_per_share=FEE_PER_SHARE)
    print(f"\n{name} on {symbol}: leakage clean={leakage_report.clean} ({len(leakage_report.mismatches)} mismatches)")

    oos_split = OosSplit(all_bars, cutoff=cutoff)
    in_sample_bars = oos_split.in_sample
    oos_split.unlock()  # in-sample "development" is a fixed strategy here, not tuned against this run - unlocking is safe
    oos_bars = oos_split.out_of_sample

    wf_windows = walk_forward_windows(
        in_sample_bars,
        train_days=WALK_FORWARD_TRAIN_DAYS,
        test_days=WALK_FORWARD_TEST_DAYS,
        step_days=WALK_FORWARD_STEP_DAYS,
    )

    report = evaluate_candidate(
        bars=in_sample_bars,
        strategy_factory=strategy_factory,
        fee_per_share=FEE_PER_SHARE,
        leakage_cut_index=len(in_sample_bars) // 2,
        min_trades=MIN_TRADES,
        oos_bars=oos_bars,
        walk_forward_test_windows=wf_windows,
        # No monte_carlo_drawdown_threshold passed: what maximum drawdown
        # is "acceptable" is a risk-tolerance decision nobody has made yet
        # (no DECISIONS.md entry for it) - inventing a number here would
        # be exactly the kind of unconfirmed business decision this
        # project's own conventions say to escalate, not assume. Comes
        # back NOT_AUTOMATED.
    )
    _print_gate(f"{name} on {symbol}", report)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    _load_dotenv(repo_root / ".env")

    api_key = os.environ.get("ALPACA_API_KEY", "")
    api_secret = os.environ.get("ALPACA_SECRET_KEY", "")
    if not api_key or not api_secret:
        print(
            "ALPACA_API_KEY / ALPACA_SECRET_KEY not set (checked .env and the real "
            "environment). Fill them into .env in the repo root, then re-run this script."
        )
        return 1

    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    end = date.today()
    start = end - timedelta(days=CALENDAR_DAYS_BACK)

    print(f"Fetching {symbol} {TIMEFRAME} bars from {start} to {end} ...")
    provider = AlpacaProvider(api_key=api_key, api_secret=api_secret)
    try:
        bars = provider.get_bars(symbol, start=start, end=end, timeframe=TIMEFRAME)
    except PermissionError as exc:
        print(f"FAILED - Alpaca rejected the credentials: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001 - this script's whole job is to report the outcome
        print(f"FAILED - unexpected error fetching bars: {exc!r}")
        return 1

    print(f"Got {len(bars)} bars for {symbol}.")
    if not bars:
        print("No bars returned - nothing to validate. Try a longer date range or a different symbol.")
        return 1

    strategies = [
        ("VwapMomentumStrategy", lambda: VwapMomentumStrategy()),
        ("EmaPullbackStrategy", lambda: EmaPullbackStrategy()),
        ("OpeningRangeBreakoutStrategy", lambda: OpeningRangeBreakoutStrategy()),
    ]
    for strategy_name, factory in strategies:
        run_gate_for_symbol(symbol, bars, strategy_name, factory)

    return 0


if __name__ == "__main__":
    sys.exit(main())
