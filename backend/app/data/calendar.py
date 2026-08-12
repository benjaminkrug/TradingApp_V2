"""US equity market (NYSE) trading calendar.

Deterministic full-day holidays only: New Year's Day, Martin Luther King
Jr. Day, Washington's Birthday (Presidents' Day), Good Friday, Memorial
Day, Juneteenth (observed as an NYSE holiday since 2022), Independence
Day, Labor Day, Thanksgiving, Christmas — with the standard weekend
observance shift (a holiday falling on Saturday is observed the preceding
Friday; on Sunday, the following Monday).

Deliberately NOT included: early-close half-days (e.g. the day before July
4th, the day after Thanksgiving, Christmas Eve when it is not itself a
full holiday). NYSE publishes these per calendar year rather than by a
fixed rule, so a hand-maintained table here would silently go stale
without anyone noticing. Flagged as a known gap in PHASE3_NOTES.md rather
than guessed at.

All times are computed in exchange-local time (America/New_York, via the
stdlib `zoneinfo` — no extra dependency) and converted to UTC, consistent
with storing `Bar.timestamp` in UTC everywhere else in this codebase.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")

_REGULAR_OPEN = (9, 30)
_REGULAR_CLOSE = (16, 0)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The n-th occurrence (1-indexed) of `weekday` (Mon=0) in a month."""
    d = date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    d += timedelta(days=offset + 7 * (n - 1))
    return d


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        d = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        d = date(year, month + 1, 1) - timedelta(days=1)
    offset = (d.weekday() - weekday) % 7
    return d - timedelta(days=offset)


def _easter_sunday(year: int) -> date:
    """Anonymous Gregorian algorithm (Meeus/Jones/Butcher)."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _observed(d: date) -> date:
    """Saturday holidays are observed the preceding Friday, Sunday the
    following Monday."""
    if d.weekday() == 5:  # Saturday
        return d - timedelta(days=1)
    if d.weekday() == 6:  # Sunday
        return d + timedelta(days=1)
    return d


def nyse_holidays(year: int) -> set[date]:
    holidays = {
        _observed(date(year, 1, 1)),  # New Year's Day
        _nth_weekday(year, 1, 0, 3),  # MLK Day: 3rd Monday of January
        _nth_weekday(year, 2, 0, 3),  # Presidents' Day: 3rd Monday of February
        _easter_sunday(year) - timedelta(days=2),  # Good Friday
        _last_weekday(year, 5, 0),  # Memorial Day: last Monday of May
        _observed(date(year, 7, 4)),  # Independence Day
        _nth_weekday(year, 9, 0, 1),  # Labor Day: 1st Monday of September
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving: 4th Thursday of November
        _observed(date(year, 12, 25)),  # Christmas
    }
    if year >= 2022:
        holidays.add(_observed(date(year, 6, 19)))  # Juneteenth
    return holidays


def is_trading_day(d: date) -> bool:
    if d.weekday() >= 5:  # Saturday/Sunday
        return False
    return d not in nyse_holidays(d.year)


def session_bounds(d: date) -> tuple[datetime, datetime]:
    """Regular session (9:30-16:00 America/New_York) for `d`, returned as
    UTC-aware datetimes (session start/end computed in exchange-local time
    so DST transitions are handled correctly, then converted). Raises
    ValueError if `d` is not a trading day."""
    if not is_trading_day(d):
        raise ValueError(f"{d} is not an NYSE trading day")
    open_local = datetime(d.year, d.month, d.day, *_REGULAR_OPEN, tzinfo=NY_TZ)
    close_local = datetime(d.year, d.month, d.day, *_REGULAR_CLOSE, tzinfo=NY_TZ)
    return open_local.astimezone(timezone.utc), close_local.astimezone(timezone.utc)
