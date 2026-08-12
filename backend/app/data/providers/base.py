"""Market data provider abstraction.

Decouples the rest of the system from any one vendor (Alpaca, Polygon.io —
see DECISIONS.md; both currently marked provisional) so the provider choice
can be swapped or added to without touching strategy/backtest code, and so
tests can run against `FakeProvider` without needing network access or
credentials at all.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from app.data.point_in_time import Bar


class MarketDataProvider(ABC):
    @abstractmethod
    def get_bars(self, symbol: str, start: date, end: date, timeframe: str) -> list[Bar]:
        """Chronologically ordered bars for `symbol` between `start` and
        `end` (inclusive), at `timeframe` (provider-specific string, e.g.
        '5Min'/'1Day' — deliberately unconstrained here since concrete
        adapters differ)."""
        raise NotImplementedError
