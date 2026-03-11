"""
Payback and ROI calculations.
"""
from __future__ import annotations
from dataclasses import dataclass
import math


@dataclass
class PaybackResult:
    years: float            # payback period; math.inf if saving <= 0 or never breaks even
    cumulative: list[float] # cumulative savings by year (25 years)
    roi_10yr: float         # (annual_saving * 10) - installed_cost


def calc_payback(
    installed_cost: float,
    annual_saving: float,
    inflation_pct: float = 5.0,
) -> PaybackResult:
    """
    Calculate payback period using compound inflation on annual saving.

    annual_saving * (1 + r)^(y-1) for year y, where r = inflation_pct / 100.
    Returns math.inf if saving <= 0 or cost never recovered within 25 years.
    """
    if annual_saving <= 0:
        return PaybackResult(
            years=math.inf,
            cumulative=[0.0] * 25,
            roi_10yr=annual_saving * 10 - installed_cost,
        )

    r = inflation_pct / 100.0
    cum = 0.0
    by_year: list[float] = []
    payback_year: float | None = None

    for y in range(1, 26):
        cum += annual_saving * ((1 + r) ** (y - 1))
        by_year.append(round(cum, 2))
        if payback_year is None and cum >= installed_cost:
            # interpolate for fractional year
            prev = by_year[-2] if len(by_year) > 1 else 0.0
            fraction = (installed_cost - prev) / (cum - prev)
            payback_year = (y - 1) + fraction

    return PaybackResult(
        years=payback_year if payback_year is not None else math.inf,
        cumulative=by_year,
        roi_10yr=round(annual_saving * 10 - installed_cost, 2),
    )
