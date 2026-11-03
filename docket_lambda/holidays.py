"""Oklahoma legal holidays (25 O.S. § 82.1) on which district courts are closed.

Missing a day that actually had a docket loses data, while fetching a closed day costs one
request. So this list is deliberately conservative: it holds only holidays that are
certain, and anything uncertain is left for the scraper to check.

  * Fixed-date holidays that fall on Saturday are observed the Friday before; on Sunday,
    the Monday after (the usual executive-order rule).
  * Christmas Eve is NOT skipped: whether it's observed, and on which day, varies by
    the governor's order each year. Add it per run with "skip_dates" if you know.
  * One-off closures (weather, etc.) also go in "skip_dates". Use "include_dates" to
    force a fetch on any date this module would skip.
"""
from __future__ import annotations

from datetime import date, timedelta


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """n-th (1-based) weekday (Mon=0) of a month; n=-1 for the last one."""
    if n > 0:
        d = date(year, month, 1)
        d += timedelta(days=(weekday - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)
    d = date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _observed(d: date) -> date:
    return d - timedelta(days=1) if d.weekday() == 5 else d + timedelta(days=1) if d.weekday() == 6 else d


def court_holidays(year: int) -> dict[date, str]:
    thanksgiving = _nth_weekday(year, 11, 3, 4)
    h = {
        _observed(date(year, 1, 1)): "New Year's Day",
        _nth_weekday(year, 1, 0, 3): "Martin Luther King Jr. Day",
        _nth_weekday(year, 2, 0, 3): "Presidents' Day",
        _nth_weekday(year, 5, 0, -1): "Memorial Day",
        _observed(date(year, 7, 4)): "Independence Day",
        _nth_weekday(year, 9, 0, 1): "Labor Day",
        _observed(date(year, 11, 11)): "Veterans Day",
        thanksgiving: "Thanksgiving",
        thanksgiving + timedelta(days=1): "Day after Thanksgiving",
        _observed(date(year, 12, 25)): "Christmas Day",
    }
    # Next year's Jan 1 on a Saturday is observed Fri Dec 31 of this year.
    nxt = _observed(date(year + 1, 1, 1))
    if nxt.year == year:
        h[nxt] = "New Year's Day (observed)"
    return h


def holidays_between(start: date, end: date) -> dict[date, str]:
    out: dict[date, str] = {}
    for y in range(start.year - 1, end.year + 1):
        out.update({d: n for d, n in court_holidays(y).items() if start <= d <= end})
    return out
