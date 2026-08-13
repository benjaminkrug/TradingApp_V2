"""Synthetic demo market data for the API layer — NOT real market data.

Real providers (Alpaca/Polygon) are still unimplemented stubs
(app/data/providers/alpaca.py, polygon.py) and this sandbox cannot reach
either API to verify credentials/connectivity even if they were
implemented (PHASE3_NOTES.md). Rather than block the whole Web-App phase
on that, or worse, silently pass synthetic numbers off as real ones,
every API response built from this module is labeled
`data_source: "synthetic_demo"` end-to-end so the frontend (and anyone
reading the API directly) can never mistake it for a real market signal.
Swap this module out for a real `MarketDataProvider.get_bars()` call once
Alpaca/Polygon is actually verified — nothing else in app/api/ needs to
change for that, since callers only depend on getting back `list[Bar]`.

Uses the same seeded-random-walk approach as
scripts/phase7_synthetic_gate_run.py, parameterized per-symbol (seeded
from the symbol string) so repeated requests for the same symbol on the
same day return a stable series instead of a different one every call.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Optional

from app.data.calendar import is_trading_day, session_bounds
from app.data.point_in_time import Bar

BAR_MINUTES = 5


def generate_demo_bars(symbol: str, num_trading_days: int = 10, end: Optional[date] = None) -> list[Bar]:
    """Deterministic (seeded from `symbol`), synthetic 5-minute bars for
    the `num_trading_days` trading days up to and including `end`
    (default: today), using the real NYSE calendar/session bounds."""
    seed = sum(ord(c) for c in symbol)
    rng = random.Random(seed)
    end = end or date.today()

    days: list[date] = []
    d = end
    while len(days) < num_trading_days:
        if is_trading_day(d):
            days.append(d)
        d -= timedelta(days=1)
    days.reverse()

    bars: list[Bar] = []
    price = 100.0 + (seed % 200)
    for d in days:
        open_utc, close_utc = session_bounds(d)
        t = open_utc
        day_drift = rng.uniform(-0.03, 0.03)
        while t < close_utc:
            drift = day_drift + rng.gauss(0, 0.15)
            price = max(1.0, price + drift)
            open_ = price
            close = max(1.0, price + rng.gauss(0, 0.1))
            high = max(open_, close) + abs(rng.gauss(0, 0.05))
            low = min(open_, close) - abs(rng.gauss(0, 0.05))
            volume = max(100, int(rng.gauss(1000, 150)))
            if rng.random() < 0.03:  # occasional volume spike, ~3% of bars
                volume = int(volume * rng.uniform(2.5, 5.0))
            bars.append(
                Bar(symbol=symbol, timestamp=t, open=open_, high=high, low=low, close=close, volume=volume)
            )
            price = close
            t += timedelta(minutes=BAR_MINUTES)
    return bars
