"""Paper-trading engine — ROADMAP.md Abschnitt 14: "Paper Trading nutzt
exakt dieselbe Logik wie später live".

That principle is enforced structurally here, not just by intent:

- Strategies (app/strategies/*.py) are unmodified pure functions of
  `cursor.history` - they cannot tell whether they are being driven by
  `SimulationCursor` (backtest) or `StreamingCursor` (here).
- New entries are sized and stopped/targeted via `build_signal()`
  (app/signals/signal.py), the exact same function the Phase 8 API uses
  to present live signals to a human - no separate, competing sizing
  logic for paper trading.
- Every fill is a `reference_engine.Fill`, so `trades_from_fills()` and
  `compute_metrics()` (app/validation/metrics.py) work unchanged on paper
  trading results.

What is NOT (yet) unified with backtesting: `reference_engine.py` only
exits on a strategy SELL signal - it has no concept of the ATR stop/target
`build_signal()` already computes at entry. This engine is the first place
those are actually enforced (`_check_stop_target`), and the first place
ROADMAP.md's "close every position by end of day" intraday rule
(Abschnitt 2) is enforced too (`_flatten_for_session_rollover`) - both
gaps were previously documented as known, unfixed limitations
(app/features/indicators.py's module docstring, PHASE7_NOTES.md). See
PHASE9_NOTES.md for why reference_engine.py itself was deliberately left
alone rather than retrofitted with the same rules - it stays a minimal,
hand-verifiable correctness oracle, not the execution model.

Also NOT unified: ROADMAP.md Abschnitt 9's long-term vision is a single
production engine (Nautilus Trader, verified installable in Phase 2 but
never integrated) driving backtest, paper, and live through identical
code paths. This module is a lighter bridge implementation built to make
paper trading demonstrable now; it is not that unification. See
PHASE9_NOTES.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Optional

from app.data.calendar import NY_TZ
from app.data.point_in_time import Bar, StreamingCursor
from app.data.providers.base import MarketDataProvider
from app.paper.portfolio import InsufficientCashError, PendingOrder, Portfolio
from app.signals.risk import DailyLossGuard
from app.signals.signal import build_signal

# Strategies (app/strategies/*.py) are duck-typed on `cursor.history` alone
# (see StreamingCursor's docstring) - not constrained to one cursor type.
Strategy = Callable[[Any], str]
StrategyFactory = Callable[[], Strategy]


def _session_date(bar: Bar) -> date:
    return bar.timestamp.astimezone(NY_TZ).date()


class PaperTradingEngine:
    """Drives one symbol's paper-trading state, one bar at a time, off a
    `Portfolio` and `DailyLossGuard` shared across every symbol traded in
    the same paper account (see `run_paper_trading` below for the
    multi-symbol driver)."""

    def __init__(
        self,
        symbol: str,
        strategy: Strategy,
        strategy_name: str,
        portfolio: Portfolio,
        daily_loss_guard: DailyLossGuard,
        risk_pct: float,
        fee_per_share: float,
        atr_period: int = 14,
        atr_multiple: float = 1.5,
        risk_reward: float = 2.0,
    ):
        self.symbol = symbol
        self.strategy = strategy
        self.strategy_name = strategy_name
        self.portfolio = portfolio
        self.daily_loss_guard = daily_loss_guard
        self.risk_pct = risk_pct
        self.fee_per_share = fee_per_share
        # Passed through to build_signal() explicitly rather than relying on
        # its defaults, so callers (and tests, which need small windows to
        # stay hand-verifiable) can control them - see build_signal()'s own
        # docstring for what each one means.
        self.atr_period = atr_period
        self.atr_multiple = atr_multiple
        self.risk_reward = risk_reward
        self.cursor = StreamingCursor()
        self._pending_order: Optional[PendingOrder] = None
        self._current_session_date: Optional[date] = None

    def on_bar(self, bar: Bar) -> None:
        if bar.symbol != self.symbol:
            raise ValueError(f"PaperTradingEngine for {self.symbol} received a bar for {bar.symbol}")

        session_date = _session_date(bar)
        if self._current_session_date is not None and session_date != self._current_session_date:
            self._flatten_for_session_rollover()
            self.daily_loss_guard.reset()
        self._current_session_date = session_date

        self.cursor.append(bar)
        self.portfolio.mark(self.symbol, bar.close)

        self._process_pending_fill(bar)
        self._check_stop_target(bar)
        self._evaluate_strategy()

    def _flatten_for_session_rollover(self) -> None:
        """ROADMAP.md Abschnitt 2: exit spätestens Handelsende (intraday
        only). Closes any still-open position at the last bar of the
        session that just ended - an approximation of a market-on-close
        fill (the actual closing-auction price is not modeled), applied
        because nothing here waits for one final "session close" event;
        the first bar of the *next* session is what tells us the previous
        one ended."""
        if self.symbol in self.portfolio.positions and self.cursor.history:
            last_bar_of_prior_session = self.cursor.history[-1]
            _, pnl = self.portfolio.close_position(
                self.symbol,
                last_bar_of_prior_session.timestamp,
                last_bar_of_prior_session.close,
                self.fee_per_share,
            )
            self.daily_loss_guard.record_pnl(pnl)
        self._pending_order = None  # an unfilled day order does not carry over to the next session

    def _process_pending_fill(self, bar: Bar) -> None:
        order = self._pending_order
        if order is None:
            return
        self._pending_order = None

        if order.side == "BUY":
            if self.symbol in self.portfolio.positions:
                return  # a stop/target or strategy exit already closed and reopened is not possible
            assert order.stop is not None and order.target is not None and order.shares is not None
            try:
                self.portfolio.open_position(
                    self.symbol, bar.timestamp, bar.open, order.shares, order.stop, order.target, self.fee_per_share
                )
            except InsufficientCashError:
                # Order rejected for insufficient buying power - dropped,
                # same as reference_engine.py dropping a pending action with
                # no next bar to fill at. Sized correctly for risk (build_signal
                # only knows the stop distance, not the account's current
                # buying power across all open positions), but the account
                # cannot actually afford it right now - a real broker would
                # reject this order too, not fill it on margin.
                pass
        elif order.side == "SELL":
            if self.symbol not in self.portfolio.positions:
                return
            _, pnl = self.portfolio.close_position(self.symbol, bar.timestamp, bar.open, self.fee_per_share)
            self.daily_loss_guard.record_pnl(pnl)

    def _check_stop_target(self, bar: Bar) -> None:
        """Stop-loss/target are resting orders already in the market, not a
        decision made from this bar's close - they can fill within the
        same bar that breaches them, using only that bar's own low/high
        (no next-bar lag, unlike strategy-decided entries/exits below).
        If both are breached in the same bar, the stop is assumed to have
        been hit first - a conservative, explicitly approximate ordering
        choice, since plain OHLC bars cannot reveal the real intrabar
        sequence (same honesty gap as `realistic_execution` in
        app/validation/gate.py - NOT_AUTOMATED there, approximated here)."""
        position = self.portfolio.positions.get(self.symbol)
        if position is None:
            return
        if bar.low <= position.stop:
            _, pnl = self.portfolio.close_position(self.symbol, bar.timestamp, position.stop, self.fee_per_share)
            self.daily_loss_guard.record_pnl(pnl)
        elif bar.high >= position.target:
            _, pnl = self.portfolio.close_position(self.symbol, bar.timestamp, position.target, self.fee_per_share)
            self.daily_loss_guard.record_pnl(pnl)

    def _evaluate_strategy(self) -> None:
        action = self.strategy(self.cursor)
        position = self.portfolio.positions.get(self.symbol)

        if position is not None:
            if action == "SELL":
                self._pending_order = PendingOrder(self.symbol, side="SELL")
            return

        if action != "BUY" or not self.daily_loss_guard.can_trade():
            return

        signal = build_signal(
            self.cursor,
            "BUY",
            strategy_name=self.strategy_name,
            account_equity=self.portfolio.equity(),
            risk_pct=self.risk_pct,
            atr_period=self.atr_period,
            atr_multiple=self.atr_multiple,
            risk_reward=self.risk_reward,
        )
        if signal is not None:
            self._pending_order = PendingOrder(
                self.symbol, side="BUY", stop=signal.stop, target=signal.target, shares=signal.shares
            )


@dataclass(frozen=True)
class PaperTradingResult:
    """`portfolio.fills` interleaves every traded symbol in chronological
    order. `app.validation.metrics.trades_from_fills()` expects a single
    symbol's fills (see its own docstring) - group by `fill.symbol` before
    calling it on multi-symbol output, as scripts/phase9_paper_trading_demo.py
    does, rather than passing `portfolio.fills` straight through."""

    portfolio: Portfolio
    daily_loss_guard: DailyLossGuard


def run_paper_trading(
    provider: MarketDataProvider,
    symbols: list[str],
    strategy_factory: StrategyFactory,
    strategy_name: str,
    start: date,
    end: date,
    timeframe: str,
    starting_equity: float,
    risk_pct: float,
    fee_per_share: float,
    max_daily_loss: float,
    atr_period: int = 14,
    atr_multiple: float = 1.5,
    risk_reward: float = 2.0,
) -> PaperTradingResult:
    """Multi-symbol paper-trading driver: pulls each symbol's bars from
    `provider` (any `MarketDataProvider` - `FakeProvider` for tests/demos
    today, `AlpacaProvider` once it is a verified implementation, see
    PHASE3_NOTES.md/PHASE9_NOTES.md), merges them into one globally
    chronological stream, and dispatches each bar to that symbol's
    `PaperTradingEngine`. All symbols share one `Portfolio` and one
    `DailyLossGuard`, so position sizing and the daily kill-switch both
    operate on the whole account, not per symbol in isolation.
    """
    portfolio = Portfolio(starting_equity)
    daily_loss_guard = DailyLossGuard(max_daily_loss)

    engines = {
        symbol: PaperTradingEngine(
            symbol=symbol,
            strategy=strategy_factory(),
            strategy_name=strategy_name,
            portfolio=portfolio,
            daily_loss_guard=daily_loss_guard,
            risk_pct=risk_pct,
            fee_per_share=fee_per_share,
            atr_period=atr_period,
            atr_multiple=atr_multiple,
            risk_reward=risk_reward,
        )
        for symbol in symbols
    }

    all_bars: list[Bar] = []
    for symbol in symbols:
        all_bars.extend(provider.get_bars(symbol, start, end, timeframe))

    # Stable sort by timestamp only: bars for different symbols at the same
    # timestamp keep provider order (arbitrary but deterministic), which is
    # fine here since each engine only ever looks at its own symbol's bars.
    for bar in sorted(all_bars, key=lambda b: b.timestamp):
        engines[bar.symbol].on_bar(bar)

    return PaperTradingResult(portfolio=portfolio, daily_loss_guard=daily_loss_guard)
