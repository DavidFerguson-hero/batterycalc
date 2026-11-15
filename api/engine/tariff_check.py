"""
Tariff check: is it the battery that saves money, or just a better tariff?

Four annual costs, always:
  A  current tariff, no battery          (the baseline)
  B  best-fit tariff, no battery         ("switch tariff only")
  C  current tariff, with the battery
  D  best-fit tariff, with the battery

"Best fit" is the cheapest option for this household's usage, among the time-of-use
tariffs we model and staying on the current tariff. The best tariff with a battery can
differ from the best tariff without one.

switch_first is raised when switching alone (A − B) captures at least 70% of the best
total saving (A − D): the homeowner should switch first and then decide on a battery.
battery_adds (B − D) is what the battery saves beyond the best switch.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from .simulator import run_simulation
from .tariffs import OPT_TARIFF_KEYS, TARIFFS, Tariff, _flat

SWITCH_FIRST_SHARE = 0.70


@dataclass
class TariffCost:
    key: str
    name: str
    no_battery: float      # £ a year, standing charge included
    with_battery: float


def current_tariff(current_tariff_key: str | None, unit_rate: float, standing_pd: float) -> Tariff:
    """The household's tariff today: a named one, or a flat rate at their own price."""
    if current_tariff_key:
        if current_tariff_key not in TARIFFS:
            raise ValueError(f"Unknown current tariff: {current_tariff_key}")
        return TARIFFS[current_tariff_key]
    return replace(
        TARIFFS["currentFlat"],
        key="current",
        name="Your current tariff",
        slot_rates=_flat(unit_rate),
        standing_charge=standing_pd / 100.0,
    )


def _costs(t: Tariff, days, cap_kwh, max_rate_kw, efficiency, export_rate) -> TariffCost:
    sim = run_simulation(t, cap_kwh, max_rate_kw, efficiency, days, export_rate=export_rate)
    return TariffCost(t.key, t.name, sim.ann_cost_no_battery, sim.ann_cost_with_battery)


def tariff_check(
    days: list[list[float]],
    unit_rate: float,
    standing_pd: float,
    cap_kwh: float,
    max_rate_kw: float,
    efficiency: float,
    export_rate: float = 0.0,
    current_tariff_key: str | None = None,
) -> dict:
    cur_t = current_tariff(current_tariff_key, unit_rate, standing_pd)
    current = _costs(cur_t, days, cap_kwh, max_rate_kw, efficiency, export_rate)
    # A flat rate has no cheap hours, so a battery can't do anything on it (without solar).
    others = [
        _costs(TARIFFS[k], days, cap_kwh, max_rate_kw, efficiency, export_rate)
        for k in OPT_TARIFF_KEYS if k != current_tariff_key
    ]
    options = [current] + others

    best_nb = min(options, key=lambda c: c.no_battery)
    best_wb = min(options, key=lambda c: c.with_battery)

    a, b = current.no_battery, best_nb.no_battery
    c, d = current.with_battery, best_wb.with_battery
    switch_only, battery_on_current, best = a - b, a - c, a - d
    share = switch_only / best if best > 0 else None

    def opt(tc: TariffCost, cost: float) -> dict:
        return {"key": tc.key, "name": tc.name, "annual_cost": round(cost, 2)}

    return {
        "current": {
            "key": current.key, "name": current.name,
            "annual_cost_no_battery": round(a, 2),
            "annual_cost_with_battery": round(c, 2),
        },
        "best_no_battery": opt(best_nb, b),
        "best_with_battery": opt(best_wb, d),
        "savings": {
            "switch_tariff_only": round(switch_only, 2),
            "battery_on_current_tariff": round(battery_on_current, 2),
            "best_tariff_and_battery": round(best, 2),
        },
        "battery_adds": round(b - d, 2),
        "switch_share_of_best": round(share, 3) if share is not None else None,
        "switch_first": share is not None and switch_only > 0 and share >= SWITCH_FIRST_SHARE,
        "by_tariff": sorted(
            (
                {"key": o.key, "name": o.name,
                 "annual_cost_no_battery": round(o.no_battery, 2),
                 "annual_cost_with_battery": round(o.with_battery, 2)}
                for o in options
            ),
            key=lambda r: r["annual_cost_with_battery"],
        ),
    }
