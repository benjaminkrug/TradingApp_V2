"""Technically-enforced In-Sample / Out-of-Sample split.

ROADMAP.md Abschnitt 8: "Claude darf OOS-Daten nicht zur Optimierung
verwenden." A rule like that living only in a prompt or in someone's head
is exactly the kind of thing that gets violated by accident under
iteration pressure (see ROADMAP.md Abschnitt 10's note on the DaviddTech
transcript, where OOS discipline was applied ad hoc through iterative
human feedback rather than a technical split). `OosSplit.out_of_sample`
is locked until `unlock()` is called explicitly — "we forgot and touched
OOS data while tuning" becomes a hard error instead of a discipline lapse.
"""

from __future__ import annotations

from datetime import date

from app.data.calendar import NY_TZ
from app.data.point_in_time import Bar


class OosLockedError(RuntimeError):
    """Raised when out-of-sample data is accessed before `unlock()`."""


class OosSplit:
    def __init__(self, bars: list[Bar], cutoff: date):
        # NY-local date, consistent with app/features/indicators.py's
        # current_session_bars and app/validation/walk_forward.py - see
        # walk_forward.py's module docstring for why this matters even
        # though it's a no-op for regular-session bars specifically.
        self._in_sample = [b for b in bars if b.timestamp.astimezone(NY_TZ).date() < cutoff]
        self._out_of_sample = [b for b in bars if b.timestamp.astimezone(NY_TZ).date() >= cutoff]
        self._unlocked = False

    @property
    def in_sample(self) -> list[Bar]:
        return list(self._in_sample)

    @property
    def out_of_sample(self) -> list[Bar]:
        if not self._unlocked:
            raise OosLockedError(
                "out_of_sample is locked. Finish strategy development and parameter "
                "selection against in_sample only, then call unlock() explicitly "
                "before evaluating on out_of_sample - see module docstring."
            )
        return list(self._out_of_sample)

    @property
    def is_unlocked(self) -> bool:
        return self._unlocked

    def unlock(self) -> None:
        self._unlocked = True
