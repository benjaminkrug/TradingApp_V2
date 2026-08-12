"""Walk-forward window generation — ROADMAP.md Abschnitt 9/10.

Rolling train -> test cycles over the *distinct exchange-local (America/
New_York) calendar dates* present in the data (not raw bar count, so this
behaves the same whether bars are 5-minute or daily) — the same NY-local
date convention `app/features/indicators.py`'s `current_session_bars`
uses, deliberately kept consistent here rather than taking `.date()`
directly off a UTC timestamp. For a regular 9:30-16:00 ET session the two
happen to agree (the session never crosses UTC midnight), but that is a
coincidence of standard market hours, not a rule this module should rely
on — extended-hours bars or a different exchange's timezone would silently
misattribute a bar to the wrong "day" under naive UTC dates. Each window's
train and test bars are disjoint and test always immediately follows
train, advancing by `step_days` each time.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.data.calendar import NY_TZ
from app.data.point_in_time import Bar


@dataclass(frozen=True)
class WalkForwardWindow:
    train: list[Bar]
    test: list[Bar]


def _local_date(bar: Bar):
    return bar.timestamp.astimezone(NY_TZ).date()


def walk_forward_windows(
    bars: list[Bar],
    train_days: int,
    test_days: int,
    step_days: int,
) -> list[WalkForwardWindow]:
    if train_days <= 0 or test_days <= 0 or step_days <= 0:
        raise ValueError("train_days, test_days, and step_days must all be positive")

    dates = sorted({_local_date(b) for b in bars})
    windows: list[WalkForwardWindow] = []

    start = 0
    while start + train_days + test_days <= len(dates):
        train_dates = set(dates[start : start + train_days])
        test_dates = set(dates[start + train_days : start + train_days + test_days])

        windows.append(
            WalkForwardWindow(
                train=[b for b in bars if _local_date(b) in train_dates],
                test=[b for b in bars if _local_date(b) in test_dates],
            )
        )
        start += step_days

    return windows
