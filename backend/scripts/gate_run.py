"""The full validation gate — every criterion in VALIDATION_PROTOCOL.md.

For each strategy x symbol x stop horizon: splits the data 70/30 into
in-sample and out-of-sample, runs the out-of-sample slice through the real
execution rules, and applies K1 and K3-K7. Records the verdict and every
underlying number to the append-only results store.

The verdict is deliberately strict (DECISIONS.md #8): a criterion that
could not be evaluated counts as not met, not as waived. Expect failures -
that is the apparatus working, and the per-criterion detail plus the
"days needed" estimate below are the useful output, not the PASS/FAIL flag.

Usage:
    cd backend
    PYTHONPATH=. python scripts/gate_run.py [SYMBOL ...]
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

from app.data.calendar import NY_TZ
from app.data.providers.alpaca import AlpacaProvider
from app.strategies.ema_pullback import EmaPullbackStrategy
from app.strategies.opening_range_breakout import OpeningRangeBreakoutStrategy
from app.strategies.vwap_momentum import VwapMomentumStrategy
from app.validation.criteria import REFERENCE_FRICTION_BP, cluster_bootstrap, evaluate_criteria
from app.validation.evaluate import evaluate
from app.validation.leakage import detect_leakage
from app.validation.oos import OosSplit
from app.validation.results_store import RunRecord, record_run

STARTING_EQUITY = 50_000.0
RISK_PCT = 0.0025
MAX_POSITION_PCT = 0.20
FEE_PER_SHARE = 0.005
MAX_DAILY_LOSS = STARTING_EQUITY * 0.03
TIMEFRAME = "5Min"
CALENDAR_DAYS_BACK = 200
DATA_SOURCE = "alpaca/iex"
HORIZONS = ["bar", "hour", "day"]
BOOTSTRAP_SAMPLES = 10_000
PERMUTATIONS = 10_000
OOS_FRACTION = 0.7

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


def days_needed_for_significance(trades, observed_days: int) -> str:
    """How much more history this candidate would need to reach t=2, holding
    its current effect size. The bootstrap standard error shrinks with the
    square root of the number of *days*, so the requirement scales as
    (2 / t_observed)^2. Reported because "not significant yet" and "not
    significant ever" are very different situations and the distinction is
    what decides whether buying more data is worth it."""
    if not trades or observed_days == 0:
        return "n/a"
    boot = cluster_bootstrap(trades, friction_bp=REFERENCE_FRICTION_BP, samples=2_000, seed=99)
    if boot.t_stat <= 0:
        return "never at this effect size (net edge is not positive)"
    factor = (2.0 / boot.t_stat) ** 2
    needed = observed_days * factor
    return f"~{needed:,.0f} trading days (~{needed / 252:.1f} years), {factor:.1f}x the current {observed_days}"


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

    passes = 0
    total = 0

    for symbol in symbols:
        all_bars = provider.get_bars(symbol, start=start, end=end, timeframe=TIMEFRAME)
        if not all_bars:
            print(f"{symbol}: no bars returned, skipped")
            continue

        split_index = int(len(all_bars) * OOS_FRACTION)
        cutoff = all_bars[split_index].timestamp.astimezone(NY_TZ).date()
        oos_split = OosSplit(all_bars, cutoff=cutoff)
        oos_split.unlock()  # the strategies are fixed; nothing was tuned on this slice
        oos_bars = oos_split.out_of_sample
        oos_days = len({b.timestamp.astimezone(NY_TZ).date() for b in oos_bars})

        print(f"\n===== {symbol} | OOS from {cutoff}: {len(oos_bars)} bars, {oos_days} trading days =====")

        for name, factory in STRATEGIES:
            leakage = detect_leakage(
                oos_bars, factory, cut_index=len(oos_bars) // 2, fee_per_share=FEE_PER_SHARE
            )

            for horizon in HORIZONS:
                total += 1
                ev = evaluate(
                    bars=oos_bars,
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
                verdict = evaluate_criteria(
                    ev.paper_trades,
                    {symbol: oos_bars},
                    leakage_clean=leakage.clean,
                    friction_bp=REFERENCE_FRICTION_BP,
                    bootstrap_samples=BOOTSTRAP_SAMPLES,
                    permutations=PERMUTATIONS,
                )
                if verdict.passed:
                    passes += 1

                print(f"\n  {name} / stop={horizon} -> {'PASS' if verdict.passed else 'FAIL'}")
                for r in verdict.results:
                    print(f"    [{r.status:14s}] {r.key}: {r.detail}")
                print(f"    data needed for t=2: {days_needed_for_significance(ev.paper_trades, oos_days)}")

                record_run(
                    RunRecord(
                        strategy=name,
                        strategy_params={
                            "atr_horizon": horizon,
                            "max_position_pct": MAX_POSITION_PCT,
                            "flatten_at_session_end": False,
                        },
                        symbols=[symbol],
                        data_start=str(cutoff),
                        data_end=str(end),
                        timeframe=TIMEFRAME,
                        data_source=DATA_SOURCE,
                        engine="paper",
                        metrics={
                            "trade_count": ev.paper_stats.trade_count,
                            "mean_bp_gross": ev.paper_stats.mean_bp,
                            "stdev_bp": ev.paper_stats.stdev_bp,
                            "t_stat_naive": ev.paper_stats.t_stat_naive,
                            "win_rate": ev.paper_stats.win_rate,
                            "oos_trading_days": oos_days,
                            "criteria": {r.key: {"status": r.status, "detail": r.detail} for r in verdict.results},
                        },
                        verdict="PASS" if verdict.passed else "FAIL",
                        note="full gate, VALIDATION_PROTOCOL.md K1+K3-K7, OOS slice only",
                    )
                )

    print(f"\n===== {passes} of {total} configurations passed the full protocol =====")
    return 0


if __name__ == "__main__":
    sys.exit(main())
