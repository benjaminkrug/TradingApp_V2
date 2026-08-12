"""In-memory MarketDataProvider for tests — no network involved.

Exists to prove the abstraction in base.py is actually usable end-to-end
without live credentials, and to give later phases (strategies, signal
engine) something to backtest against before real provider adapters are
verified. See PHASE3_NOTES.md.
"""

from __future__ import annotations

from datetime import date

from app.data.point_in_time import Bar
from app.data.providers.base import MarketDataProvider


class FakeProvider(MarketDataProvider):
    def __init__(self, bars_by_symbol: dict[str, list[Bar]]):
        self._bars_by_symbol = bars_by_symbol

    def get_bars(self, symbol: str, start: date, end: date, timeframe: str) -> list[Bar]:
        bars = self._bars_by_symbol.get(symbol, [])
        return [b for b in bars if start <= b.timestamp.date() <= end]
