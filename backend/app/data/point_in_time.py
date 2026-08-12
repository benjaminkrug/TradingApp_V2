"""Point-in-time data access primitives.

Implements the structural look-ahead guard required by ROADMAP.md Abschnitt 7:
"Zum Zeitpunkt eines Signals darf nur Information verwendet werden, die zu
diesem Zeitpunkt tatsächlich verfügbar war."

How look-ahead is actually prevented here: `SimulationCursor` is the only
object strategy code ever receives, and its public API has no method that
can return bar[i] for i > the current index — there simply is no such
method. That is what "structural" means in this module: it is a property of
the API surface, not of any runtime check. It holds as long as calling code
only uses the public API; a caller that reaches into `cursor._bars` directly
(Python does not enforce privacy) could still defeat it. If that turns out
to matter in practice (e.g. once strategy code is less trusted, such as
AI-generated strategies in Phase 7), the stronger fix is to stop holding the
full bar list in the cursor at all and stream bars in one at a time instead.
Not done here because nothing currently needs that stronger guarantee.

`CursorNotStartedError` is a separate, narrower thing: it only fires when
`current`/`history` is read before `advance()`/`next()` was ever called. It
is not raised in response to an attempted look-ahead — there is no code path
that even represents "attempting to look ahead" given the API shape above.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


class CursorNotStartedError(RuntimeError):
    """Raised when `current`/`history` is read before the cursor has advanced."""


@dataclass(frozen=True)
class Bar:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError(
                "Bar.timestamp must be timezone-aware (e.g. datetime(..., "
                "tzinfo=timezone.utc)). Naive datetimes are a foundational "
                "type used everywhere downstream; a DST/session-boundary bug "
                "here is cheap to prevent now and expensive to retrofit once "
                "real market-hours data depends on it."
            )


class PointInTimeSeries:
    """A chronologically ordered, immutable, single-symbol bar series.

    Storage/query convenience for offline analysis (e.g. "what did we know
    as of 10:35?"). Not handed to strategy code during a backtest — use
    `SimulationCursor` for that.
    """

    def __init__(self, bars: list[Bar]):
        ordered = sorted(bars, key=lambda b: b.timestamp)
        if ordered != list(bars):
            raise ValueError("bars must be supplied in chronological order")
        symbols = {b.symbol for b in bars}
        if len(symbols) > 1:
            raise ValueError(
                f"PointInTimeSeries holds bars for exactly one symbol, got {sorted(symbols)}. "
                "Mixing symbols here would silently corrupt any point-in-time logic built on top."
            )
        self._bars = list(bars)

    def __len__(self) -> int:
        return len(self._bars)

    def as_of(self, timestamp: datetime) -> list[Bar]:
        """All bars with timestamp <= `timestamp`."""
        return [b for b in self._bars if b.timestamp <= timestamp]

    def new_cursor(self) -> "SimulationCursor":
        return SimulationCursor(self._bars)


class SimulationCursor:
    """One-directional iterator over a bar series.

    Implements the standard iterator protocol (`for bar in cursor:`) rather
    than a bespoke `advance()`-only interface, specifically so that
    `StopIteration` behaves the way Python code normally expects it to (a
    hand-rolled `advance()` that raises `StopIteration` outside of an
    iterator works today only because callers happen to catch it explicitly;
    if it were ever consumed from inside a generator function instead,
    PEP 479 turns an uncaught `StopIteration` into a confusing `RuntimeError`
    at the generator boundary). `advance()` is kept as a readable alias.

    `history` returns bars up to and including the current one — safe to
    compute indicators/features over. See module docstring for exactly what
    "cannot look ahead" does and does not guarantee.
    """

    def __init__(self, bars: list[Bar]):
        self._bars = bars
        self._index = -1

    def __iter__(self) -> "SimulationCursor":
        return self

    def __next__(self) -> Bar:
        next_index = self._index + 1
        if next_index >= len(self._bars):
            raise StopIteration
        self._index = next_index
        return self.current

    def advance(self) -> Bar:
        return next(self)

    @property
    def current(self) -> Bar:
        if self._index < 0:
            raise CursorNotStartedError("cursor has not been advanced yet")
        return self._bars[self._index]

    @property
    def history(self) -> list[Bar]:
        if self._index < 0:
            return []
        return self._bars[: self._index + 1]

    @property
    def has_next(self) -> bool:
        return self._index + 1 < len(self._bars)
