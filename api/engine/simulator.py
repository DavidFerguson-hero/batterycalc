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


@dataclass
class SolarResult:
    """Additional financials when a solar profile is included."""
    ann_generation_kwh: float
    ann_self_consumed_kwh: float
    ann_exported_no_batt_kwh: float
    ann_exported_with_batt_kwh: float
    self_consumption_pct: float         # % of solar used on-site (with battery)
    ann_seg_income_no_batt: float
    ann_seg_income_with_batt: float
    ann_cost_solar_only: float          # new tariff + solar, no battery
    ann_cost_solar_battery: float       # new tariff + solar + battery
    saving_solar_only: float            # vs ann_cost_current
    saving_solar_battery: float         # vs ann_cost_current


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

    # Self-consumption always comes first — battery only discharges to cover home load.
    # Export is modelled separately at the end (residual SoC after the last discharge slot).
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
            disc = min(soc - min_soc, kwh, max_per_slot)
            soc -= disc
            grid_import = kwh - disc

        cost_with_battery += max(0.0, grid_import) * rate
        soc_profile.append(soc)
        grid_profile.append(max(0.0, grid_import))

    # Export: any residual SoC above min_soc at the end of the last discharge slot.
    # This is the only energy that can be sold without reducing self-consumption savings.
    # Selling it earns export_rate revenue; it was charged at the cheap overnight rate.
    total_export_kwh = 0.0
    total_export_revenue = 0.0
    if export_rate > 0:
        discharge_indices = [i for i in range(48) if tariff.discharge_slots[i]]
        if discharge_indices:
            last_ds = discharge_indices[-1]
            residual = max(0.0, soc_profile[last_ds] - min_soc)
            if residual > 0:
                total_export_kwh = residual
                total_export_revenue = residual * export_rate
                cost_with_battery -= total_export_revenue

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


# ── Per-slot energy flow ───────────────────────────────────────────────────────

def calc_day_flows(
    day_kwh: list[float],
    tariff: Tariff,
    cap_kwh: float,
    max_rate_kw: float,
    efficiency: float,
    solar_profile: list[float] | None = None,
) -> dict:
    """
    Simulate one representative day and return per-slot energy flow arrays (kWh).

    Dispatch priority (mirrors calc_solar_impact):
      1. Solar self-consumption
      2. Solar surplus → battery
      3. Cheap-slot grid top-up → battery
      4. Battery discharge → remaining load
      5. Remaining solar surplus → export
      6. Remaining load → grid

    Returns dict of 48-element lists:
      solar_gen, self_consumed, solar_to_batt, grid_to_batt,
      from_battery, grid_to_load, exported, soc_profile
    """
    max_per_slot = max_rate_kw * 0.5
    has_batt = cap_kwh >= 1.0
    min_soc  = cap_kwh * 0.10 if has_batt else 0.0
    soc      = cap_kwh * 0.30 if has_batt else 0.0

    solar_gen    = [0.0] * 48
    self_consumed= [0.0] * 48
    solar_to_batt= [0.0] * 48
    grid_to_batt = [0.0] * 48
    from_battery = [0.0] * 48
    grid_to_load = [0.0] * 48
    exported     = [0.0] * 48
    soc_out      = [0.0] * 48

    for i in range(48):
        load = day_kwh[i]
        gen  = solar_profile[i] if solar_profile else 0.0
        solar_gen[i] = gen

        # 1. Solar self-consumption
        sc = min(gen, load)
        self_consumed[i] = sc
        surplus   = gen - sc
        remaining = load - sc

        # 2. Solar surplus → battery
        stb = 0.0
        if has_batt and surplus > 0 and soc < cap_kwh - 0.01:
            stb = min(surplus, cap_kwh - soc, max_per_slot)
            soc     += stb
            surplus -= stb
        solar_to_batt[i] = stb

        # 3. Cheap-slot grid top-up → battery (grid draw, not stored kWh)
        #    Skipped when solar is present: overnight grid pre-fill would consume
        #    all headroom before solar starts, forcing daytime generation to export
        #    instead of charging the battery.  Solar handles filling during the day;
        #    any remaining headroom is implicitly covered by the next night cycle.
        gtb = 0.0
        if has_batt and solar_profile is None and tariff.charge_slots[i] and soc < cap_kwh - 0.01:
            headroom = min(max_per_slot - stb, cap_kwh - soc)
            if headroom > 0.001:
                soc += headroom
                gtb  = headroom / efficiency
        grid_to_batt[i] = gtb

        # 4. Battery discharge → remaining load
        #    Solar+battery: discharge any time there is unmet load (maximise
        #    self-sufficiency, avoid grid draw).  Battery-only: tariff-slot only.
        #    SoC floor of 10% is enforced by min_soc in both cases.
        fb = 0.0
        should_discharge = tariff.discharge_slots[i] or (
            solar_profile is not None and remaining > 0
        )
        if has_batt and should_discharge and soc > min_soc:
            disc = min(soc - min_soc, remaining, max_per_slot)
            soc       -= disc
            remaining -= disc
            fb         = disc
        from_battery[i] = fb

        # 5. Remaining solar surplus → export
        exported[i] = surplus

        # 6. Remaining load from grid
        grid_to_load[i] = max(0.0, remaining)

        soc_out[i] = soc

    r4 = lambda lst: [round(v, 4) for v in lst]
    return {
        "solar_gen":    r4(solar_gen),
        "self_consumed":r4(self_consumed),
        "solar_to_batt":r4(solar_to_batt),
        "grid_to_batt": r4(grid_to_batt),
        "from_battery": r4(from_battery),
        "grid_to_load": r4(grid_to_load),
        "exported":     r4(exported),
        "soc_profile":  r4(soc_out),
    }


# ── Solar ──────────────────────────────────────────────────────────────────────

def calc_solar_impact(
    tariff: Tariff,
    cap_kwh: float,
    max_rate_kw: float,
    efficiency: float,
    days: list[list[float]],
    avg_solar_profile: list[float],   # 48-slot annual-avg kWh/slot
    seg_rate: float,                  # £/kWh export rate
    ann_cost_current: float,          # baseline from run_simulation
    sc_new: float,                    # tariff.standing_charge * 365
) -> SolarResult:
    """
    Compute annual costs and savings when solar generation is overlaid.

    Dispatch priority per slot:
      1. Solar self-consumption (load met directly from panels)
      2. Surplus solar charges battery (free electrons, no grid draw)
      3. Remaining battery headroom filled from cheap grid (charge slot)
      4. Battery discharges to cover remaining load (discharge slot)
      5. Any remaining solar surplus exported at seg_rate
    """
    if not days:
        raise ValueError("No days to simulate.")

    max_per_slot = max_rate_kw * 0.5
    n_days = len(days)
    scale  = 365.0 / n_days

    tot_solar_only   = 0.0   # cost: new tariff + solar, no battery
    tot_solar_batt   = 0.0   # cost: new tariff + solar + battery
    tot_generation   = 0.0
    tot_self_consumed= 0.0
    tot_export_nb    = 0.0   # exported with no battery
    tot_export_wb    = 0.0   # exported with battery

    for day_kwh in days:
        soc = cap_kwh * 0.30
        min_soc = cap_kwh * 0.10

        day_gen = sum(avg_solar_profile)
        tot_generation += day_gen

        for i in range(48):
            load = day_kwh[i]
            rate = tariff.slot_rates[i]
            gen  = avg_solar_profile[i]

            # ── Solar-only (no battery) ──────────────────────────
            self_nb  = min(gen, load)
            surp_nb  = gen - self_nb
            grid_nb  = load - self_nb
            tot_export_nb  += surp_nb
            tot_solar_only += max(0.0, grid_nb) * rate - surp_nb * seg_rate

            # ── Solar + battery ──────────────────────────────────
            self_use = min(gen, load)
            surplus  = gen - self_use
            remaining = load - self_use
            tot_self_consumed += self_use

            # 2. Charge from solar surplus
            solar_to_batt = 0.0
            if surplus > 0 and soc < cap_kwh - 0.01:
                solar_to_batt = min(surplus, cap_kwh - soc, max_per_slot)
                soc     += solar_to_batt
                surplus -= solar_to_batt

            # 3. Top-up from cheap grid
            grid_charge = 0.0
            if tariff.charge_slots[i] and soc < cap_kwh - 0.01:
                headroom = min(max_per_slot - solar_to_batt, cap_kwh - soc)
                if headroom > 0.001:
                    soc += headroom
                    grid_charge = headroom / efficiency

            # 4. Discharge to cover remaining load
            if tariff.discharge_slots[i] and soc > min_soc:
                disc = min(soc - min_soc, remaining, max_per_slot)
                soc       -= disc
                remaining -= disc

            # 5. Export remaining surplus
            export = surplus
            tot_export_wb += export

            net_grid = remaining + grid_charge
            tot_solar_batt += max(0.0, net_grid) * rate - export * seg_rate

    ann_solar_only   = tot_solar_only * scale + sc_new
    ann_solar_batt   = tot_solar_batt * scale + sc_new
    ann_gen          = tot_generation * scale
    ann_self         = tot_self_consumed * scale
    ann_exp_nb       = tot_export_nb * scale
    ann_exp_wb       = tot_export_wb * scale
    self_pct         = (ann_self / ann_gen * 100.0) if ann_gen > 0 else 0.0

    return SolarResult(
        ann_generation_kwh=round(ann_gen, 0),
        ann_self_consumed_kwh=round(ann_self, 0),
        ann_exported_no_batt_kwh=round(ann_exp_nb, 0),
        ann_exported_with_batt_kwh=round(ann_exp_wb, 0),
        self_consumption_pct=round(self_pct, 1),
        ann_seg_income_no_batt=round(ann_exp_nb * seg_rate, 2),
        ann_seg_income_with_batt=round(ann_exp_wb * seg_rate, 2),
        ann_cost_solar_only=round(ann_solar_only, 2),
        ann_cost_solar_battery=round(ann_solar_batt, 2),
        saving_solar_only=round(ann_cost_current - ann_solar_only, 2),
        saving_solar_battery=round(ann_cost_current - ann_solar_batt, 2),
    )
