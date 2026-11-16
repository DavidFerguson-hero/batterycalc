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
    end_soc: float = 0.0        # SoC (kWh) left at midnight, carried into the next day
    end_solar_kwh: float = 0.0  # how much of end_soc is stored solar
    solar_storage_value: float = 0.0   # £: stored solar used at home, less export income given up


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
    ann_solar_storage: float = 0.0

    def saving_breakdown(self) -> dict:
        """
        Where the battery's saving (saving_battery_only) comes from.
          time_shifting  — grid electricity charged cheaply and used at dearer times, net of
                           what charging it cost (losses included)
          solar_storage  — spare solar stored and used at home, net of the export income
                           given up (0 without solar)
          other          — stored energy sold back to the grid
        The parts add up to saving_battery_only exactly.
        """
        other = self.ann_export_revenue
        solar = self.ann_solar_storage
        return {
            "time_shifting": round(self.saving_battery_only - other - solar, 2),
            "solar_storage": round(solar, 2),
            "other": round(other, 2),
            "total": round(self.saving_battery_only, 2),
        }


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
    # What adding the battery to the solar saves, split by where the stored energy came from.
    # Parts add up to battery_saving (= saving_solar_battery − saving_solar_only).
    battery_saving: float = 0.0
    battery_time_shifting: float = 0.0  # grid-charged energy used at dearer times, net of charge cost
    battery_solar_storage: float = 0.0  # stored solar used at home, net of the export income given up
    battery_other: float = 0.0          # the battery's starting charge

    def saving_breakdown(self) -> dict:
        return {
            "time_shifting": round(self.battery_time_shifting, 2),
            "solar_storage": round(self.battery_solar_storage, 2),
            "other": round(self.battery_other, 2),
            "total": round(self.battery_saving, 2),
        }


def day_import_cost(day_kwh: list[float], rates: list[float], export_rate: float = 0.0) -> float:
    """
    A day's cost with no battery. Negative half-hours are spare solar (net load), which is
    exported at export_rate.
    """
    return sum(k * r if k > 0 else k * export_rate for k, r in zip(day_kwh, rates))


def simulate_day_full(
    day_kwh: list[float],
    tariff: Tariff,
    cap_kwh: float,
    max_rate_kw: float,
    efficiency: float,          # round-trip, e.g. 0.90
    export_rate: float = 0.0,   # £/kWh — 0 means no export
    start_soc: float | None = None,
    start_solar_kwh: float = 0.0,
) -> DayResult:
    """
    Simulate one day of battery operation.

    day_kwh is the net load: what the home uses less any solar generation. A negative
    half-hour is spare solar.

    Charging: efficiency loss applied on the way in (grid: importing more than stored;
    solar: storing less than was generated).
    Discharging: 1-to-1 offset of consumption (efficiency already paid on charge).
    Battery starts at start_soc (default 30% SoC, used for the first day of a run),
    respects 10% minimum reserve, and reports end_soc for the next day.

    Spare solar charges the battery first; what doesn't fit is exported at export_rate.
    On a day with spare solar, cheap-rate grid charging stops short of full so the solar
    has room (the model knows the day's generation in advance, as a forecast would).
    Grid-charged energy is used in the tariff's discharge slots; stored solar can also be
    used in any half-hour that isn't a charge slot. Without solar the result is the same as
    a battery-only run.
    """
    max_per_slot = max_rate_kw * 0.5    # kWh limit per 30-min slot
    min_soc = cap_kwh * 0.10
    soc = cap_kwh * 0.30 if start_soc is None else min(max(start_soc, min_soc), cap_kwh)
    solar_kwh = min(max(start_solar_kwh, 0.0), max(0.0, soc - min_soc))   # stored solar

    # Spare solar still to come after each half-hour, for the grid-charge ceiling.
    spare_after = [0.0] * 48
    acc = 0.0
    for i in range(47, -1, -1):
        spare_after[i] = acc
        acc += max(0.0, -day_kwh[i])
    has_solar = acc > 0

    cost_no_battery = 0.0
    cost_with_battery = 0.0
    solar_value = 0.0
    soc_profile: list[float] = []
    grid_profile: list[float] = []

    # Self-consumption always comes first — battery only discharges to cover home load.
    # Export is modelled separately at the end (residual SoC after the last discharge slot).
    for i in range(48):
        kwh = day_kwh[i]
        rate = tariff.slot_rates[i]

        if kwh < 0:   # spare solar: store what fits, export the rest
            spare = -kwh
            cost_no_battery -= spare * export_rate
            stored_in = 0.0
            if soc < cap_kwh - 0.01:
                taken = min(spare, max_per_slot, (cap_kwh - soc) / efficiency)
                stored_in = taken * efficiency
                soc += stored_in
                solar_kwh += stored_in
                spare -= taken
                solar_value -= taken * export_rate
            cost_with_battery -= spare * export_rate
            soc_profile.append(soc)
            grid_profile.append(0.0)
            continue

        cost_no_battery += kwh * rate
        grid_import = kwh
        ceiling = max(min_soc, cap_kwh - spare_after[i]) if has_solar else cap_kwh

        if tariff.charge_slots[i] and soc < ceiling - 0.01:
            to_add = min(max_per_slot, ceiling - soc)
            soc += to_add
            grid_import = kwh + to_add / efficiency    # extra draw to account for losses
        elif soc > min_soc and kwh > 0 and (tariff.discharge_slots[i] or (
                solar_kwh > 0 and not tariff.charge_slots[i])):
            avail = soc - min_soc if tariff.discharge_slots[i] else min(solar_kwh, soc - min_soc)
            disc = min(avail, kwh, max_per_slot)
            from_solar = disc if not tariff.discharge_slots[i] else disc * solar_kwh / (soc - min_soc)
            solar_kwh -= from_solar
            solar_value += from_solar * rate
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

    # Energy sold as export has left the battery, so it can't also carry into tomorrow.
    end_soc = max(min_soc, soc - total_export_kwh)
    if total_export_kwh > 0 and soc > min_soc:
        solar_kwh *= (end_soc - min_soc) / (soc - min_soc)

    return DayResult(
        cost_no_battery=cost_no_battery,
        cost_with_battery=cost_with_battery,
        soc_profile=soc_profile,
        grid_profile=grid_profile,
        export_kwh=total_export_kwh,
        export_revenue=total_export_revenue,
        end_soc=end_soc,
        end_solar_kwh=max(0.0, solar_kwh),
        solar_storage_value=solar_value,
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
    tot_solar_value = 0.0
    solar_kwh = 0.0   # stored solar carried from one day to the next
    soc = None   # first day starts at the default 30%; each later day starts where the last ended
    rates = tariff.slot_rates
    discharge = tariff.discharge_slots

    # Consecutive identical days that start at the same charge give identical results,
    # so reuse the previous day's. Exact, and it makes the estimate route (where every
    # day in a month is the same) about as fast as it was with 35 days.
    prev_day: list[float] | None = None
    prev_soc: float | None = None
    prev_solar: float | None = None
    prev = None   # (result, cost_no_batt, cost_current, shifted)

    for day_kwh in days:
        if (prev is not None and soc == prev_soc and solar_kwh == prev_solar
                and (day_kwh is prev_day or day_kwh == prev_day)):
            result, day_no_batt, day_curr, day_shifted = prev
        else:
            day_curr = sum(k * cur_rate if k > 0 else k * export_rate for k in day_kwh)
            day_no_batt = day_import_cost(day_kwh, rates, export_rate)
            result = simulate_day_full(day_kwh, tariff, cap_kwh, max_rate_kw, efficiency,
                                       export_rate, soc, solar_kwh)
            day_shifted = sum(
                max(0.0, k - g) for k, g, dis in zip(day_kwh, result.grid_profile, discharge) if dis
            )
            prev_day, prev_soc, prev_solar = day_kwh, soc, solar_kwh
            prev = (result, day_no_batt, day_curr, day_shifted)

        soc = result.end_soc
        solar_kwh = result.end_solar_kwh
        tot_solar_value += result.solar_storage_value
        tot_curr += day_curr
        tot_no_batt += day_no_batt
        tot_with_batt += result.cost_with_battery
        tot_export_kwh += result.export_kwh
        tot_export_revenue += result.export_revenue
        kwh_shifted += day_shifted
        for i, v in enumerate(result.soc_profile):
            avg_soc[i] += v

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
        ann_solar_storage=tot_solar_value * scale,
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

    Dispatch strategy
    -----------------
    Battery-only (no solar):
      Charge during tariff cheap slots → discharge during tariff peak slots.

    Solar + battery:
      Overnight cheap slots  → grid charges battery up to a ceiling that
                               reserves headroom for expected daytime solar
                               surplus (so solar fills the battery, not exports).
      Daytime                → solar self-consumes first; surplus charges battery;
                               battery discharges any time there is unmet load
                               (maximise self-sufficiency, avoid grid draw).
      Evening peak           → battery discharges to cover load as normal.
      SoC floor of 10% (min_soc) is enforced throughout.

    Overnight charge ceiling (solar+battery)
    ----------------------------------------
    Before the main loop we estimate how much solar surplus will be available
    to charge the battery during the day:
      expected_solar_batt_fill = Σ max(0, solar[i] − load[i])   for all i
    This is an upper bound (assumes battery has infinite headroom when solar
    generates).  The overnight grid charge ceiling is then:
      ceiling = max(min_soc, cap_kwh − expected_solar_batt_fill)
    Result: grid fills the battery to exactly the level that solar is expected
    to top up, so the battery reaches ~100% by mid-afternoon without wasting
    any solar generation as export.

    Returns dict of 48-element lists:
      solar_gen, self_consumed, solar_to_batt, grid_to_batt,
      from_battery, grid_to_load, exported, soc_profile
    """
    max_per_slot = max_rate_kw * 0.5
    has_batt = cap_kwh >= 1.0
    min_soc  = cap_kwh * 0.10 if has_batt else 0.0
    soc      = cap_kwh * 0.30 if has_batt else 0.0

    # Pre-compute overnight charge ceiling for solar+battery
    if has_batt and solar_profile is not None:
        expected_solar_surplus = sum(
            max(0.0, solar_profile[i] - day_kwh[i]) for i in range(48)
        )
        overnight_ceil = max(min_soc, cap_kwh - expected_solar_surplus)
    else:
        overnight_ceil = cap_kwh   # battery-only: fill to 100%

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

        # 2. Solar surplus → battery (up to full capacity, not just the ceiling —
        #    the ceiling only limits overnight grid charging)
        stb = 0.0
        if has_batt and surplus > 0 and soc < cap_kwh - 0.01:
            stb = min(surplus, cap_kwh - soc, max_per_slot)
            soc     += stb
            surplus -= stb
        solar_to_batt[i] = stb

        # 3. Cheap-slot grid top-up → battery
        #    Solar+battery: charge only up to overnight_ceil so that headroom is
        #    preserved for daytime solar generation.
        #    Battery-only: charge to cap_kwh (overnight_ceil == cap_kwh).
        gtb = 0.0
        if has_batt and tariff.charge_slots[i] and soc < overnight_ceil - 0.01:
            headroom = min(max_per_slot - stb, overnight_ceil - soc)
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

    # Pre-compute overnight charge ceiling per day (same logic as calc_day_flows).
    # We use avg_solar_profile as a proxy for every day's expected solar surplus.
    expected_solar_surplus = sum(
        max(0.0, avg_solar_profile[i] - (sum(d[i] for d in days) / len(days)))
        for i in range(48)
    )
    min_soc_global = cap_kwh * 0.10
    overnight_ceil = max(min_soc_global, cap_kwh - expected_solar_surplus)

    min_soc = cap_kwh * 0.10
    soc = cap_kwh * 0.30   # first day only — charge carries over between days
    # Where the stored energy came from, so each kWh used can be credited to its source.
    pool = {"grid": 0.0, "solar": 0.0, "start": soc}
    val_grid = val_solar = val_start = 0.0   # £ of home use covered, by source
    cost_grid = cost_solar = 0.0             # £ to charge from grid / export income given up
    for day_kwh in days:

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

            # 2. Charge from solar surplus (up to full capacity)
            solar_to_batt = 0.0
            if surplus > 0 and soc < cap_kwh - 0.01:
                solar_to_batt = min(surplus, cap_kwh - soc, max_per_slot)
                soc     += solar_to_batt
                surplus -= solar_to_batt
                pool["solar"] += solar_to_batt
                cost_solar    += solar_to_batt * seg_rate

            # 3. Top-up from cheap grid — capped at overnight_ceil so headroom
            #    is preserved for daytime solar generation
            grid_charge = 0.0
            if tariff.charge_slots[i] and soc < overnight_ceil - 0.01:
                headroom = min(max_per_slot - solar_to_batt, overnight_ceil - soc)
                if headroom > 0.001:
                    soc += headroom
                    grid_charge = headroom / efficiency
                    pool["grid"] += headroom
                    cost_grid    += grid_charge * rate

            # 4. Discharge to cover remaining load at any time (self-sufficiency)
            if soc > min_soc and remaining > 0:
                disc = min(soc - min_soc, remaining, max_per_slot)
                stored = pool["grid"] + pool["solar"] + pool["start"]
                for src in pool:
                    share = disc * pool[src] / stored
                    pool[src] -= share
                    if src == "grid":
                        val_grid += share * rate
                    elif src == "solar":
                        val_solar += share * rate
                    else:
                        val_start += share * rate
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

    batt_shift = (val_grid - cost_grid) * scale
    batt_solar = (val_solar - cost_solar) * scale
    batt_other = val_start * scale

    return SolarResult(
        battery_saving=round(ann_solar_only - ann_solar_batt, 2),
        battery_time_shifting=batt_shift,
        battery_solar_storage=batt_solar,
        battery_other=batt_other,
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
