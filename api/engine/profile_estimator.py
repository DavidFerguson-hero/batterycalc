"""
Synthetic half-hourly consumption profile generator.

Takes annual_kwh + property_type (+ heating type from the EPC) and produces
365 days of half-hourly kWh in the same format as csv_parser.ParseResult.days,
so the simulation engine can consume it without modification.
"""
from __future__ import annotations

from datetime import date, timedelta

from .csv_parser import ParseResult

# ---------------------------------------------------------------------------
# Profile shapes — relative weights, normalized to sum=1.0 by _norm()
# 48 slots, each representing a 30-min window starting at midnight.
# ---------------------------------------------------------------------------

# Standard house: strong morning (07-09) + evening peak (18-21)
_RAW_HOUSE = [
    # 00:00–05:30  overnight low
    0.40, 0.35, 0.30, 0.28, 0.26, 0.25, 0.25, 0.26, 0.28, 0.32, 0.38, 0.46,
    # 06:00–07:30  morning ramp
    0.72, 1.10, 1.55, 1.80,
    # 08:00–09:30  morning peak → taper
    1.75, 1.52, 1.28, 1.05,
    # 10:00–15:30  daytime (most out at work)
    0.88, 0.78, 0.76, 0.76, 0.80, 0.84, 0.86, 0.82, 0.76, 0.74, 0.78, 0.90,
    # 16:00–17:30  late afternoon ramp
    1.12, 1.38, 1.72, 2.02,
    # 18:00–20:30  evening peak (cooking, heating, TV)
    2.25, 2.28, 2.18, 2.02, 1.78, 1.50,
    # 21:00–23:30  wind down
    1.20, 0.95, 0.72, 0.56, 0.46, 0.40,
]

# Flat/apartment: flatter profile — softer morning, less cooking peak
_RAW_FLAT = [
    # 00:00–05:30  overnight
    0.38, 0.33, 0.28, 0.26, 0.24, 0.23, 0.23, 0.24, 0.26, 0.30, 0.35, 0.44,
    # 06:00–07:30  morning ramp (softer — smaller kitchen, no garden)
    0.62, 0.92, 1.28, 1.45,
    # 08:00–09:30  morning peak
    1.42, 1.25, 1.10, 0.98,
    # 10:00–15:30  daytime (slightly higher — more WFH in smaller spaces)
    0.90, 0.84, 0.82, 0.82, 0.84, 0.87, 0.88, 0.86, 0.82, 0.80, 0.83, 0.92,
    # 16:00–17:30  late afternoon
    1.05, 1.22, 1.48, 1.68,
    # 18:00–20:30  evening peak (flatter — smaller appliances)
    1.75, 1.78, 1.70, 1.58, 1.40, 1.20,
    # 21:00–23:30  wind down
    1.05, 0.85, 0.65, 0.52, 0.43, 0.38,
]


def _norm(raw: list[float]) -> list[float]:
    total = sum(raw)
    return [v / total for v in raw]


PROFILE_HOUSE = _norm(_RAW_HOUSE)
PROFILE_FLAT  = _norm(_RAW_FLAT)

_PROFILES: dict[str, list[float]] = {
    "flat":     PROFILE_FLAT,
    "terraced": PROFILE_HOUSE,
    "semi":     PROFILE_HOUSE,
    "detached": PROFILE_HOUSE,
}

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
# APPROXIMATE, pending calibration against real households (task 3.1).
# Shaped to match the well-known UK pattern: domestic electricity peaks in
# Dec/Jan (lighting, longer evenings, more time indoors) and bottoms out in
# June/July. Homes heated by electricity (no mains gas) swing far more.
#   gas:      December ≈ 1.5× June
#   electric: December ≈ 3.2× June
# ---------------------------------------------------------------------------
MONTHLY_FACTORS: dict[str, list[float]] = {
    "gas":      [1.20, 1.12, 1.05, 0.95, 0.88, 0.83, 0.83, 0.85, 0.90, 1.00, 1.12, 1.22],
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
    Each day uses the property's daily shape, scaled by its month's seasonal factor.
    """
    profile = _PROFILES.get(property_type, PROFILE_HOUSE)
    factors = monthly_factors(heating)
    dates = model_year_dates()
    weight_total = sum(factors[d.month - 1] for d in dates)
    days: list[list[float]] = []
    for d in dates:
        daily_kwh = annual_kwh * factors[d.month - 1] / weight_total
        days.append([v * daily_kwh for v in profile])
    return days


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
