"""
Half-hourly solar generation for the v2 assessment (story H17), without any network call.

A typical UK roof makes about 850 kWh per kWp a year (the same figure the v1 calculator
used). That year is split into months by a typical UK monthly yield, and each day's
generation follows a sine curve between sunrise and sunset for its month (clock time,
so British Summer Time is included). East or west-facing roofs make less and peak
earlier or later.

Every day in a month gets that month's average day: the model has no cloudy or sunny
days, so it slightly understates how often a battery fills up on bright days and sits
empty on dull ones.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Literal

Orientation = Literal["south", "south_east", "south_west", "east", "west"]

KWH_PER_KWP_YEAR = 850.0

# kWh per kWp in each month for a south-facing roof at about 35° in the Midlands (sums to 850).
_MONTHLY_KWH_PER_KWP = [25, 40, 70, 95, 115, 115, 115, 100, 75, 50, 30, 20]
_DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

# Sunrise and sunset in clock hours for the middle of each month, central England.
_SUN_HOURS = [
    (8.1, 16.3), (7.4, 17.3), (6.4, 18.1), (6.4, 19.9), (5.3, 20.8), (4.8, 21.5),
    (5.1, 21.3), (5.9, 20.5), (6.8, 19.4), (7.5, 18.2), (7.3, 16.5), (8.1, 15.9),
]

# Share of a south-facing roof's yield, and how far the daily peak moves (hours).
ORIENTATIONS: dict[str, tuple[float, float]] = {
    "south": (1.00, 0.0),
    "south_east": (0.95, -0.75),
    "south_west": (0.95, 0.75),
    "east": (0.82, -1.5),
    "west": (0.82, 1.5),
}


def _shape(month: int, shift_h: float) -> list[float]:
    """48 weights for month (0–11) that sum to 1."""
    rise, set_ = _SUN_HOURS[month]
    rise, set_ = rise + shift_h, set_ + shift_h
    w = []
    for slot in range(48):
        mid = slot / 2 + 0.25   # middle of the half hour
        x = (mid - rise) / (set_ - rise)
        w.append(math.sin(math.pi * x) ** 2 if 0 < x < 1 else 0.0)
    total = sum(w)
    return [v / total for v in w]


def monthly_profiles(kwp: float, orientation: str = "south") -> list[list[float]]:
    """12 average days (kWh per half hour), January first."""
    factor, shift = ORIENTATIONS[orientation]
    return [
        [kwp * factor * _MONTHLY_KWH_PER_KWP[m] / _DAYS_IN_MONTH[m] * s for s in _shape(m, shift)]
        for m in range(12)
    ]


def annual_generation_kwh(kwp: float, orientation: str = "south") -> float:
    return kwp * ORIENTATIONS[orientation][0] * KWH_PER_KWP_YEAR


def generation_days(
    n_days: int, dates: list[date] | None, kwp: float, orientation: str = "south",
) -> list[list[float]]:
    """
    One 48-slot generation day for each usage day. With dates, each day takes its month's
    profile. Without dates (an upload with no dates), every day gets the yearly average day.
    """
    months = monthly_profiles(kwp, orientation)
    if dates and len(dates) == n_days:
        return [months[d.month - 1] for d in dates]
    avg = [sum(months[m][i] * _DAYS_IN_MONTH[m] for m in range(12)) / 365 for i in range(48)]
    return [avg] * n_days
