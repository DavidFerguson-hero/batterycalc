"""
"What would make it pay back?" (task 1.7, story H14)

When the verdict is not_yet, three levers the homeowner can pull:
  1. Price    — the installed price at which the likely payback is within the warranty
                (and the lower price at which it would be "worth it").
  2. Tariff   — whether pairing the battery with the best tariff for it changes the verdict.
  3. EV       — whether adding a planned electric car changes the verdict.
"""
from __future__ import annotations

import math

from .lifetime import WORTH_IT_SHARE, LifetimeAssumptions, cash_by_year, lifetime_finance

VERDICT_RANK = {"not_yet": 0, "borderline": 1, "worth_it": 2}


def max_price_for_payback(
    year1_saving: float,
    within_years: float,
    assumptions: LifetimeAssumptions | None = None,
) -> float | None:
    """
    The highest installed price whose likely payback is within `within_years`.

    Paying back "for good" by year N means the cumulative cash is >= 0 at the end of
    every year from N to the end of the battery's life, so the price can be at most the
    smallest cumulative net saving over those years (the inverter replacement included).
    None if no positive price works.
    """
    a = assumptions or LifetimeAssumptions()
    cum = cash_by_year(0.0, year1_saving, a.price_growth["central"], a)   # starts at 0
    first = max(1, math.ceil(within_years))
    if first > a.battery_life_years:
        return None
    price = min(cum[first:])
    return price if price > 0 else None


def price_lever(year1_saving: float, current_price: float,
                assumptions: LifetimeAssumptions | None = None) -> dict:
    a = assumptions or LifetimeAssumptions()
    within = max_price_for_payback(year1_saving, a.warranty_years, a)
    worth = max_price_for_payback(year1_saving, WORTH_IT_SHARE * a.warranty_years, a)
    return {
        "current_price": round(current_price),
        "price_for_payback_within_warranty": None if within is None else math.floor(within),
        "price_for_worth_it": None if worth is None else math.floor(worth),
    }


def verdict_change(year1_saving: float, price: float, current_verdict: str) -> dict:
    lt = lifetime_finance(price, year1_saving)
    payback = lt.payback_years["likely"]
    return {
        "year1_battery_saving": round(year1_saving, 2),
        "payback_years": None if payback is None else round(payback, 1),
        "verdict": lt.verdict,
        "changes_verdict": VERDICT_RANK[lt.verdict] > VERDICT_RANK[current_verdict],
    }
