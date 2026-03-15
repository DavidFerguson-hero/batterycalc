"""
Tariff definitions — ported from the JS TARIFFS object.
Each tariff has:
  slot_rates      list[float]  — pence/kWh for each of the 48 half-hour slots
  charge_slots    list[bool]   — True = battery charges in this slot
  discharge_slots list[bool]   — True = battery discharges in this slot
  standing_charge float        — £/day
"""
from dataclasses import dataclass, field
from typing import Optional


def _flat(rate: float) -> list[float]:
    return [rate] * 48


def _slots(*ranges: tuple[int, int]) -> list[bool]:
    a = [False] * 48
    for lo, hi in ranges:
        for i in range(lo, hi + 1):
            a[i] = True
    return a


@dataclass
class Tariff:
    key: str
    name: str
    supplier: str
    description: str
    color: str
    slot_rates: list[float]
    charge_slots: list[bool]
    discharge_slots: list[bool]
    standing_charge: float          # £/day
    is_flat_rate: bool = False
    is_dynamic: bool = False
    export_rate: float = 0.0        # £/kWh — 0.0 means no export


def _make_octopus_go() -> list[float]:
    r = _flat(0.3872)
    for i in range(0, 11): r[i] = 0.07   # 00:00–05:30
    r[47] = 0.07                           # 23:30
    return r

def _make_intelligent_octopus() -> list[float]:
    r = _flat(0.38)
    for i in range(0, 11): r[i] = 0.09
    r[46] = r[47] = 0.09
    return r

def _make_octopus_cosy() -> list[float]:
    r = _flat(0.28)
    for i in range(8, 14):  r[i] = 0.12  # 04:00–07:00 cosy
    for i in range(26, 32): r[i] = 0.12  # 13:00–16:00 cosy
    for i in range(32, 42): r[i] = 0.50  # 16:00–21:00 peak
    return r

def _make_economy7() -> list[float]:
    r = _flat(0.33)
    for i in range(1, 15): r[i] = 0.09   # 00:30–07:30
    return r

def _make_eon_next_drive() -> list[float]:
    r = _flat(0.35)
    for i in range(0, 14): r[i] = 0.085  # 00:00–07:00
    return r

def _make_edf_go_electric() -> list[float]:
    r = _flat(0.34)
    for i in range(0, 14): r[i] = 0.08   # 00:00–07:00
    return r

def _make_edf_freephase() -> list[float]:
    r = _flat(0.221)
    for i in range(0, 12): r[i] = 0.170  # 00:00–05:30 green (night)
    r[46] = r[47] = 0.170                 # 23:00–23:30 green (night)
    for i in range(32, 38): r[i] = 0.384 # 16:00–18:30 red (peak)
    return r

def _make_edf_freephase_dynamic() -> list[float]:
    r = _flat(0.262)
    for i in range(0, 12): r[i] = 0.039  # 00:00–05:30 green (night)
    r[46] = r[47] = 0.039                 # 23:00–23:30 green (night)
    for i in range(32, 38): r[i] = 0.431 # 16:00–18:30 red (peak)
    return r

def _make_scottish_power() -> list[float]:
    r = _flat(0.36)
    for i in range(0, 14): r[i] = 0.10   # 00:00–07:00
    r[46] = r[47] = 0.10                  # 23:00–23:30
    return r

def _make_octopus_flux_import() -> list[float]:
    r = _flat(0.23)
    for i in range(0, 10): r[i] = 0.21   # 00:00–05:00 cheap
    r[46] = r[47] = 0.21                   # 23:00–23:30 cheap
    for i in range(32, 38): r[i] = 0.43   # 16:00–19:00 peak
    return r


# Ofgem Q1 2026 standard variable — fallback when CSV has no cost column
IMPLIED_RATE = 0.2816

TARIFFS: dict[str, Tariff] = {
    "currentFlat": Tariff(
        key="currentFlat",
        name="Current Tariff (Standard Variable)",
        supplier="Your Current Supplier",
        description="Flat-rate tariff. A battery alone saves nothing on a flat rate — savings come from switching to a Time-of-Use tariff.",
        color="#8b949e",
        slot_rates=_flat(IMPLIED_RATE),
        charge_slots=[False] * 48,
        discharge_slots=[False] * 48,
        standing_charge=0.53,
        is_flat_rate=True,
    ),
    "octopusGo": Tariff(
        key="octopusGo",
        name="Octopus Go",
        supplier="Octopus Energy",
        description="Night 7p/kWh (23:30–05:30) · Day 38.72p/kWh. Lowest overnight rate — maximises battery savings.",
        color="#ff6b35",
        slot_rates=_make_octopus_go(),
        charge_slots=_slots((0, 10), (47, 47)),
        discharge_slots=_slots((11, 46)),
        standing_charge=0.47,
        export_rate=0.075,
    ),
    "intelligentOctopus": Tariff(
        key="intelligentOctopus",
        name="Intelligent Octopus Go",
        supplier="Octopus Energy",
        description="Smart overnight 9p/kWh (23:00–05:30) · Day 38p/kWh. AI-managed charging.",
        color="#c56bff",
        slot_rates=_make_intelligent_octopus(),
        charge_slots=_slots((0, 10), (46, 47)),
        discharge_slots=_slots((11, 45)),
        standing_charge=0.47,
        export_rate=0.075,
    ),
    "octopusCosy": Tariff(
        key="octopusCosy",
        name="Octopus Cosy",
        supplier="Octopus Energy",
        description="Cosy 12p/kWh (04:00–07:00 & 13:00–16:00) · Peak 50p/kWh (16:00–21:00) · Standard 28p.",
        color="#ff3d6b",
        slot_rates=_make_octopus_cosy(),
        charge_slots=_slots((8, 13), (26, 31)),
        discharge_slots=_slots((32, 41)),
        standing_charge=0.47,
        export_rate=0.075,
    ),
    "economy7": Tariff(
        key="economy7",
        name="Economy 7",
        supplier="Multiple Suppliers",
        description="Night 9p/kWh (00:30–07:30) · Day 33p/kWh. Classic 7-hour off-peak window.",
        color="#3d8bff",
        slot_rates=_make_economy7(),
        charge_slots=_slots((1, 14)),
        discharge_slots=_slots((0, 0), (15, 47)),
        standing_charge=0.53,
        export_rate=0.075,
    ),
    "eonNextDrive": Tariff(
        key="eonNextDrive",
        name="E.ON Next Drive",
        supplier="E.ON Energy",
        description="Night 8.5p/kWh (00:00–07:00) · Day 35p/kWh. Designed for EVs and home batteries.",
        color="#e60026",
        slot_rates=_make_eon_next_drive(),
        charge_slots=_slots((0, 13)),
        discharge_slots=_slots((14, 47)),
        standing_charge=0.53,
        export_rate=0.085,
    ),
    "edfGoElectric": Tariff(
        key="edfGoElectric",
        name="EDF GoElectric Overnight",
        supplier="EDF Energy",
        description="Night 8p/kWh (00:00–07:00) · Day 34p/kWh.",
        color="#0066cc",
        slot_rates=_make_edf_go_electric(),
        charge_slots=_slots((0, 13)),
        discharge_slots=_slots((14, 47)),
        standing_charge=0.50,
        export_rate=0.080,
    ),
    "edfFreePhase": Tariff(
        key="edfFreePhase",
        name="EDF FreePhase Static",
        supplier="EDF Energy",
        description="Night 17p/kWh (23:00–06:00) · Peak 38.4p/kWh (16:00–19:00) · Day 22.1p/kWh · SC 53.2p.",
        color="#0099d4",
        slot_rates=_make_edf_freephase(),
        charge_slots=_slots((0, 11), (46, 47)),
        discharge_slots=_slots((32, 37)),
        standing_charge=0.532,
        export_rate=0.075,
    ),
    "edfFreePhaseDynamic": Tariff(
        key="edfFreePhaseDynamic",
        name="EDF FreePhase Dynamic",
        supplier="EDF Energy",
        description="Night ~3.9p/kWh (23:00–06:00) · Peak ~43p/kWh (16:00–19:00) · Day ~26p/kWh · SC 53.2p. Rates change daily — figures are recent averages.",
        color="#38bdf8",
        slot_rates=_make_edf_freephase_dynamic(),
        charge_slots=_slots((0, 11), (46, 47)),
        discharge_slots=_slots((12, 45)),
        standing_charge=0.532,
        is_dynamic=True,
        export_rate=0.075,
    ),
    "scottishPower": Tariff(
        key="scottishPower",
        name="Scottish Power Smart Tariff",
        supplier="Scottish Power",
        description="Night 10p/kWh (23:00–07:00) · Day 36p/kWh. Eight-hour overnight window.",
        color="#009933",
        slot_rates=_make_scottish_power(),
        charge_slots=_slots((0, 13), (46, 47)),
        discharge_slots=_slots((14, 45)),
        standing_charge=0.55,
        export_rate=0.075,
    ),
    "octopusFlux": Tariff(
        key="octopusFlux",
        name="Octopus Flux",
        supplier="Octopus Energy",
        description="Flux Night 21p (23:00–05:00) · Day 23p · Peak 43p (16:00–19:00). Designed for battery + solar. Export: Peak 35p (16:00–19:00) · Standard 15p.",
        color="#f59e0b",
        slot_rates=_make_octopus_flux_import(),
        charge_slots=_slots((0, 9), (46, 47)),       # 23:00–05:00
        discharge_slots=_slots((32, 37)),              # 16:00–19:00
        standing_charge=0.47,
        export_rate=0.15,   # flat default; peak is higher but we use flat average
    ),
    "britishGasSV": Tariff(
        key="britishGasSV",
        name="British Gas Standard Variable",
        supplier="British Gas",
        description="Standard Variable at Ofgem Q1 2026 price cap (~24.5p/kWh). Flat rate.",
        color="#003da5",
        slot_rates=_flat(0.245),
        charge_slots=[False] * 48,
        discharge_slots=[False] * 48,
        standing_charge=0.61,
        is_flat_rate=True,
    ),
}

OPT_TARIFF_KEYS = [
    "octopusGo", "intelligentOctopus", "octopusCosy", "octopusFlux", "economy7",
    "eonNextDrive", "edfGoElectric", "edfFreePhase", "edfFreePhaseDynamic",
    "scottishPower",
]

OPT_BATTERIES = [
    {"kwh": 5.0,  "cost": 3500,  "label": "5 kWh"},
    {"kwh": 7.5,  "cost": 5000,  "label": "7.5 kWh"},
    {"kwh": 10.0, "cost": 6000,  "label": "10 kWh"},
    {"kwh": 13.5, "cost": 7500,  "label": "13.5 kWh"},
    {"kwh": 15.0, "cost": 8500,  "label": "15 kWh"},
    {"kwh": 20.0, "cost": 11000, "label": "20 kWh"},
]

DEFAULT_COSTS: dict[float, int] = {
    3: 2200, 4: 2900, 5: 3500, 6: 4000, 7: 4600, 7.5: 5000,
    8: 5300, 9: 5700, 10: 6000, 11: 6400, 12: 6800, 13: 7200,
    13.5: 7500, 14: 7800, 15: 8500, 16: 9000, 17: 9500,
    18: 10000, 19: 10500, 20: 11000, 21: 11500, 22: 12000,
    23: 12500, 24: 13000, 25: 13500,
}
