"""Pre-trade News/Earnings/Volatility filter — ROADMAP.md Abschnitt 14:
"Vor jedem Trade: Prüfung auf Earnings, relevante News, ungewöhnliche
Volatilität." Never built in any earlier phase (flagged as a gap in
PHASE10_NOTES.md); implemented now because ROADMAP explicitly requires it
before Phase 11 (Controlled Live Test) puts real capital at risk.

Three checks, three different levels of honesty about what is actually
implemented — deliberately not uniform, because pretending otherwise
would misrepresent what each one can actually do:

1. Earnings blackout: a real check with a real interface
   (`EarningsCalendarProvider`), but only a documented, unverified stub
   for actual data - no earnings-calendar API is reachable from this
   sandbox (same network constraint as Alpaca/Polygon, see
   PHASE3_NOTES.md). `FakeEarningsCalendarProvider` exists for tests,
   mirroring `app/data/providers/fake.py`'s `FakeProvider`.
2. Unusual volatility: a REAL, fully working check - needs no external
   data, only this codebase's own `atr()` (short-window ATR vs. a longer
   baseline). Unlike the other two, this one is not a stub.
3. Relevant news: NOT implemented, not even as a documented stub.
   "Relevant" is a judgment call (sentiment, materiality, source
   credibility) this codebase cannot make at all yet, not merely one it
   can't verify with real data - a fake interface with no real content
   behind it would overstate how built this is. Reported as
   `NOT_AUTOMATED`, the same honesty pattern `app/validation/gate.py`
   uses for checks it genuinely cannot automate.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Literal, Optional

from app.data.point_in_time import Bar
from app.features.indicators import atr

Status = Literal["PASS", "BLOCK", "NOT_AUTOMATED"]


@dataclass(frozen=True)
class PreTradeCheckResult:
    name: str
    status: Status
    detail: str


@dataclass(frozen=True)
class PreTradeGateReport:
    results: list[PreTradeCheckResult]

    @property
    def blocked(self) -> bool:
        return any(r.status == "BLOCK" for r in self.results)


class EarningsCalendarProvider(ABC):
    @abstractmethod
    def next_earnings_date(self, symbol: str, as_of: date) -> Optional[date]:
        """The next known earnings date for `symbol` on or after `as_of`,
        or None if none is known/scheduled."""
        raise NotImplementedError


class FakeEarningsCalendarProvider(EarningsCalendarProvider):
    def __init__(self, earnings_dates: dict[str, list[date]]):
        self._by_symbol = {symbol: sorted(dates) for symbol, dates in earnings_dates.items()}

    def next_earnings_date(self, symbol: str, as_of: date) -> Optional[date]:
        for d in self._by_symbol.get(symbol, []):
            if d >= as_of:
                return d
        return None


def check_earnings_blackout(
    symbol: str, as_of: date, provider: EarningsCalendarProvider, blackout_days: int = 2
) -> PreTradeCheckResult:
    next_date = provider.next_earnings_date(symbol, as_of)
    if next_date is None:
        return PreTradeCheckResult("earnings_blackout", "PASS", f"no known upcoming earnings date for {symbol}")
    days_until = (next_date - as_of).days
    if 0 <= days_until <= blackout_days:
        return PreTradeCheckResult(
            "earnings_blackout", "BLOCK", f"{symbol} reports earnings in {days_until} day(s) ({next_date})"
        )
    return PreTradeCheckResult("earnings_blackout", "PASS", f"next known earnings for {symbol}: {next_date}")


def check_unusual_volatility(
    history: list[Bar], short_period: int = 5, baseline_period: int = 20, expansion_multiple: float = 2.5
) -> PreTradeCheckResult:
    """BLOCKs when a short-window ATR has expanded far beyond a longer
    baseline ATR - the concrete case ROADMAP.md Abschnitt 14 names
    ("ungewöhnliche Volatilität"). A real, working check: unlike the other
    two functions in this module, it needs no external data source."""
    short_atr = atr(history, short_period)
    baseline_atr = atr(history, baseline_period)
    if short_atr is None or baseline_atr is None:
        return PreTradeCheckResult("unusual_volatility", "NOT_AUTOMATED", "not enough history to compute ATR yet")
    if baseline_atr == 0:
        return PreTradeCheckResult("unusual_volatility", "PASS", "baseline ATR is zero - nothing to compare against")
    ratio = short_atr / baseline_atr
    if ratio >= expansion_multiple:
        return PreTradeCheckResult(
            "unusual_volatility",
            "BLOCK",
            f"{short_period}-bar ATR is {ratio:.2f}x the {baseline_period}-bar baseline "
            f"(threshold {expansion_multiple}x)",
        )
    return PreTradeCheckResult("unusual_volatility", "PASS", f"{short_period}-bar ATR is {ratio:.2f}x baseline")


def check_relevant_news() -> PreTradeCheckResult:
    return PreTradeCheckResult(
        "relevant_news",
        "NOT_AUTOMATED",
        "no news-relevance data source exists - deliberately not stubbed with a fake interface, "
        "since 'relevant' is a judgment call this codebase cannot yet make at all, not just one "
        "it can't verify with real data (contrast with EarningsCalendarProvider, which has a real "
        "interface behind its stub).",
    )


def run_pretrade_gate(
    symbol: str,
    as_of: date,
    history: list[Bar],
    earnings_provider: EarningsCalendarProvider,
    earnings_blackout_days: int = 2,
    volatility_short_period: int = 5,
    volatility_baseline_period: int = 20,
    volatility_expansion_multiple: float = 2.5,
) -> PreTradeGateReport:
    return PreTradeGateReport(
        results=[
            check_earnings_blackout(symbol, as_of, earnings_provider, earnings_blackout_days),
            check_unusual_volatility(
                history, volatility_short_period, volatility_baseline_period, volatility_expansion_multiple
            ),
            check_relevant_news(),
        ]
    )
