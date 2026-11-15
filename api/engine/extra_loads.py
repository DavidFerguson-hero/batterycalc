"""
Extra household loads that change the battery case: an electric car (EV) and a heat pump.

Each can be:
  "none"      — not part of the picture
  "have"      — already in the home. For an uploaded CSV it's already in the readings, so
                nothing is added. For the estimate route the annual figure is taken to include
                it, so that share is moved into the load's own pattern (overnight charging,
                winter heating) and the rest keeps the normal household shape.
  "planning"  — not yet in the home: its half-hourly use is added on top.

All figures are kWh. Approximate defaults are marked; they should be reviewed in task 3.1.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

SLOTS = 48
Status = Literal["none", "have", "planning"]

# ── EV ────────────────────────────────────────────────────────────────────────
EV_KWH_PER_MILE = 0.30         # plan default; a typical family EV is 0.25–0.35
EV_DEFAULT_MILES = 7000        # roughly the average annual mileage of a UK car (approximate)
EV_DEFAULT_WINDOW = ("00:30", "04:30")   # cheap on every overnight tariff we model
EV_CHARGER_KW = 7.0            # home wallbox; limits kWh per half-hour

# ── Heat pump ─────────────────────────────────────────────────────────────────
HP_DEFAULT_EFFICIENCY = 3.0    # seasonal COP: kWh of heat per kWh of electricity (plan default)

# Space heating + hot water demand by EPC rating, kWh of heat per m² of floor a year.
# APPROXIMATE: typical UK figures by efficiency band, for review in task 3.1.
HEAT_DEMAND_PER_M2 = {"A": 50, "B": 65, "C": 90, "D": 120, "E": 150, "F": 185, "G": 220}
HEAT_DEMAND_PER_M2_UNKNOWN = 120
DEFAULT_FLOOR_AREA_M2 = {"flat": 60, "terraced": 80, "semi": 90, "detached": 130}

# Share of the year's heat used in each month (Jan..Dec). Hot water keeps summer above zero.
# APPROXIMATE, shaped like UK heating degree days.
_HP_MONTHLY_RAW = [15.5, 13.5, 12.0, 8.5, 5.5, 3.5, 3.0, 3.0, 4.5, 8.0, 11.5, 15.0]
HP_MONTHLY = [v / sum(_HP_MONTHLY_RAW) for v in _HP_MONTHLY_RAW]

# Daily heat pump pattern: runs low overnight, more in the morning and evening.
_HP_DAILY_RAW = (
    [0.6] * 12 +             # 00:00–06:00 low, steady
    [1.6] * 6 +              # 06:00–09:00 morning warm-up and hot water
    [0.9] * 14 +             # 09:00–16:00 tick-over
    [1.5] * 12 +             # 16:00–22:00 evening
    [0.8] * 4                # 22:00–00:00 wind down
)
HP_DAILY = [v / sum(_HP_DAILY_RAW) for v in _HP_DAILY_RAW]

# Never strip more than this share of an estimate's annual figure out as "already have".
_MAX_HAVE_SHARE = 0.7


@dataclass
class EVSettings:
    status: Status = "none"
    annual_miles: float = EV_DEFAULT_MILES
    kwh_per_mile: float = EV_KWH_PER_MILE
    charge_start: str = EV_DEFAULT_WINDOW[0]
    charge_end: str = EV_DEFAULT_WINDOW[1]

    @property
    def annual_kwh(self) -> float:
        return self.annual_miles * self.kwh_per_mile


@dataclass
class HeatPumpSettings:
    status: Status = "none"
    heat_demand_kwh: float | None = None   # if known; otherwise from floor area and EPC rating
    floor_area_m2: float | None = None
    epc_rating: str | None = None
    efficiency: float = HP_DEFAULT_EFFICIENCY

    def heat_demand(self, property_type: str = "semi") -> float:
        if self.heat_demand_kwh:
            return self.heat_demand_kwh
        area = self.floor_area_m2 or DEFAULT_FLOOR_AREA_M2.get(property_type, 90)
        per_m2 = HEAT_DEMAND_PER_M2.get((self.epc_rating or "").upper()[:1], HEAT_DEMAND_PER_M2_UNKNOWN)
        return area * per_m2

    def annual_kwh(self, property_type: str = "semi") -> float:
        return self.heat_demand(property_type) / self.efficiency


def _slot(hhmm: str) -> int:
    h, m = (int(x) for x in hhmm.split(":"))
    if not (0 <= h < 24 and m in (0, 30)):
        raise ValueError(f"Charging times must be on the hour or half hour, got {hhmm!r}")
    return h * 2 + m // 30


def ev_window_slots(start: str, end: str) -> list[int]:
    """Half-hour slots from start up to (not including) end; wraps past midnight."""
    a, b = _slot(start), _slot(end)
    if a == b:
        raise ValueError("EV charging window can't be empty")
    return list(range(a, b)) if a < b else list(range(a, SLOTS)) + list(range(0, b))


def ev_day(ev: EVSettings) -> list[float]:
    """One day's EV charging (kWh per slot): the daily need spread over the charging window."""
    slots = ev_window_slots(ev.charge_start, ev.charge_end)
    daily = ev.annual_kwh / 365.0
    if daily > len(slots) * EV_CHARGER_KW * 0.5 + 1e-9:
        raise ValueError(
            f"{daily:.1f} kWh a day won't fit in a {len(slots) / 2:g}-hour window "
            f"on a {EV_CHARGER_KW:g} kW charger"
        )
    day = [0.0] * SLOTS
    for i in slots:
        day[i] = daily / len(slots)
    return day


def hp_days(hp: HeatPumpSettings, dates: list[date] | None, n_days: int, property_type: str) -> list[list[float]]:
    """Heat pump use for each day: annual kWh × that month's share, spread over its days."""
    annual = hp.annual_kwh(property_type)
    if dates is None:   # undated data: no seasons to follow, spread evenly
        per_day = [annual / 365.0] * n_days
    else:
        days_in_month: dict[tuple[int, int], int] = {}
        for d in dates:
            days_in_month[(d.year, d.month)] = days_in_month.get((d.year, d.month), 0) + 1
        # Each calendar month gets its share; scale so a 365-day run totals the annual figure.
        weight = [HP_MONTHLY[d.month - 1] / days_in_month[(d.year, d.month)] for d in dates]
        scale = annual * len(dates) / 365.0 / sum(weight)
        per_day = [w * scale for w in weight]
    return [[v * s for s in HP_DAILY] for v in per_day]


@dataclass
class ExtraLoadsResult:
    days: list[list[float]]
    ev_kwh_added: float = 0.0          # added on top ("planning")
    hp_kwh_added: float = 0.0
    ev_kwh_reshaped: float = 0.0       # moved into the load's own pattern ("have", estimate route)
    hp_kwh_reshaped: float = 0.0
    hp_heat_demand_kwh: float | None = None

    def summary(self) -> dict:
        return {
            "ev_kwh_added": round(self.ev_kwh_added, 1),
            "heat_pump_kwh_added": round(self.hp_kwh_added, 1),
            "ev_kwh_already_included": round(self.ev_kwh_reshaped, 1),
            "heat_pump_kwh_already_included": round(self.hp_kwh_reshaped, 1),
            "heat_pump_heat_demand_kwh": round(self.hp_heat_demand_kwh, 0) if self.hp_heat_demand_kwh else None,
        }


def apply_extra_loads(
    days: list[list[float]],
    dates: list[date] | None,
    ev: EVSettings | None = None,
    hp: HeatPumpSettings | None = None,
    *,
    route: Literal["estimate", "upload"],
    property_type: str = "semi",
) -> ExtraLoadsResult:
    """Return new days with the EV and heat pump applied as described in the module docstring."""
    ev = ev or EVSettings()
    hp = hp or HeatPumpSettings()
    n = len(days)
    out = ExtraLoadsResult(days=[list(d) for d in days])
    if hp.status != "none":
        out.hp_heat_demand_kwh = hp.heat_demand(property_type)

    add: list[list[float]] = []      # profiles to add on top
    carve: list[list[list[float]]] = []   # "have" profiles (estimate route) to carve out of the base

    if ev.status != "none":
        ev_profile = ev_day(ev)
        ev_profiles = [ev_profile] * n
        if ev.status == "planning":
            add.append(ev_profiles)
            out.ev_kwh_added = sum(ev_profile) * n
        elif route == "estimate":
            carve.append(ev_profiles)
            out.ev_kwh_reshaped = sum(ev_profile) * n

    if hp.status != "none":
        hp_profiles = hp_days(hp, dates, n, property_type)
        hp_total = sum(map(sum, hp_profiles))
        if hp.status == "planning":
            add.append(hp_profiles)
            out.hp_kwh_added = hp_total
        elif route == "estimate":
            carve.append(hp_profiles)
            out.hp_kwh_reshaped = hp_total

    if carve:
        base_total = sum(map(sum, out.days))
        carved_total = sum(sum(map(sum, p)) for p in carve)
        if carved_total > base_total * _MAX_HAVE_SHARE:
            # The annual figure is too small to include all of this; keep the household share
            # and scale the existing loads down so the year still adds up.
            k = base_total * _MAX_HAVE_SHARE / carved_total
            carve = [[[v * k for v in day] for day in p] for p in carve]
            out.ev_kwh_reshaped *= k
            out.hp_kwh_reshaped *= k
            carved_total *= k
        keep = (base_total - carved_total) / base_total
        out.days = [[v * keep for v in day] for day in out.days]
        add.extend(carve)

    for profiles in add:
        for day, extra in zip(out.days, profiles):
            for i in range(SLOTS):
                day[i] += extra[i]
    return out
