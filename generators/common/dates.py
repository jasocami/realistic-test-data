"""
Date arithmetic that does not break on 29 February.
===============================================================================

WHAT IS THIS FILE?
------------------
Small date helpers shared by every topic generator.

THE BUG THIS FILE EXISTS TO PREVENT
-----------------------------------
The obvious way to add a year to a date in Python is:

    some_date.replace(year=some_date.year + 1)

...and it works perfectly, until the day it doesn't:

    >>> from datetime import date
    >>> date(2024, 2, 29).replace(year=2025)
    Traceback (most recent call last):
    ValueError: day is out of range for month

29 February only exists in leap years. 2024 has one, 2025 does not, so there
is no such thing as 29 February 2025 and Python refuses to invent one.

This is a genuinely common production bug. It lies dormant for up to four
years and then fires on exactly one day -- typically on an insurance renewal
date, a subscription anniversary or a birthday calculation. The fix is to
decide explicitly what "one year after 29 February" should mean. The usual
answer, and the one used here, is 28 February.
"""

from __future__ import annotations

import calendar
from datetime import date


def add_years(start: date, years: int) -> date:
    """Add (or subtract) whole years, clamping 29 February to the 28th.

    >>> add_years(date(2024, 2, 29), 1)
    datetime.date(2025, 2, 28)
    >>> add_years(date(2024, 6, 14), 2)
    datetime.date(2026, 6, 14)
    >>> add_years(date(2024, 2, 29), -4)
    datetime.date(2020, 2, 29)
    """
    target_year = start.year + years
    last_day_of_month = calendar.monthrange(target_year, start.month)[1]
    return date(target_year, start.month, min(start.day, last_day_of_month))


def add_months(start: date, months: int) -> date:
    """Add (or subtract) whole months, clamping to the end of the month.

    The same class of problem as add_years: there is no 31 February, and no
    31 April either.

    >>> add_months(date(2024, 1, 31), 1)
    datetime.date(2024, 2, 29)
    >>> add_months(date(2025, 1, 31), 1)
    datetime.date(2025, 2, 28)
    >>> add_months(date(2024, 3, 15), -3)
    datetime.date(2023, 12, 15)
    """
    zero_based_month = start.month - 1 + months
    target_year = start.year + zero_based_month // 12
    target_month = zero_based_month % 12 + 1
    last_day_of_month = calendar.monthrange(target_year, target_month)[1]
    return date(target_year, target_month, min(start.day, last_day_of_month))


def next_weekday(day: date) -> date:
    """Move a date forward to the next Monday-to-Friday day, if needed.

    Used wherever the data models something that only happens on working
    days -- clinic appointments, phlebotomy rounds, business transactions.
    Real calendars have this shape and data that ignores it looks wrong the
    moment anyone charts activity by day of week.

    >>> next_weekday(date(2024, 6, 15))    # a Saturday
    datetime.date(2024, 6, 17)
    >>> next_weekday(date(2024, 6, 14))    # already a Friday
    datetime.date(2024, 6, 14)
    """
    from datetime import timedelta

    while day.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        day += timedelta(days=1)
    return day


def age_on(born: date, when: date) -> int:
    """Whole years between two dates.

    Handles the case everyone forgets: someone born in December is not a year
    older until December, so the comparison has to include month and day.

    >>> age_on(date(1974, 3, 11), date(2025, 6, 30))
    51
    >>> age_on(date(1974, 12, 25), date(2025, 6, 30))
    50
    """
    return when.year - born.year - ((when.month, when.day) < (born.month, born.day))
