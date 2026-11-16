"""
Which battery size is best value?

For each standard size: pair it with its best tariff, credit the battery only with what it
saves beyond the best tariff available without a battery (as in the tariff check), and run
the lifetime model on that size's installed cost. Best value is the size with the highest
*likely lifetime net gain*: not the biggest saving, which usually belongs to a battery too
big to pay for itself.
"""
from __future__ import annotations

from dataclasses import dataclass

from .costs import fair_price, price_range_for
from .lifetime import lifetime_finance


@dataclass
class SizeOption:
    kwh: float
    label: str
    installed_cost: float
    tariff_key: str
    tariff_name: str
    annual_cost_with_battery: float


def compare_sizes(options: list[SizeOption], best_no_battery_cost: float) -> dict:
    """
    options: the best tariff for each size (one entry per size).
    best_no_battery_cost: £/yr on the best tariff without a battery (tariff check case B).
    """
    if not options:
        raise ValueError("No battery sizes to compare.")

    rows = []
    for o in sorted(options, key=lambda x: x.kwh):
        saving = best_no_battery_cost - o.annual_cost_with_battery
        lt = lifetime_finance(o.installed_cost, saving, *price_range_for(o.kwh, o.installed_cost))
        rows.append({
            "kwh": o.kwh,
            "label": o.label,
            "installed_cost": round(o.installed_cost),
            "tariff_key": o.tariff_key,
            "tariff_name": o.tariff_name,
            "year1_battery_saving": round(saving, 2),
            "payback_years": None if lt.payback_years["likely"] is None else round(lt.payback_years["likely"], 1),
            "lifetime_net_gain": round(lt.lifetime_net_gain["likely"]),
            "verdict": lt.verdict,
        })

    best_i = max(range(len(rows)), key=lambda i: (rows[i]["lifetime_net_gain"], -rows[i]["kwh"]))
    biggest_saving = max(rows, key=lambda r: r["year1_battery_saving"])
    return {
        "best_value": {**rows[best_i], "fair_price": fair_price(rows[best_i]["kwh"])},
        "smaller": rows[best_i - 1] if best_i > 0 else None,
        "larger": rows[best_i + 1] if best_i + 1 < len(rows) else None,
        "biggest_saving_kwh": biggest_saving["kwh"],
        "all_sizes": rows,
    }


def options_from_matrix(matrix: dict[str, list[dict]], tariff_names: dict[str, str],
                        current: dict | None = None) -> list[SizeOption]:
    """
    The cheapest tariff for each battery size, from build_opt_matrix output.
    current: the tariff check's current tariff, kept as a candidate when it isn't in the matrix.
    """
    best: dict[float, SizeOption] = {}
    for tk, rows in matrix.items():
        for r in rows:
            o = SizeOption(
                kwh=r["battery_kwh"], label=r["battery_label"], installed_cost=r["battery_cost"],
                tariff_key=tk, tariff_name=tariff_names.get(tk, tk),
                annual_cost_with_battery=r["ann_cost_with_battery"],
            )
            if o.kwh not in best or o.annual_cost_with_battery < best[o.kwh].annual_cost_with_battery:
                best[o.kwh] = o
    if current and current["key"] not in matrix:
        # A flat rate has no cheap hours: the battery can't save anything on it.
        for kwh, o in list(best.items()):
            if current["annual_cost_with_battery"] < o.annual_cost_with_battery:
                best[kwh] = SizeOption(kwh, o.label, o.installed_cost, current["key"], current["name"],
                                       current["annual_cost_with_battery"])
    return list(best.values())
