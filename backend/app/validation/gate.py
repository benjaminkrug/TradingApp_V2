"""The 12-point checklist (ROADMAP.md Abschnitt 15) as an automated gate.

Deliberately does NOT claim to automate all 12 points. Several genuinely
cannot be checked yet with what exists in this codebase (survivorship
bias provenance, realistic slippage/execution, market-regime coverage,
paper-trading confirmation) — those come back `NOT_AUTOMATED` with a
reason, rather than being silently skipped or faked as passing. A
`GateReport` is honest about its own coverage on purpose: a checklist
that quietly can't check half its items but still shows all-green would
be worse than the loose, un-automated checklist it replaced.

`GateReport.passed` is True only if none of the checks that *could* run
failed. It says nothing about the `NOT_AUTOMATED` items — check
`fully_automated` if you need to know whether every point was actually
covered.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from app.backtest.reference_engine import run_reference_backtest
from app.data.point_in_time import Bar
from app.validation.leakage import StrategyFactory, detect_leakage
from app.validation.metrics import compute_metrics, trades_from_fills
from app.validation.monte_carlo import bootstrap_max_drawdowns, percentile
from app.validation.walk_forward import WalkForwardWindow

Status = Literal["PASS", "FAIL", "NOT_AUTOMATED"]


@dataclass(frozen=True)
class GateCheckResult:
    name: str
    status: Status
    detail: str


@dataclass(frozen=True)
class GateReport:
    results: list[GateCheckResult]

    @property
    def passed(self) -> bool:
        return not any(r.status == "FAIL" for r in self.results)

    @property
    def fully_automated(self) -> bool:
        return not any(r.status == "NOT_AUTOMATED" for r in self.results)


def evaluate_candidate(
    *,
    bars: list[Bar],
    strategy_factory: StrategyFactory,
    fee_per_share: float,
    leakage_cut_index: int,
    min_trades: int = 30,
    oos_bars: Optional[list[Bar]] = None,
    walk_forward_test_windows: Optional[list[WalkForwardWindow]] = None,
    monte_carlo_drawdown_threshold: Optional[float] = None,
    monte_carlo_samples: int = 1000,
    monte_carlo_seed: Optional[int] = None,
) -> GateReport:
    results: list[GateCheckResult] = []

    in_sample_result = run_reference_backtest(bars, strategy_factory(), fee_per_share=fee_per_share)
    in_sample_trades = trades_from_fills(in_sample_result.fills)
    in_sample_metrics = compute_metrics(in_sample_trades)

    # 1 + 2: look-ahead bias / data leakage - same underlying check
    leakage_report = detect_leakage(bars, strategy_factory, cut_index=leakage_cut_index, fee_per_share=fee_per_share)
    results.append(
        GateCheckResult(
            "no_lookahead_or_leakage",
            "PASS" if leakage_report.clean else "FAIL",
            "no mismatches detected"
            if leakage_report.clean
            else f"{len(leakage_report.mismatches)} mismatch(es) between full and truncated runs",
        )
    )

    # 3: survivorship bias - not checkable from a backtest result alone
    results.append(
        GateCheckResult(
            "no_survivorship_bias",
            "NOT_AUTOMATED",
            "requires universe-selection provenance, not derivable from a single backtest result. "
            "Verify manually that `bars` came from PointInTimeUniverse.as_of(...) (Phase 3), not a static/current universe.",
        )
    )

    # 4: fees. This only checks that a non-zero fee was assumed at all -
    # it cannot judge whether fee_per_share is itself a realistic amount
    # for the traded instrument, that's a manual/domain judgment.
    results.append(
        GateCheckResult(
            "realistic_fees",
            "PASS" if fee_per_share > 0 else "FAIL",
            f"fee_per_share={fee_per_share} (checks only that a non-zero fee was assumed, "
            "not whether this specific amount is realistic)",
        )
    )

    # 5: slippage - no model exists yet
    results.append(
        GateCheckResult(
            "realistic_slippage",
            "NOT_AUTOMATED",
            "no slippage model exists yet - see PHASE2_NOTES.md / ROADMAP.md Abschnitt 9",
        )
    )

    # 6: execution realism - reference_engine is explicitly a correctness oracle, not the product
    results.append(
        GateCheckResult(
            "realistic_execution",
            "NOT_AUTOMATED",
            "reference_engine.py is a correctness oracle (next-bar-open fills, single unit, "
            "no partial fills or market impact), not the production engine - see its own docstring",
        )
    )

    # 7: sufficient trades
    results.append(
        GateCheckResult(
            "sufficient_trades",
            "PASS" if in_sample_metrics.trade_count >= min_trades else "FAIL",
            f"{in_sample_metrics.trade_count} trades (minimum {min_trades})",
        )
    )

    # 8: OOS positive
    if oos_bars is not None:
        oos_result = run_reference_backtest(oos_bars, strategy_factory(), fee_per_share=fee_per_share)
        oos_metrics = compute_metrics(trades_from_fills(oos_result.fills))
        results.append(
            GateCheckResult(
                "oos_positive",
                "PASS" if oos_metrics.expectancy > 0 else "FAIL",
                f"OOS expectancy={oos_metrics.expectancy:.4f} over {oos_metrics.trade_count} trades",
            )
        )
    else:
        results.append(GateCheckResult("oos_positive", "NOT_AUTOMATED", "no oos_bars supplied"))

    # 9: walk-forward stability
    if walk_forward_test_windows:
        window_expectancies = []
        for window in walk_forward_test_windows:
            window_result = run_reference_backtest(window.test, strategy_factory(), fee_per_share=fee_per_share)
            window_expectancies.append(compute_metrics(trades_from_fills(window_result.fills)).expectancy)
        profitable = sum(1 for e in window_expectancies if e > 0)
        share_profitable = profitable / len(window_expectancies)
        results.append(
            GateCheckResult(
                "walk_forward_stable",
                "PASS" if share_profitable >= 0.5 else "FAIL",
                f"{profitable}/{len(window_expectancies)} test windows profitable",
            )
        )
    else:
        results.append(GateCheckResult("walk_forward_stable", "NOT_AUTOMATED", "no walk_forward_test_windows supplied"))

    # 10: Monte Carlo. Threshold and drawdowns are both <= 0 by convention
    # (see monte_carlo.max_drawdown) - "acceptable" means not worse than
    # (i.e. >=) the threshold.
    if monte_carlo_drawdown_threshold is not None and in_sample_trades:
        pnls = [t.pnl for t in in_sample_trades]
        drawdowns = bootstrap_max_drawdowns(pnls, num_samples=monte_carlo_samples, seed=monte_carlo_seed)
        worst_5pct = percentile(drawdowns, 5)
        results.append(
            GateCheckResult(
                "monte_carlo_acceptable",
                "PASS" if worst_5pct >= monte_carlo_drawdown_threshold else "FAIL",
                f"5th percentile bootstrap drawdown={worst_5pct:.2f} (threshold={monte_carlo_drawdown_threshold})",
            )
        )
    else:
        results.append(
            GateCheckResult(
                "monte_carlo_acceptable",
                "NOT_AUTOMATED",
                "no monte_carlo_drawdown_threshold supplied, or no in-sample trades to resample",
            )
        )

    # 11: multiple market regimes - no regime detection exists yet
    results.append(
        GateCheckResult(
            "multiple_regimes_tested",
            "NOT_AUTOMATED",
            "no market regime detection exists yet - planned for Phase 6+",
        )
    )

    # 12: paper trading confirmation - doesn't exist yet
    results.append(
        GateCheckResult(
            "paper_trading_confirmed",
            "NOT_AUTOMATED",
            "paper trading does not exist yet - Phase 9",
        )
    )

    return GateReport(results=results)
