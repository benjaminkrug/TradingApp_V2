"""Point-in-time data access primitives.

Implements the structural look-ahead guard required by ROADMAP.md Abschnitt 7:
"Zum Zeitpunkt eines Signals darf nur Information verwendet werden, die zu
diesem Zeitpunkt tatsächlich verfügbar war." Rather than relying on callers
to behave (a prompt instruction, or a human, can always make a mistake), the
data types here make it structurally impossible to reach a future bar.

Strategies and features must only ever be handed a `SimulationCursor`, never
a raw list of bars or a `PointInTimeSeries`. The cursor only exposes
`current` and `history` (index <= current), and only moves forward.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


class LookAheadError(RuntimeError):
    """Raised when code attempts to access data not yet available "now"."""


@dataclass(frozen=True, order=True)
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class PointInTimeSeries:
    """A chronologically ordered, immutable bar series.

    This is a storage/query convenience for offline analysis (e.g. "what did
    we know as of 10:35?"). It is intentionally *not* handed to strategy code
    during a backtest — use `SimulationCursor` for that, which cannot be
    asked for the future even by an incorrect caller.
    """

    def __init__(self, bars: list[Bar]):
        ordered = sorted(bars, key=lambda b: b.timestamp)
        if ordered != list(bars):
            raise ValueError("bars must be supplied in chronological order")
        self._bars = list(bars)

    def __len__(self) -> int:
        return len(self._bars)

    def as_of(self, timestamp: datetime) -> list[Bar]:
        """All bars with timestamp <= `timestamp`."""
        return [b for b in self._bars if b.timestamp <= timestamp]

    def new_cursor(self) -> "SimulationCursor":
        return SimulationCursor(self._bars)


class SimulationCursor:
    """One-directional cursor over a bar series.

    `advance()` is the only way to move, and only ever forward. `history`
    returns bars up to and including the current one — safe to compute
    indicators/features over. There is no method that returns anything past
    `current`, so a strategy holding only a cursor structurally cannot look
    ahead, regardless of what it tries.
    """

    def __init__(self, bars: list[Bar]):
        self._bars = bars
        self._index = -1

    def advance(self) -> Bar:
        next_index = self._index + 1
        if next_index >= len(self._bars):
            raise StopIteration
        self._index = next_index
        return self.current

    @property
    def current(self) -> Bar:
        if self._index < 0:
            raise LookAheadError("cursor has not been advanced yet")
        return self._bars[self._index]

    @property
    def history(self) -> list[Bar]:
        if self._index < 0:
            return []
        return self._bars[: self._index + 1]

    @property
    def has_next(self) -> bool:
        return self._index + 1 < len(self._bars)
