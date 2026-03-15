"""
Battery simulation engine — direct Python port of simulateDay / simulateDayFull / runSimulation.

All monetary values are in £ (not pence) — slot_rates are stored as £/kWh (e.g. 0.07).
"""
from __future__ import annotations
from dataclasses import dataclass
from .tariffs import Tariff

IMPLIED_RATE = 0.2816  # £/kWh — Ofgem Q1 2026 standard variable


@dataclass
class DayResult:
    cost_no_battery: float
    cost_with_battery: float
    soc_profile: list[float]    # SoC (kWh) at end of each slot
    grid_profile: list[float]   # Grid import (kWh) each slot
    export_kwh: float = 0.0
    export_revenue: float = 0.0


@dataclass
class SimResult:
    ann_cost_current: float
    ann_cost_no_battery: float
    ann_cost_with_battery: float
    saving_battery_only: float
    saving_tariff_switch: float
    total_saving: float
    avg_soc_profile: list[float]
    avg_kwh_shifted_per_day: float
    ann_export_revenue: float = 0.0
    ann_kwh_exported: float = 0.0


def simulate_day_full(
    day_kwh: list[float],
    tariff: Tariff,
    cap_kwh: float,
    max_rate_kw: float,
    efficiency: float,          # round-trip, e.g. 0.90
    export_rate: float = 0.0,   # £/kWh — 0 means no export
) -> DayResult:
    """
    Simulate one day of battery operation.

    Charging: efficiency loss applied on grid-side (importing more than stored).
    Discharging: 1-to-1 offset of consumption (efficiency already paid on charge).
    Battery starts at 30% SoC, respects 10% minimum reserve.
    """
    max_per_slot = max_rate_kw * 0.5    # kWh limit per 30-min slot
    min_soc = cap_kwh * 0.10
    soc = cap_kwh * 0.30

    cost_no_battery = 0.0
    cost_with_battery = 0.0
    soc_profile: list[float] = []
    grid_profile: list[float] = []
    total_export_kwh = 0.0
    total_export_revenue = 0.0

    for i in range(48):
        kwh = day_kwh[i]
        rate = tariff.slot_rates[i]
        cost_no_battery += kwh * rate

        grid_import = kwh

        if tariff.charge_slots[i] and soc < cap_kwh - 0.01:
            to_add = min(max_per_slot, cap_kwh - soc)
            soc += to_add
            grid_import = kwh + to_add / efficiency    # extra draw to account for losses
        elif tariff.discharge_slots[i] and soc > min_soc:
            if export_rate > 0:
                # Export mode: discharge as much as possible, sell surplus to grid
                disc = min(soc - min_soc, max_per_slot)
            else:
                # No export: only discharge to cover consumption
                disc = min(soc - min_soc, kwh, max_per_slot)
            soc -= disc
            grid_import = kwh - disc

        if grid_import < 0 and export_rate > 0:
            # Battery provided more than needed — export surplus
            export_kwh_slot = -grid_import
            cost_with_battery += 0.0
            cost_with_battery -= export_kwh_slot * export_rate   # revenue reduces cost
            # Track export
            total_export_kwh += export_kwh_slot
            total_export_revenue += export_kwh_slot * export_rate
        else:
            cost_with_battery += max(0.0, grid_import) * rate

        soc_profile.append(soc)
        grid_profile.append(max(0.0, grid_import))

    return DayResult(
        cost_no_battery=cost_no_battery,
        cost_with_battery=cost_with_battery,
        soc_profile=soc_profile,
        grid_profile=grid_profile,
        export_kwh=total_export_kwh,
        export_revenue=total_export_revenue,
    )


def run_simulation(
    tariff: Tariff,
    cap_kwh: float,
    max_rate_kw: float,
    efficiency: float,
    days: list[list[float]],        # each inner list = 48 half-hourly kWh values
    current_rate: float | None = None,
    current_sc_pd: float = 53.0,    # user's current standing charge in pence/day
    export_rate: float = 0.0,
) -> SimResult | None:
    """
    Run the simulation across all uploaded days and annualise.

    current_rate:  the user's existing flat rate (£/kWh). Falls back to IMPLIED_RATE.
    current_sc_pd: the user's current standing charge in pence/day (default 53p).
    Returns None if days is empty.
    """
    if not days:
        return None

    cur_rate = current_rate if current_rate is not None else IMPLIED_RATE
    n_days = len(days)
    scale = 365.0 / n_days

    sc_current = (current_sc_pd / 100.0) * 365   # user-supplied standing charge
    sc_new = tariff.standing_charge * 365

    tot_curr = 0.0
    tot_no_batt = 0.0
    tot_with_batt = 0.0
    kwh_shifted = 0.0
    avg_soc = [0.0] * 48
    tot_export_kwh = 0.0
    tot_export_revenue = 0.0

    for day_kwh in days:
        for i in range(48):
            tot_curr += day_kwh[i] * cur_rate
            tot_no_batt += day_kwh[i] * tariff.slot_rates[i]

        result = simulate_day_full(day_kwh, tariff, cap_kwh, max_rate_kw, efficiency, export_rate)
        tot_with_batt += result.cost_with_battery
        tot_export_kwh += result.export_kwh
        tot_export_revenue += result.export_revenue

        for i in range(48):
            avg_soc[i] += result.soc_profile[i]
            if tariff.discharge_slots[i]:
                kwh_shifted += max(0.0, day_kwh[i] - result.grid_profile[i])

    avg_soc = [v / n_days for v in avg_soc]

    ann_cost_current = tot_curr * scale + sc_current
    ann_cost_no_battery = tot_no_batt * scale + sc_new
    ann_cost_with_battery = tot_with_batt * scale + sc_new

    return SimResult(
        ann_cost_current=ann_cost_current,
        ann_cost_no_battery=ann_cost_no_battery,
        ann_cost_with_battery=ann_cost_with_battery,
        saving_battery_only=ann_cost_no_battery - ann_cost_with_battery,
        saving_tariff_switch=ann_cost_current - ann_cost_no_battery,
        total_saving=ann_cost_current - ann_cost_with_battery,
        avg_soc_profile=avg_soc,
        avg_kwh_shifted_per_day=kwh_shifted / n_days,
        ann_export_revenue=tot_export_revenue * scale,
        ann_kwh_exported=tot_export_kwh * scale,
    )
