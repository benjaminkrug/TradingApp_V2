"""Risk/exit parameter calculations — ROADMAP.md Abschnitt 13/17.

`risk_pct` is never defaulted here: DECISIONS.md marks the 0.25-0.5%
figure as provisional (a recommendation, not yet individually confirmed
by the user — see that file's note on decisions #4/#5). Every call site
must pass it explicitly rather than silently inheriting an unconfirmed
number as a default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


def atr_stop_loss(entry: float, atr_value: float, atr_multiple: float = 1.5) -> float:
    """Long-only ATR-based stop, placed below entry."""
    if atr_multiple <= 0:
        raise ValueError("atr_multiple must be positive")
    if atr_value < 0:
        raise ValueError("atr_value cannot be negative")
    return entry - atr_multiple * atr_value


def risk_reward_target(entry: float, stop: float, risk_reward: float = 2.0) -> float:
    """Take-profit placed at `risk_reward` multiples of the entry-to-stop
    distance above entry (ROADMAP.md Abschnitt 14)."""
    if stop >= entry:
        raise ValueError("stop must be below entry for a long position")
    if risk_reward <= 0:
        raise ValueError("risk_reward must be positive")
    risk_per_share = entry - stop
    return entry + risk_reward * risk_per_share


def position_size(
    account_equity: float,
    risk_pct: float,
    entry: float,
    stop: float,
    max_position_pct: Optional[float] = None,
) -> float:
    """Shares such that a fill exactly at `stop` loses `risk_pct` of
    `account_equity` — the worked example in ROADMAP.md Abschnitt 13
    (50000 account, 0.5% risk, entry 100, stop 98 -> 125 shares).

    `max_position_pct` optionally caps the resulting position at a share of
    account equity. Risk-based sizing alone says nothing about how much
    capital a position ties up: with a tight stop it implies an enormous
    one, and it only limits the loss *if the stop holds* - which it does
    not against an overnight gap, now that DECISIONS.md #2 permits
    multi-day holds. Measured on real data, a stop from a 5-minute ATR
    produced positions of 83-136% of the account. Defaults to None (no
    cap) so the ROADMAP worked example above keeps its documented result;
    callers that trade rather than illustrate should set it.
    """
    if not 0 < risk_pct < 1:
        raise ValueError("risk_pct must be a fraction between 0 and 1 (e.g. 0.005 for 0.5%)")
    if account_equity <= 0:
        raise ValueError("account_equity must be positive")
    risk_per_share = entry - stop
    if risk_per_share <= 0:
        raise ValueError("stop must be below entry for a long position")
    max_loss = account_equity * risk_pct
    shares = max_loss / risk_per_share

    if max_position_pct is not None:
        if not 0 < max_position_pct <= 1:
            raise ValueError("max_position_pct must be a fraction in (0, 1], e.g. 0.20 for 20%")
        if entry <= 0:
            raise ValueError("entry must be positive")
        shares = min(shares, account_equity * max_position_pct / entry)
    return shares


@dataclass
class DailyLossGuard:
    """Hard, technical daily-loss kill-switch — ROADMAP.md Abschnitt 12:
    "Kill-Switch als Code, nicht als Regel". Once cumulative recorded PnL
    for the day drops to or below `-max_daily_loss`, the guard trips and
    `can_trade()` returns False for the rest of the day, regardless of
    whatever PnL gets recorded afterwards — a big subsequent win must not
    silently re-enable trading, since the entire point of a daily loss
    limit is "stop for today," not "stop until the running total happens
    to look better again." The only way past a trip is `reset()`, a
    deliberate, visible action — never an implicit side effect of a
    profitable trade.
    """

    max_daily_loss: float  # positive number, e.g. 250.0 for a $250/day limit
    _cumulative_pnl: float = field(default=0.0, init=False)
    _tripped: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.max_daily_loss <= 0:
            raise ValueError("max_daily_loss must be positive")

    def record_pnl(self, pnl: float) -> None:
        self._cumulative_pnl += pnl
        if self._cumulative_pnl <= -self.max_daily_loss:
            self._tripped = True

    def can_trade(self) -> bool:
        return not self._tripped

    def reset(self) -> None:
        self._cumulative_pnl = 0.0
        self._tripped = False

    @property
    def cumulative_pnl(self) -> float:
        return self._cumulative_pnl
