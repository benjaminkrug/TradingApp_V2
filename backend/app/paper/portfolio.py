"""Paper-trading portfolio state — cash, open positions, and the resulting
fills, shared across every symbol's `PaperTradingEngine` (app/paper/engine.py)
so risk sizing (app/signals/risk.py's `position_size`) is always computed
against one account's actual current equity, not a per-symbol fiction.

Deliberately produces the same `Fill` objects `reference_engine.py` does
(app/backtest/reference_engine.py), so `trades_from_fills()` and
`compute_metrics()` (app/validation/metrics.py) work unchanged on paper
trading output — one metrics implementation for both backtest and paper
trading, not two that could quietly drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

from app.backtest.reference_engine import Fill


class InsufficientCashError(ValueError):
    """Raised by `open_position` when its cost would take `cash` negative.

    `app.signals.risk.position_size` sizes a position purely off risk
    (max acceptable loss / stop distance) - it has no concept of buying
    power. With one shared `Portfolio` funding several symbols at once
    (see `run_paper_trading`), several risk-correctly-sized positions can
    still collectively cost more than the account actually holds. A real
    broker rejects an order it can't afford rather than silently lending
    against thin air; this engine does the same, rather than letting
    `cash` go negative (caught during Phase 9 development by actually
    running scripts/phase9_paper_trading_demo.py and noticing negative
    ending cash - see PHASE9_NOTES.md)."""


@dataclass
class OpenPosition:
    symbol: str
    entry_time: datetime
    entry_price: float
    quantity: float
    stop: float
    target: float
    entry_fee: float


@dataclass
class PendingOrder:
    """A strategy decision awaiting execution at the *next* bar's open —
    mirrors reference_engine.py's next-bar-open fill convention. Stop-loss
    and take-profit orders do NOT go through this: they are resting orders
    already in the market and can fill intrabar, using only the bar that
    breaches them (see PaperTradingEngine._check_stop_target) - no next-bar
    lag applies to those, only to strategy-decided entries/exits, which are
    based on a bar's close and cannot realistically be acted on before the
    following bar."""

    symbol: str
    side: Literal["BUY", "SELL"]
    stop: Optional[float] = None
    target: Optional[float] = None
    shares: Optional[float] = None


class Portfolio:
    def __init__(self, starting_cash: float):
        if starting_cash <= 0:
            raise ValueError("starting_cash must be positive")
        self.starting_cash = starting_cash
        self.cash = starting_cash
        self.positions: dict[str, OpenPosition] = {}
        self.fills: list[Fill] = []
        self._mark_prices: dict[str, float] = {}
        self.rejected_orders: int = 0

    def mark(self, symbol: str, price: float) -> None:
        """Records the latest known price for `symbol`, used by `equity()`
        to mark open positions to market. Call this on every bar seen for a
        symbol, whether or not it results in a trade."""
        self._mark_prices[symbol] = price

    def equity(self) -> float:
        total = self.cash
        for symbol, position in self.positions.items():
            price = self._mark_prices.get(symbol, position.entry_price)
            total += position.quantity * price
        return total

    def open_position(
        self,
        symbol: str,
        entry_time: datetime,
        entry_price: float,
        quantity: float,
        stop: float,
        target: float,
        fee_per_share: float,
    ) -> Fill:
        """`fee_per_share` is a per-share rate, scaled by `quantity` here to
        get the total dollar fee for this fill. Caught during development:
        reference_engine.py's `fee_per_share` parameter is applied as a flat
        per-fill amount, not multiplied by quantity - harmless there only
        because it always trades a single unit (quantity=1.0, see its own
        docstring), which makes "flat fee" and "per-share fee" numerically
        identical by coincidence. Paper trading has real share counts
        (app/signals/risk.py's `position_size`), so copying that shortcut
        here would have understated trading costs by roughly the share
        count on every fill - e.g. 125 shares at a "$0.01/share" fee would
        have cost $0.01 total instead of $1.25."""
        if symbol in self.positions:
            raise ValueError(
                f"Portfolio.open_position: {symbol} already has an open position - no pyramiding "
                "(same rule as reference_engine.run_reference_backtest)"
            )
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        fee = fee_per_share * quantity
        cost = entry_price * quantity + fee
        if cost > self.cash:
            self.rejected_orders += 1
            raise InsufficientCashError(
                f"Portfolio.open_position: {symbol} order costs {cost:.2f} but only {self.cash:.2f} cash "
                "is available - order rejected, not filled on margin."
            )
        self.cash -= cost
        self.positions[symbol] = OpenPosition(
            symbol=symbol,
            entry_time=entry_time,
            entry_price=entry_price,
            quantity=quantity,
            stop=stop,
            target=target,
            entry_fee=fee,
        )
        fill = Fill(symbol=symbol, timestamp=entry_time, side="BUY", price=entry_price, quantity=quantity, fee=fee)
        self.fills.append(fill)
        return fill

    def close_position(
        self, symbol: str, exit_time: datetime, exit_price: float, fee_per_share: float
    ) -> tuple[Fill, float]:
        position = self.positions.pop(symbol, None)
        if position is None:
            raise ValueError(f"Portfolio.close_position: no open position for {symbol}")
        fee = fee_per_share * position.quantity
        self.cash += exit_price * position.quantity - fee
        fill = Fill(
            symbol=symbol, timestamp=exit_time, side="SELL", price=exit_price, quantity=position.quantity, fee=fee
        )
        self.fills.append(fill)
        # Same formula as app/validation/metrics.py's trades_from_fills(), so
        # a full post-hoc trades_from_fills(portfolio.fills) run reproduces
        # this exact number per trade - verified by a cross-check test
        # (tests/test_portfolio.py) rather than sharing code for one line
        # of arithmetic.
        realized_pnl = (exit_price - position.entry_price) * position.quantity - position.entry_fee - fee
        return fill, realized_pnl
