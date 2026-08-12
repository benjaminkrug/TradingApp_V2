"""Walk-forward window generation — ROADMAP.md Abschnitt 9/10.

Rolling train -> test cycles over the *distinct calendar dates* present in
the data (not raw bar count, so this behaves the same whether bars are
5-minute or daily). Each window's train and test bars are disjoint and
test always immediately follows train, advancing by `step_days` each time
— this is the mechanism that lets a strategy be checked across changing
market conditions rather than a single lucky train/test split.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.data.point_in_time import Bar


@dataclass(frozen=True)
class WalkForwardWindow:
    train: list[Bar]
    test: list[Bar]


def walk_forward_windows(
    bars: list[Bar],
    train_days: int,
    test_days: int,
    step_days: int,
) -> list[WalkForwardWindow]:
    if train_days <= 0 or test_days <= 0 or step_days <= 0:
        raise ValueError("train_days, test_days, and step_days must all be positive")

    dates = sorted({b.timestamp.date() for b in bars})
    windows: list[WalkForwardWindow] = []

    start = 0
    while start + train_days + test_days <= len(dates):
        train_dates = set(dates[start : start + train_days])
        test_dates = set(dates[start + train_days : start + train_days + test_days])

        windows.append(
            WalkForwardWindow(
                train=[b for b in bars if b.timestamp.date() in train_dates],
                test=[b for b in bars if b.timestamp.date() in test_dates],
            )
        )
        start += step_days

    return windows
