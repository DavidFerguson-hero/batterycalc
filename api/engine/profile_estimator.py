"""
Synthetic half-hourly consumption profile generator.

Takes annual_kwh + property_type (+ heating type from the EPC) and produces
365 days of half-hourly kWh in the same format as csv_parser.ParseResult.days,
so the simulation engine can consume it without modification.
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from .csv_parser import ParseResult

# ---------------------------------------------------------------------------
# Daily shape — share of a day's use in each half hour (48 slots from midnight,
# UK local time), normalised to sum to 1.0 by _norm().
#
# Measured, not guessed (task 3.1): the average day of 3,765 London homes with a
# full year of half-hourly readings in 2013 (Low Carbon London smart meter trial,
# UK Power Networks, via 4TU.ResearchData, CC BY 4.0), each home weighted equally.
# Real homes use far more overnight (fridges, freezers, standby: about 15% of the
# day before 06:00) and have a gentler teatime peak than the hand-drawn curve this
# replaced, which made a battery look about 8% more useful than it is.
# The trial recorded no property type, so every home type uses this shape.
# ---------------------------------------------------------------------------
_RAW_TYPICAL = [
    # 00:00–05:30  overnight: fridges, freezers, standby, late evenings
    0.80, 0.74, 0.67, 0.61, 0.57, 0.55, 0.53, 0.52, 0.52, 0.52, 0.56, 0.60,
    # 06:00–09:30  morning
    0.68, 0.78, 0.90, 0.98, 1.02, 1.03, 1.03, 1.03,
    # 10:00–15:30  daytime
    1.02, 1.00, 1.00, 1.01, 1.03, 1.04, 1.03, 1.01, 0.99, 0.99, 1.00, 1.05,
    # 16:00–20:30  teatime and evening peak
    1.12, 1.21, 1.31, 1.38, 1.47, 1.51, 1.53, 1.51, 1.49,
    # 21:00–23:30  wind down
    1.47, 1.44, 1.37, 1.30, 1.16, 1.01, 0.92,
]


def _norm(raw: list[float]) -> list[float]:
    total = sum(raw)
    return [v / total for v in raw]


PROFILE_TYPICAL = _norm(_RAW_TYPICAL)

_PROFILES: dict[str, list[float]] = {
    "flat":     PROFILE_TYPICAL,
    "terraced": PROFILE_TYPICAL,
    "semi":     PROFILE_TYPICAL,
    "detached": PROFILE_TYPICAL,
}

# Real homes don't use the same amount every day: in the trial, a home's daily total
# typically varied by about 25% around its average for the month. A battery can't
# store all of a busy day's peak or fill up usefully on a quiet one, so identical days
# overstate the saving. Each modelled day is scaled by a fixed pseudo-random factor
# with this spread (the same every run), keeping each month's total unchanged.
DAY_TO_DAY_SPREAD = 0.25
_DAY_SEED = 2013

# Suggested annual kWh by property type and bedroom count.
# Values sourced from BEIS UK domestic energy consumption statistics.
SUGGESTED_KWH: dict[str, dict[int, int]] = {
    "flat":     {1: 1800, 2: 2400, 3: 2900},
    "terraced": {2: 2800, 3: 3200, 4: 3800},
    "semi":     {2: 3000, 3: 3500, 4: 4200},
    "detached": {3: 4200, 4: 5100, 5: 6500},
}

# ---------------------------------------------------------------------------
# Seasonal shape — relative daily use by calendar month (index 0 = January).
#
# gas: measured from the same 3,765 trial homes (task 3.1), almost all heated by gas;
#   January ≈ 1.5× August.
# electric: homes heated by electricity (no mains gas) swing far more; December ≈ 3.2×
#   June. Still an estimate: the trial had too few electrically heated homes to measure.
# ---------------------------------------------------------------------------
MONTHLY_FACTORS: dict[str, list[float]] = {
    "gas":      [1.21, 1.18, 1.15, 0.99, 0.90, 0.85, 0.84, 0.82, 0.89, 0.96, 1.08, 1.14],
    "electric": [1.75, 1.60, 1.35, 1.00, 0.70, 0.55, 0.52, 0.55, 0.68, 0.95, 1.40, 1.75],
}
HEATING_TYPES = tuple(MONTHLY_FACTORS)

# A fixed non-leap year: the estimate route models "a typical year", not a real one.
MODEL_YEAR = 2025
N_SYNTHETIC_DAYS = 365


def model_year_dates() -> list[date]:
    start = date(MODEL_YEAR, 1, 1)
    return [start + timedelta(days=i) for i in range(N_SYNTHETIC_DAYS)]


def monthly_factors(heating: str) -> list[float]:
    if heating not in MONTHLY_FACTORS:
        raise ValueError(f"heating must be one of {HEATING_TYPES}")
    return MONTHLY_FACTORS[heating]


def generate_days(
    annual_kwh: float,
    property_type: str,
    heating: str = "gas",
) -> list[list[float]]:
    """
    Return 365 days (1 Jan → 31 Dec of a typical year) whose total is annual_kwh.
    Each day uses the typical daily shape, scaled by its month's seasonal factor and
    by a fixed day-to-day factor (see DAY_TO_DAY_SPREAD) that leaves each month's total as it was.
    """
    profile = _PROFILES.get(property_type, PROFILE_TYPICAL)
    factors = monthly_factors(heating)
    dates = model_year_dates()
    weight_total = sum(factors[d.month - 1] for d in dates)
    day_factor = _day_to_day_factors(dates)
    days: list[list[float]] = []
    for d, f in zip(dates, day_factor):
        daily_kwh = annual_kwh * factors[d.month - 1] / weight_total * f
        days.append([v * daily_kwh for v in profile])
    return days


def _day_to_day_factors(dates: list[date]) -> list[float]:
    """One factor per day, spread like real homes' daily totals, averaging exactly 1 within each month."""
    rng = random.Random(_DAY_SEED)
    raw = [rng.lognormvariate(0.0, DAY_TO_DAY_SPREAD) for _ in dates]
    month_mean: dict[int, float] = {}
    for m in {d.month for d in dates}:
        vals = [r for r, d in zip(raw, dates) if d.month == m]
        month_mean[m] = sum(vals) / len(vals)
    return [r / month_mean[d.month] for r, d in zip(raw, dates)]


def make_parse_result(
    annual_kwh: float,
    property_type: str,
    unit_rate_p: float,
    heating: str = "gas",
) -> ParseResult:
    """Build a ParseResult from estimator inputs, ready for run_simulation()."""
    days = generate_days(annual_kwh, property_type, heating)
    total = sum(sum(d) for d in days)
    return ParseResult(
        days=days,
        inferred_rate=unit_rate_p / 100.0,
        days_count=len(days),
        total_kwh=round(total, 2),
        daily_avg_kwh=round(total / len(days), 3),
        annual_kwh_estimate=round(annual_kwh, 1),
        dates=model_year_dates(),
        coverage=None,
        confidence="estimate",
    )
