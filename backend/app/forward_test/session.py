"""Forward testing — ROADMAP.md Abschnitt 14/19: "mehrere Wochen,
idealerweise Monate, vor jedem Echtgeldeinsatz", at least 20 trades or
about 3 months (transcript `FbuYWdwA_wU` reference), confirming the
strategy's OOS backtest results before it goes anywhere near real money.

This is NOT another backtest. A backtest and Phase 9's paper-trading demo
both process a fixed, already-existing batch of bars in one call. A
forward test is defined by *real elapsed calendar time*: new bars arrive
as the market actually produces them, over days and weeks, and no amount
of code can compress that into a single function call without
misrepresenting what happened. `ForwardTestSession.ingest()` is built
around that: it is meant to be called repeatedly, once per new batch of
real-world data as it arrives (daily, say), accumulating state across
calls - never with the whole test's data handed over up front.

Reuses Phase 9's exact `PaperTradingEngine`/`Portfolio`/`DailyLossGuard` -
a forward test IS a paper-trading run, just one tracked over a required
minimum duration/trade count rather than a fixed demo window. No new
execution logic exists here, only tracking and a readiness check against
ROADMAP's explicit criterion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.data.point_in_time import Bar
from app.paper.engine import PaperTradingEngine, Strategy, StrategyFactory
from app.paper.portfolio import Portfolio
from app.signals.risk import DailyLossGuard
from app.validation.metrics import Metrics, compute_metrics, trades_from_fills


@dataclass(frozen=True)
class ForwardTestCriteria:
    """ROADMAP.md Abschnitt 14's own numbers - not invented here. `min_days`
    uses 90 as a plain-English "about 3 months", not a precise trading-day
    count; the roadmap does not specify one more precisely than that."""

    min_trades: int = 20
    min_days: float = 90.0


@dataclass(frozen=True)
class ForwardTestStatus:
    started_at: Optional[datetime]
    last_bar_at: Optional[datetime]
    elapsed_days: float
    metrics: Metrics
    trades_criterion_met: bool
    days_criterion_met: bool

    @property
    def ready_for_review(self) -> bool:
        """ROADMAP's "mindestens 20 Trades bzw. ca. 3 Monate" - "bzw."
        (or) means either threshold is sufficient, not both."""
        return self.trades_criterion_met or self.days_criterion_met


class ForwardTestSession:
    def __init__(
        self,
        symbols: list[str],
        strategy_factory: StrategyFactory,
        strategy_name: str,
        starting_equity: float,
        risk_pct: float,
        fee_per_share: float,
        max_daily_loss: float,
        criteria: ForwardTestCriteria = ForwardTestCriteria(),
        atr_period: int = 14,
        atr_multiple: float = 1.5,
        risk_reward: float = 2.0,
    ):
        self.criteria = criteria
        self.portfolio = Portfolio(starting_equity)
        self.daily_loss_guard = DailyLossGuard(max_daily_loss)
        self.engines: dict[str, PaperTradingEngine] = {
            symbol: PaperTradingEngine(
                symbol=symbol,
                strategy=strategy_factory(),
                strategy_name=strategy_name,
                portfolio=self.portfolio,
                daily_loss_guard=self.daily_loss_guard,
                risk_pct=risk_pct,
                fee_per_share=fee_per_share,
                atr_period=atr_period,
                atr_multiple=atr_multiple,
                risk_reward=risk_reward,
            )
            for symbol in symbols
        }
        self._started_at: Optional[datetime] = None
        self._last_bar_at: Optional[datetime] = None

    def ingest(self, bars: list[Bar]) -> None:
        """Feed one new batch of bars - call this once per real-world data
        pull (e.g. once a day) as the forward test actually progresses,
        not once with the whole history. Bars for multiple symbols may be
        mixed together; each is dispatched to its own symbol's engine in
        chronological order."""
        for bar in sorted(bars, key=lambda b: b.timestamp):
            if bar.symbol not in self.engines:
                raise ValueError(
                    f"ForwardTestSession.ingest: no engine configured for symbol {bar.symbol!r} "
                    f"(configured symbols: {sorted(self.engines)})"
                )
            if self._started_at is None:
                self._started_at = bar.timestamp
            self._last_bar_at = bar.timestamp
            self.engines[bar.symbol].on_bar(bar)

    def status(self) -> ForwardTestStatus:
        if self._started_at is None or self._last_bar_at is None:
            elapsed_days = 0.0
        else:
            elapsed_days = (self._last_bar_at - self._started_at).total_seconds() / 86400.0

        # trades_from_fills() expects a single symbol's fills (see its own
        # docstring) - portfolio.fills interleaves every traded symbol, the
        # same grouping fix used in scripts/phase9_paper_trading_demo.py.
        fills_by_symbol: dict[str, list] = {}
        for fill in self.portfolio.fills:
            fills_by_symbol.setdefault(fill.symbol, []).append(fill)
        trades = [trade for fills in fills_by_symbol.values() for trade in trades_from_fills(fills)]
        metrics = compute_metrics(trades)

        return ForwardTestStatus(
            started_at=self._started_at,
            last_bar_at=self._last_bar_at,
            elapsed_days=elapsed_days,
            metrics=metrics,
            trades_criterion_met=metrics.trade_count >= self.criteria.min_trades,
            days_criterion_met=elapsed_days >= self.criteria.min_days,
        )


@dataclass(frozen=True)
class OosComparisonReport:
    oos_expectancy: float
    forward_expectancy: float
    oos_win_rate: float
    forward_win_rate: float
    same_sign_expectancy: bool
    note: str


_MAGNITUDE_CAVEAT = (
    "raw expectancy magnitudes are NOT directly comparable if oos_metrics came from "
    "reference_engine.run_reference_backtest() (always exactly 1 unit per trade) while "
    "forward_metrics came from ForwardTestSession/app.paper (realistic, risk-based share "
    "counts via app.signals.risk.position_size - often far more than 1 share). Only the "
    "SIGN of expectancy is safe to compare across that difference; a forward-test dollar "
    "expectancy many times larger or smaller than the OOS one is expected from position "
    "sizing alone; see scripts/phase10_forward_test_demo.py for a concrete example."
)


def compare_to_oos(oos_metrics: Metrics, forward_metrics: Metrics) -> OosComparisonReport:
    """Side-by-side comparison, deliberately NOT a pass/fail gate.
    ROADMAP.md Abschnitt 14 says forward testing should "confirm" the OOS
    result, but names no numeric tolerance for how much divergence is
    still acceptable - inventing one here would be exactly the kind of
    unconfirmed business decision DECISIONS.md #4/#5 were escalated to the
    user for, not something to quietly assume. The one thing that IS
    unambiguous without any threshold: expectancy flipping sign between
    OOS and forward testing is a plain "this does not confirm the OOS
    result", not a judgment call - reported explicitly, the rest left as
    numbers for a human to weigh, WITH the position-sizing caveat below -
    caught while writing scripts/phase10_forward_test_demo.py, whose OOS
    metrics (reference_engine, 1 unit/trade) and forward metrics (real
    risk-based share counts) differ in expectancy by ~100x purely from
    that scale difference, not from any actual change in edge."""
    if forward_metrics.trade_count == 0:
        return OosComparisonReport(
            oos_expectancy=oos_metrics.expectancy,
            forward_expectancy=forward_metrics.expectancy,
            oos_win_rate=oos_metrics.win_rate,
            forward_win_rate=forward_metrics.win_rate,
            same_sign_expectancy=False,
            note="no forward-test trades yet - nothing to compare",
        )
    same_sign = (oos_metrics.expectancy > 0) == (forward_metrics.expectancy > 0)
    note = (
        f"same sign as OOS expectancy. {_MAGNITUDE_CAVEAT}"
        if same_sign
        else f"OPPOSITE sign from OOS expectancy - forward test does not confirm the OOS result. {_MAGNITUDE_CAVEAT}"
    )
    return OosComparisonReport(
        oos_expectancy=oos_metrics.expectancy,
        forward_expectancy=forward_metrics.expectancy,
        oos_win_rate=oos_metrics.win_rate,
        forward_win_rate=forward_metrics.win_rate,
        same_sign_expectancy=same_sign,
        note=note,
    )
