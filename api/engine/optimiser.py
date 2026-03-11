"""
Optimisation matrix — all tariffs × all standard battery sizes.

Returns a dict keyed by tariff_key, each containing a list of result dicts
(one per battery size) sorted by ascending battery size.
"""
from __future__ import annotations
import math
from .tariffs import TARIFFS, OPT_TARIFF_KEYS, OPT_BATTERIES, Tariff
from .simulator import run_simulation, SimResult
from .payback import calc_payback, PaybackResult


def _nearest_batt_kwh(kwh: float) -> float:
    sizes = [b["kwh"] for b in OPT_BATTERIES]
    return min(sizes, key=lambda s: abs(s - kwh))


def build_opt_matrix(
    days: list[list[float]],
    current_rate: float | None,
    max_rate_kw: float,
    efficiency: float,
    selected_cap_kwh: float,
    selected_cost_gbp: float,
    inflation_pct: float = 5.0,
) -> dict:
    """
    Run simulation for every tariff in OPT_TARIFF_KEYS × every battery in OPT_BATTERIES.

    For the battery size nearest to selected_cap_kwh, the installed cost is taken from
    selected_cost_gbp (the user's slider) rather than the default price list. This makes
    the heatmap reactive to whatever cost the user has entered.
    """
    nearest_kwh = _nearest_batt_kwh(selected_cap_kwh)
    matrix: dict[str, list[dict]] = {}

    for tk in OPT_TARIFF_KEYS:
        tariff = TARIFFS[tk]
        rows = []
        for batt in OPT_BATTERIES:
            batt_cost = selected_cost_gbp if batt["kwh"] == nearest_kwh else batt["cost"]

            sim = run_simulation(
                tariff=tariff,
                cap_kwh=batt["kwh"],
                max_rate_kw=max_rate_kw,
                efficiency=efficiency,
                days=days,
                current_rate=current_rate,
            )
            if sim is None:
                continue

            pb = calc_payback(batt_cost, sim.total_saving, inflation_pct)

            rows.append({
                "tariff_key": tk,
                "tariff_name": tariff.name,
                "tariff_color": tariff.color,
                "battery_kwh": batt["kwh"],
                "battery_label": batt["label"],
                "battery_cost": batt_cost,
                "ann_cost_current": round(sim.ann_cost_current, 2),
                "ann_cost_no_battery": round(sim.ann_cost_no_battery, 2),
                "ann_cost_with_battery": round(sim.ann_cost_with_battery, 2),
                "saving_battery_only": round(sim.saving_battery_only, 2),
                "saving_tariff_switch": round(sim.saving_tariff_switch, 2),
                "total_saving": round(sim.total_saving, 2),
                "payback_years": round(pb.years, 2) if pb.years != math.inf else None,
                "roi_10yr": pb.roi_10yr,
                "cumulative_savings": pb.cumulative,
            })

        matrix[tk] = rows

    return matrix
