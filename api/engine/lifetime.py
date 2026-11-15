"""
Lifetime finance for a home battery: what it costs, what it saves year by year over its
life, when it pays back, and a plain verdict.

Three cases are always modelled, so the answer is a range, not a single number:
  optimistic   — low installed cost,     high energy-price growth
  likely       — typical installed cost, central energy-price growth
  pessimistic  — high installed cost,    low energy-price growth

Each year's saving = year-1 saving
                   × capacity left after wear          (1 − capacity_loss)^(year − 1)
                   × energy prices relative to year 1  (1 + price_growth)^(year − 1)
and the inverter replacement cost is paid in its replacement year.

Decisions D3 and D5 (approved by David, 15 Nov 2026) set the defaults below.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

# ── D5: default assumptions ───────────────────────────────────────────────────
PRICE_GROWTH = {"low": 0.01, "central": 0.03, "high": 0.05}   # energy prices, a year
CAPACITY_LOSS_PER_YEAR = 0.02
BATTERY_LIFE_YEARS = 15
WARRANTY_YEARS = 10
INVERTER_REPLACEMENT_YEAR = 10

# ── Placeholders until D4 (task 1.8) supplies sourced cost figures ───────────
INVERTER_REPLACEMENT_COST = 1000.0   # £, PLACEHOLDER — fitted hybrid inverter
COST_RANGE = (0.85, 1.15)            # low / high installed cost as a share of typical, PLACEHOLDER

# ── D3: verdict thresholds (likely payback as a share of the warranty) ───────
WORTH_IT_SHARE = 0.70
BORDERLINE_SHARE = 1.00

Verdict = Literal["worth_it", "borderline", "not_yet"]


@dataclass
class LifetimeAssumptions:
    battery_life_years: int = BATTERY_LIFE_YEARS
    warranty_years: int = WARRANTY_YEARS
    capacity_loss_per_year: float = CAPACITY_LOSS_PER_YEAR
    price_growth: dict[str, float] = field(default_factory=lambda: dict(PRICE_GROWTH))
    inverter_replacement_year: int | None = INVERTER_REPLACEMENT_YEAR
    inverter_replacement_cost: float = INVERTER_REPLACEMENT_COST


@dataclass
class LifetimeCase:
    name: str                      # "optimistic" | "likely" | "pessimistic"
    installed_cost: float
    price_growth: float
    cash_by_year: list[float]      # year 0 .. life: cumulative £ (starts at −installed cost)
    payback_years: float | None    # when it breaks even for good; None if not within its life
    lifetime_net_gain: float       # cumulative £ at the end of the battery's life


@dataclass
class LifetimeResult:
    cases: dict[str, LifetimeCase]
    payback_years: dict[str, float | None]   # "low" (soonest) | "likely" | "high" (latest)
    lifetime_net_gain: dict[str, float]      # "low" (worst) | "likely" | "high" (best)
    verdict: Verdict
    assumptions: LifetimeAssumptions

    def to_dict(self) -> dict:
        a = self.assumptions
        return {
            "verdict": self.verdict,
            "payback_years": {k: _r(v, 1) for k, v in self.payback_years.items()},
            "lifetime_net_gain": {k: round(v) for k, v in self.lifetime_net_gain.items()},
            "installed_cost": {
                "low": round(self.cases["optimistic"].installed_cost),
                "typical": round(self.cases["likely"].installed_cost),
                "high": round(self.cases["pessimistic"].installed_cost),
            },
            "cash_by_year": {n: [round(v) for v in c.cash_by_year] for n, c in self.cases.items()},
            "assumptions": {
                "battery_life_years": a.battery_life_years,
                "warranty_years": a.warranty_years,
                "capacity_loss_pct_per_year": a.capacity_loss_per_year * 100,
                "price_growth_pct": {k: v * 100 for k, v in a.price_growth.items()},
                "inverter_replacement_year": a.inverter_replacement_year,
                "inverter_replacement_cost": a.inverter_replacement_cost,
            },
        }


def _r(v: float | None, nd: int) -> float | None:
    return None if v is None else round(v, nd)


def cash_by_year(
    installed_cost: float,
    year1_saving: float,
    price_growth: float,
    a: LifetimeAssumptions,
) -> list[float]:
    """Cumulative cash position at the end of each year, year 0 (install) to end of life."""
    cash = [-installed_cost]
    for y in range(1, a.battery_life_years + 1):
        saving = (
            year1_saving
            * (1 - a.capacity_loss_per_year) ** (y - 1)
            * (1 + price_growth) ** (y - 1)
        )
        if y == a.inverter_replacement_year:
            saving -= a.inverter_replacement_cost
        cash.append(cash[-1] + saving)
    return cash


def payback_from_cash(cash: list[float]) -> float | None:
    """
    The point after which the battery stays in profit: the last time the cumulative
    cash crosses from below zero to zero or above, interpolated within that year.
    A mid-life dip (an inverter replacement) that pushes it back below zero moves
    payback later. None if it is still below zero at the end of its life.
    """
    if cash[-1] < 0:
        return None
    last_negative = max((y for y, v in enumerate(cash) if v < 0), default=None)
    if last_negative is None:
        return 0.0
    before, after = cash[last_negative], cash[last_negative + 1]
    return last_negative + (-before) / (after - before)


def verdict_for(likely_payback: float | None, warranty_years: float) -> Verdict:
    if likely_payback is None:
        return "not_yet"
    if likely_payback <= WORTH_IT_SHARE * warranty_years:
        return "worth_it"
    if likely_payback <= BORDERLINE_SHARE * warranty_years:
        return "borderline"
    return "not_yet"


def lifetime_finance(
    typical_cost: float,
    year1_saving: float,
    cost_low: float | None = None,
    cost_high: float | None = None,
    assumptions: LifetimeAssumptions | None = None,
) -> LifetimeResult:
    """Model the battery over its life in three cases and give a verdict."""
    a = assumptions or LifetimeAssumptions()
    low = cost_low if cost_low is not None else typical_cost * COST_RANGE[0]
    high = cost_high if cost_high is not None else typical_cost * COST_RANGE[1]
    g = a.price_growth

    cases = {}
    for name, cost, growth in (
        ("optimistic", low, g["high"]),
        ("likely", typical_cost, g["central"]),
        ("pessimistic", high, g["low"]),
    ):
        cash = cash_by_year(cost, year1_saving, growth, a)
        cases[name] = LifetimeCase(
            name=name,
            installed_cost=cost,
            price_growth=growth,
            cash_by_year=cash,
            payback_years=payback_from_cash(cash),
            lifetime_net_gain=cash[-1],
        )

    return LifetimeResult(
        cases=cases,
        payback_years={
            "low": cases["optimistic"].payback_years,
            "likely": cases["likely"].payback_years,
            "high": cases["pessimistic"].payback_years,
        },
        lifetime_net_gain={
            "low": cases["pessimistic"].lifetime_net_gain,
            "likely": cases["likely"].lifetime_net_gain,
            "high": cases["optimistic"].lifetime_net_gain,
        },
        verdict=verdict_for(cases["likely"].payback_years, a.warranty_years),
        assumptions=a,
    )
