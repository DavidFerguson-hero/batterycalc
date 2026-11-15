"""
POST /api/analyse   — upload CSV(s), return full results
POST /api/recalculate — re-run with new slider params against cached days
"""
from __future__ import annotations
import math
import hashlib
import time
from collections import OrderedDict
from dataclasses import replace
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from engine.csv_parser import parse_csv_bytes, merge_parse_results, ParseResult
from engine.simulator import run_simulation, calc_day_flows
from engine.optimiser import build_opt_matrix
from engine.payback import calc_payback
from engine.tariffs import TARIFFS, OPT_TARIFF_KEYS, IMPLIED_RATE
from engine.profile_estimator import make_parse_result, SUGGESTED_KWH
from engine.carbon import fetch_carbon_intensity_profile, calc_carbon_savings
from engine.extra_loads import (
    EV_DEFAULT_MILES, EV_DEFAULT_WINDOW, EV_KWH_PER_MILE, HP_DEFAULT_EFFICIENCY,
    EVSettings, HeatPumpSettings, apply_extra_loads,
)

# In-memory session cache so /recalculate can re-run without a re-upload.
# Bounded in size and age: a full year of half-hourly data is ~17,500 numbers per
# session, and uploaded usage should not sit in memory indefinitely. Never persisted.
_SESSION_MAX = 200
_SESSION_TTL_S = 60 * 60
_session_cache: "OrderedDict[str, tuple[float, ParseResult]]" = OrderedDict()


def _cache_put(session_id: str, parse: ParseResult) -> None:
    _session_cache[session_id] = (time.monotonic(), replace(parse, readings={}))
    _session_cache.move_to_end(session_id)
    while len(_session_cache) > _SESSION_MAX:
        _session_cache.popitem(last=False)


def _cache_get(session_id: str) -> ParseResult | None:
    item = _session_cache.get(session_id)
    if item is None:
        return None
    stored_at, parse = item
    if time.monotonic() - stored_at > _SESSION_TTL_S:
        del _session_cache[session_id]
        return None
    return parse


def _average_day(days: list[list[float]]) -> list[float]:
    n = len(days)
    return [sum(d[i] for d in days) / n for i in range(48)]


HeatingType = Literal["gas", "electric"]
LoadStatus = Literal["none", "have", "planning"]


class EVInput(BaseModel):
    """An electric car. "have": already in the usage figures. "planning": add it on top."""
    status:       LoadStatus = "none"
    annual_miles: float = Field(EV_DEFAULT_MILES, ge=0, le=60000)
    kwh_per_mile: float = Field(EV_KWH_PER_MILE, ge=0.1, le=1.0)
    charge_start: str   = Field(EV_DEFAULT_WINDOW[0], pattern=r"^([01]\d|2[0-3]):(00|30)$")
    charge_end:   str   = Field(EV_DEFAULT_WINDOW[1], pattern=r"^([01]\d|2[0-3]):(00|30)$")


class HeatPumpInput(BaseModel):
    """A heat pump. Heat demand comes from heat_demand_kwh if given, else floor area × EPC rating."""
    status:          LoadStatus = "none"
    heat_demand_kwh: Optional[float] = Field(None, ge=500, le=60000)
    floor_area_m2:   Optional[float] = Field(None, ge=15, le=1000)
    epc_rating:      Optional[str]   = Field(None, pattern=r"^[A-Ga-g]$")
    efficiency:      float = Field(HP_DEFAULT_EFFICIENCY, ge=1.5, le=6.0)


def _with_extra_loads(
    parse: ParseResult,
    ev: EVInput | None,
    hp: HeatPumpInput | None,
    route: str,
    property_type: str,
) -> ParseResult:
    """Apply the EV / heat pump to the days and record what changed in the summary."""
    ev = ev or EVInput()
    hp = hp or HeatPumpInput()
    if ev.status == "none" and hp.status == "none":
        return parse
    try:
        res = apply_extra_loads(
            parse.days, parse.dates,
            EVSettings(**ev.model_dump()), HeatPumpSettings(**hp.model_dump()),
            route=route, property_type=property_type,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    annual = sum(map(sum, res.days)) * 365.0 / len(res.days)
    return replace(
        parse,
        days=res.days,
        annual_kwh_estimate=round(annual, 1),
        daily_avg_kwh=round(annual / 365.0, 3),
        extra_loads={"ev": ev.model_dump(), "heat_pump": hp.model_dump(), **res.summary()},
    )

# ── Solar estimation constants ──────────────────────────────────────────────
SOLAR_KWP             = 4.0      # Standard residential system (kWp)
SOLAR_GEN_PER_KWP     = 850.0    # kWh/kWp/year — UK annual average
SOLAR_INSTALLED_COST  = 6000.0   # £ — typical 4 kWp fully installed (inc. 5% VAT)
SEG_EXPORT_RATE       = 0.075    # 7.5p/kWh — Smart Export Guarantee typical
FLUX_EXPORT_RATE      = 0.15     # 15p/kWh — Octopus Flux average export rate
SOLAR_SC_SOLO         = 0.35     # Self-consumption without battery (~35%)
SOLAR_SC_WITH_BATT    = 0.65     # Self-consumption with 10 kWh battery (~65%)

# Annual-average half-hourly solar generation profile for a south-facing system
# at 52.6°N (UK midlands), modelled as a Gaussian centred on 13:00 BST.
# Normalised: sum = 1.0.  Multiply by (annual_gen_kwh / 365) for absolute kWh/slot.
UK_SOLAR_PROFILE_NORM: list[float] = [
    # 00:00–06:00 (slots 0–12) — dark
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    # 06:30 (slot 13) — dawn
    0.0066,
    # 07:00–09:30 (slots 14–19)
    0.0093, 0.0129, 0.0172, 0.0225, 0.0285, 0.0350,
    # 10:00–12:30 (slots 20–25)
    0.0420, 0.0490, 0.0555, 0.0611, 0.0655, 0.0683,
    # 13:00–13:30 (slots 26–27) — peak
    0.0692, 0.0683,
    # 14:00–16:30 (slots 28–33)
    0.0655, 0.0611, 0.0555, 0.0490, 0.0420, 0.0350,
    # 17:00–18:30 (slots 34–37)
    0.0285, 0.0225, 0.0172, 0.0129,
    # 19:00–23:30 (slots 38–47) — dark
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
]

router = APIRouter(tags=["analyse"])


# ── Pydantic models ────────────────────────────────────────────────────────────

class EstimateRequest(BaseModel):
    annual_kwh:        float = Field(..., ge=500, le=20000)
    property_type:     str   = "semi"     # flat | terraced | semi | detached
    unit_rate_p:       float = Field(28.16, ge=5, le=100)   # pence/kWh
    tariff_key:        str   = "octopusGo"
    battery_cap_kwh:   float = Field(10.0,  ge=1,   le=50)
    battery_cost_gbp:  float = Field(6000,  ge=500, le=50000)
    max_charge_rate_kw:float = Field(3.6,   ge=0.5, le=15)
    efficiency_pct:    float = Field(90.0,  ge=50,  le=100)
    inflation_pct:     float = Field(5.0,   ge=0,   le=20)
    current_sc_pd:     float = Field(53.0,  ge=0,   le=200)
    export_rate_p:     float = Field(0.0,   ge=0,   le=100)
    heating_type:      HeatingType = "gas"   # from the EPC: "electric" when there's no mains gas
    ev:                Optional[EVInput] = None
    heat_pump:         Optional[HeatPumpInput] = None


class CompareRequest(BaseModel):
    annual_kwh:               float = Field(..., ge=500, le=20000)
    property_type:            str   = "semi"
    unit_rate_p:              float = Field(28.16, ge=5, le=100)
    inflation_pct:            float = Field(5.0,   ge=0, le=20)
    current_sc_pd:            float = Field(53.0,  ge=0, le=200)
    efficiency_pct:           float = Field(90.0,  ge=50, le=100)
    max_charge_rate_kw:       float = Field(3.6,   ge=0.5, le=15)
    # Optional sidebar overrides
    battery_cap_kwh_override: Optional[float] = Field(None, ge=1, le=50)
    battery_cost_gbp_override:Optional[float] = Field(None, ge=500, le=50000)
    tariff_key_override:      Optional[str]   = None
    solar_kwp:                float        = Field(4.0,  ge=0.5, le=30)
    solar_installed_cost:     float        = Field(8000.0, ge=500, le=50000)
    # Existing system context — changes scenario labels, best_key logic, AI framing
    context_has_solar:        bool         = False
    context_has_battery:      bool         = False
    heating_type:             HeatingType  = "gas"
    ev:                       Optional[EVInput] = None
    heat_pump:                Optional[HeatPumpInput] = None


class RecalculateRequest(BaseModel):
    session_id: str
    tariff_key: str = "octopusGo"
    battery_cap_kwh: float = Field(10.0, ge=1, le=50)
    battery_cost_gbp: float = Field(6000, ge=500, le=50000)
    max_charge_rate_kw: float = Field(3.6, ge=0.5, le=15)
    efficiency_pct: float = Field(90.0, ge=50, le=100)
    inflation_pct: float = Field(5.0, ge=0, le=20)
    current_sc_pd: float = Field(53.0, ge=0, le=200)   # pence/day
    export_rate_p: float = Field(0.0, ge=0, le=100)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_response(
    parse: ParseResult,
    tariff_key: str,
    battery_cap_kwh: float,
    battery_cost_gbp: float,
    max_charge_rate_kw: float,
    efficiency_pct: float,
    inflation_pct: float,
    current_sc_pd: float,
    session_id: str,
    source: str = "upload",   # "upload" | "estimate"
    export_rate_p: float = 0.0,
) -> dict:
    tariff = TARIFFS.get(tariff_key)
    if tariff is None:
        raise HTTPException(status_code=400, detail=f"Unknown tariff key: {tariff_key}")

    efficiency = efficiency_pct / 100.0
    current_rate = parse.inferred_rate

    # Detailed simulation for selected tariff + exact slider values
    sim = run_simulation(
        tariff=tariff,
        cap_kwh=battery_cap_kwh,
        max_rate_kw=max_charge_rate_kw,
        efficiency=efficiency,
        days=parse.days,
        current_rate=current_rate,
        current_sc_pd=current_sc_pd,
        export_rate=export_rate_p / 100.0,
    )
    if sim is None:
        raise HTTPException(status_code=422, detail="No usable data in uploaded files.")

    pb = calc_payback(battery_cost_gbp, sim.total_saving, inflation_pct)

    # Optimisation matrix (all tariffs × all standard battery sizes)
    matrix = build_opt_matrix(
        days=parse.days,
        current_rate=current_rate,
        max_rate_kw=max_charge_rate_kw,
        efficiency=efficiency,
        selected_cap_kwh=battery_cap_kwh,
        selected_cost_gbp=battery_cost_gbp,
        inflation_pct=inflation_pct,
        current_sc_pd=current_sc_pd,
    )

    # Best tariff (by total saving, for selected battery size)
    best_tariff = _best_tariff(matrix, battery_cap_kwh)
    best_battery_kwh = _best_battery(matrix, tariff_key)

    # Heatmap: payback years per tariff × battery size
    heatmap = _build_heatmap(matrix)

    # Tariff rankings (for selected battery)
    tariff_ranking = _tariff_ranking(matrix, battery_cap_kwh)

    # Battery rankings (for selected tariff)
    battery_ranking = _battery_ranking(matrix, tariff_key)

    # All combinations ranked by 10yr ROI
    all_combinations = _all_combinations(matrix)

    return {
        "session_id": session_id,
        "source": source,
        "summary": {
            "days_analysed": parse.days_count,
            "total_kwh": parse.total_kwh,
            "daily_avg_kwh": parse.daily_avg_kwh,
            "annual_kwh_estimate": parse.annual_kwh_estimate,
            "inferred_rate_pence": round(current_rate * 100, 2) if current_rate else None,
            "days_modelled": len(parse.days),
            "coverage": parse.coverage,
            "confidence": parse.confidence,
            "extra_loads": parse.extra_loads,
        },
        "selected": {
            "tariff_key": tariff_key,
            "tariff_name": tariff.name,
            "battery_cap_kwh": battery_cap_kwh,
            "battery_cost_gbp": battery_cost_gbp,
            "max_charge_rate_kw": max_charge_rate_kw,
            "efficiency_pct": efficiency_pct,
            "inflation_pct": inflation_pct,
            "current_sc_pd": current_sc_pd,
        },
        "financials": {
            "ann_cost_current": round(sim.ann_cost_current, 2),
            "ann_cost_no_battery": round(sim.ann_cost_no_battery, 2),
            "ann_cost_with_battery": round(sim.ann_cost_with_battery, 2),
            "saving_battery_only": round(sim.saving_battery_only, 2),
            "saving_tariff_switch": round(sim.saving_tariff_switch, 2),
            "total_saving": round(sim.total_saving, 2),
            "payback_years": round(pb.years, 2) if pb.years != math.inf else None,
            "roi_10yr": pb.roi_10yr,
            "ann_export_revenue": round(sim.ann_export_revenue, 2),
            "ann_kwh_exported": round(sim.ann_kwh_exported, 1),
        },
        "charts": {
            "soc_profile": [round(v, 3) for v in sim.avg_soc_profile],
            "cumulative_savings": pb.cumulative,
            "heatmap": heatmap,
            "avg_consumption_profile": [round(v, 4) for v in _average_day(parse.days)],
        },
        "recommendations": {
            "best_tariff_key": best_tariff,
            "best_battery_kwh": best_battery_kwh,
            "tariff_ranking": tariff_ranking,
            "battery_ranking": battery_ranking,
        },
        "all_combinations": all_combinations,
    }


def _best_tariff(matrix: dict, cap_kwh: float) -> str | None:
    best_key, best_saving = None, -math.inf
    for tk, rows in matrix.items():
        row = _nearest_row(rows, cap_kwh)
        if row and row["total_saving"] > best_saving:
            best_saving = row["total_saving"]
            best_key = tk
    return best_key


def _best_battery(matrix: dict, tariff_key: str) -> float | None:
    rows = matrix.get(tariff_key, [])
    if not rows:
        return None
    return max(rows, key=lambda r: r["roi_10yr"])["battery_kwh"]


def _nearest_row(rows: list[dict], cap_kwh: float) -> dict | None:
    if not rows:
        return None
    return min(rows, key=lambda r: abs(r["battery_kwh"] - cap_kwh))


def _build_heatmap(matrix: dict) -> list[dict]:
    return [
        {
            "tariff_key": tk,
            "tariff_name": matrix[tk][0]["tariff_name"] if matrix[tk] else tk,
            "cells": [
                {
                    "battery_kwh": r["battery_kwh"],
                    "battery_label": r["battery_label"],
                    "battery_cost": r["battery_cost"],
                    "payback_years": r["payback_years"],
                    "total_saving": r["total_saving"],
                    "roi_10yr": r["roi_10yr"],
                }
                for r in rows
            ],
        }
        for tk, rows in matrix.items()
    ]


def _tariff_ranking(matrix: dict, cap_kwh: float) -> list[dict]:
    ranked = []
    for tk, rows in matrix.items():
        row = _nearest_row(rows, cap_kwh)
        if row:
            ranked.append(row)
    return sorted(ranked, key=lambda r: r["total_saving"], reverse=True)


def _battery_ranking(matrix: dict, tariff_key: str) -> list[dict]:
    rows = matrix.get(tariff_key, [])
    return sorted(rows, key=lambda r: r["roi_10yr"], reverse=True)


def _all_combinations(matrix: dict) -> list[dict]:
    all_rows = [r for rows in matrix.values() for r in rows]
    return sorted(all_rows, key=lambda r: r["roi_10yr"], reverse=True)


def _session_key(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


# ── Solar scenario helpers ──────────────────────────────────────────────────

def _solar_only_scenario(
    unit_rate: float,
    inflation_pct: float,
    avg_day_kwh: list[float],
    solar_profile: list[float],
    solar_kwp: float = SOLAR_KWP,
    installed_cost: float = SOLAR_INSTALLED_COST,
) -> dict:
    """Solar-only scenario, SEG export, no battery."""
    gen           = solar_kwp * SOLAR_GEN_PER_KWP
    self_consumed = gen * SOLAR_SC_SOLO
    exported      = gen * (1 - SOLAR_SC_SOLO)
    import_saving = self_consumed * unit_rate
    export_rev    = exported * SEG_EXPORT_RATE
    total_saving  = import_saving + export_rev
    pb = calc_payback(installed_cost, total_saving, inflation_pct)

    # Per-slot flows for the energy flow chart (no battery — use dummy flat-rate tariff)
    from engine.tariffs import Tariff as _Tariff
    _flat = _Tariff(
        key="flat", name="flat",
        supplier="", description="", color="",
        slot_rates=[unit_rate] * 48,
        charge_slots=[False] * 48,
        discharge_slots=[False] * 48,
        standing_charge=0.0,
    )
    daily_flows = calc_day_flows(avg_day_kwh, _flat, 0.0, 3.6, 0.9, solar_profile)

    return {
        "label":          "Solar Only",
        "icon":           "☀️",
        "tech":           f"{solar_kwp:.1f} kWp solar · SEG at {int(SEG_EXPORT_RATE*100)}p/kWh",
        "annual_saving":  round(total_saving, 0),
        "installed_cost": installed_cost,
        "payback_years":  round(pb.years, 1) if pb.years != math.inf else None,
        "roi_10yr":       round(pb.roi_10yr, 0),
        "cumulative":     pb.cumulative,
        "daily_flows":    daily_flows,
        "breakdown": {
            "import_saving":     round(import_saving, 0),
            "export_revenue":    round(export_rev, 0),
            "kwh_self_consumed": round(self_consumed, 0),
            "kwh_exported":      round(exported, 0),
            "export_rate_p":     SEG_EXPORT_RATE * 100,
        },
    }


def _solar_battery_scenario(
    matrix: dict,
    unit_rate: float,
    inflation_pct: float,
    avg_day_kwh: list[float],
    solar_profile: list[float],
    efficiency: float,
    max_rate_kw: float,
    solar_kwp: float = SOLAR_KWP,
    solar_installed_cost: float = SOLAR_INSTALLED_COST,
) -> dict:
    """
    Solar + best battery on Octopus Flux.

    Solar contribution (higher self-consumption, Flux export rate) is added on top
    of the Flux+battery baseline from the simulation matrix.  This avoids
    double-counting because the simulator runs battery-only (no solar).
    """
    import math as _math
    gen = solar_kwp * SOLAR_GEN_PER_KWP

    # Best Flux + battery combo from matrix
    flux_rows = matrix.get("octopusFlux", [])
    if flux_rows:
        best_flux = max(flux_rows, key=lambda r: r["roi_10yr"])
    else:
        all_rows = [r for rows in matrix.values() for r in rows]
        best_flux = max(all_rows, key=lambda r: r["roi_10yr"]) if all_rows else None

    if not best_flux:
        return {}

    batt_kwh  = best_flux["battery_kwh"]
    batt_cost = best_flux["battery_cost"]
    flux_saving = best_flux["total_saving"]   # tariff switch + battery arbitrage (no solar)

    # Additional solar saving on top of Flux+battery baseline
    sb_self     = gen * SOLAR_SC_WITH_BATT
    sb_exported = gen * (1 - SOLAR_SC_WITH_BATT)
    solar_import_saving = sb_self * unit_rate          # avoid importing at user's current rate
    solar_export_rev    = sb_exported * FLUX_EXPORT_RATE
    solar_extra         = solar_import_saving + solar_export_rev

    total_saving = flux_saving + solar_extra
    total_cost   = solar_installed_cost + batt_cost
    pb = calc_payback(total_cost, total_saving, inflation_pct)

    flux_tariff  = TARIFFS["octopusFlux"]
    daily_flows  = calc_day_flows(
        avg_day_kwh, flux_tariff, batt_kwh, max_rate_kw, efficiency, solar_profile
    )

    return {
        "label":          "Solar + Battery",
        "icon":           "⚡",
        "tech":           f"{solar_kwp:.1f} kWp solar + {batt_kwh} kWh battery · Octopus Flux",
        "annual_saving":  round(total_saving, 0),
        "installed_cost": round(total_cost, 0),
        "payback_years":  round(pb.years, 1) if pb.years != math.inf else None,
        "roi_10yr":       round(pb.roi_10yr, 0),
        "cumulative":     pb.cumulative,
        "daily_flows":    daily_flows,
        "breakdown": {
            "flux_battery_saving":  round(flux_saving, 0),
            "solar_import_saving":  round(solar_import_saving, 0),
            "solar_export_revenue": round(solar_export_rev, 0),
            "kwh_self_consumed":    round(sb_self, 0),
            "kwh_exported":         round(sb_exported, 0),
            "export_rate_p":        FLUX_EXPORT_RATE * 100,
            "battery_kwh":          batt_kwh,
            "best_tariff":          "Octopus Flux",
        },
    }


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/analyse")
async def analyse(
    files: Annotated[list[UploadFile], File()],
    tariff_key: Annotated[str, Form()] = "octopusGo",
    battery_cap_kwh: Annotated[float, Form()] = 10.0,
    battery_cost_gbp: Annotated[float, Form()] = 6000.0,
    max_charge_rate_kw: Annotated[float, Form()] = 3.6,
    efficiency_pct: Annotated[float, Form()] = 90.0,
    inflation_pct: Annotated[float, Form()] = 5.0,
    current_sc_pd: Annotated[float, Form()] = 53.0,
    export_rate_p: Annotated[float, Form()] = 0.0,
    property_type: Annotated[str, Form()] = "semi",
    ev: Annotated[Optional[str], Form(description="EVInput as JSON")] = None,
    heat_pump: Annotated[Optional[str], Form(description="HeatPumpInput as JSON")] = None,
):
    if not files:
        raise HTTPException(status_code=400, detail="At least one CSV file is required.")

    parse_results = []
    for f in files:
        raw = await f.read()
        try:
            parse_results.append(parse_csv_bytes(raw))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    merged = merge_parse_results(parse_results)
    try:
        ev_in = EVInput.model_validate_json(ev) if ev else None
        hp_in = HeatPumpInput.model_validate_json(heat_pump) if heat_pump else None
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid ev / heat_pump settings: {e}")
    merged = _with_extra_loads(merged, ev_in, hp_in, "upload", property_type)

    # Cache parsed days against a session id based on raw content hash
    combined_raw = b"".join([str(r.days).encode() for r in parse_results])
    combined_raw += f"|{property_type}|{ev or ''}|{heat_pump or ''}".encode()
    session_id = _session_key(combined_raw)
    _cache_put(session_id, merged)

    return _build_response(
        parse=merged,
        tariff_key=tariff_key,
        battery_cap_kwh=battery_cap_kwh,
        battery_cost_gbp=battery_cost_gbp,
        max_charge_rate_kw=max_charge_rate_kw,
        efficiency_pct=efficiency_pct,
        inflation_pct=inflation_pct,
        current_sc_pd=current_sc_pd,
        session_id=session_id,
        export_rate_p=export_rate_p,
    )


@router.post("/estimate")
async def estimate(req: EstimateRequest):
    valid_types = {"flat", "terraced", "semi", "detached"}
    if req.property_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"property_type must be one of {valid_types}")

    parse = make_parse_result(req.annual_kwh, req.property_type, req.unit_rate_p, req.heating_type)
    parse = _with_extra_loads(parse, req.ev, req.heat_pump, "estimate", req.property_type)

    cache_key = f"est|{req.model_dump_json(include={'annual_kwh', 'property_type', 'unit_rate_p', 'heating_type', 'ev', 'heat_pump'})}"
    session_id = hashlib.sha256(cache_key.encode()).hexdigest()[:16]
    _cache_put(session_id, parse)

    return _build_response(
        parse=parse,
        tariff_key=req.tariff_key,
        battery_cap_kwh=req.battery_cap_kwh,
        battery_cost_gbp=req.battery_cost_gbp,
        max_charge_rate_kw=req.max_charge_rate_kw,
        efficiency_pct=req.efficiency_pct,
        inflation_pct=req.inflation_pct,
        current_sc_pd=req.current_sc_pd,
        session_id=session_id,
        source="estimate",
        export_rate_p=req.export_rate_p,
    )


@router.post("/recalculate")
async def recalculate(req: RecalculateRequest):
    parse = _cache_get(req.session_id)
    if parse is None:
        raise HTTPException(
            status_code=404,
            detail="Session not found. Please re-upload your CSV files.",
        )

    return _build_response(
        parse=parse,
        tariff_key=req.tariff_key,
        battery_cap_kwh=req.battery_cap_kwh,
        battery_cost_gbp=req.battery_cost_gbp,
        max_charge_rate_kw=req.max_charge_rate_kw,
        efficiency_pct=req.efficiency_pct,
        inflation_pct=req.inflation_pct,
        current_sc_pd=req.current_sc_pd,
        session_id=req.session_id,
        export_rate_p=req.export_rate_p,
    )


@router.post("/compare")
async def compare_scenarios(req: CompareRequest):
    """
    Returns three scenario estimates side-by-side for the 'starting fresh' journey:
      battery_only   — best TOU tariff + best battery from optimisation matrix
      solar_only     — 4 kWp solar with SEG export (no battery)
      solar_battery  — 4 kWp solar + best battery on Octopus Flux

    Solar figures use UK-average generation estimates (not half-hourly simulation).
    Also returns full_result (standard estimate payload) for the drill-down sections.
    """
    valid_types = {"flat", "terraced", "semi", "detached"}
    if req.property_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"property_type must be one of {valid_types}")

    parse = make_parse_result(req.annual_kwh, req.property_type, req.unit_rate_p, req.heating_type)
    parse = _with_extra_loads(parse, req.ev, req.heat_pump, "estimate", req.property_type)
    unit_rate = parse.inferred_rate if parse.inferred_rate else IMPLIED_RATE

    cache_key  = f"est|{req.model_dump_json(include={'annual_kwh', 'property_type', 'unit_rate_p', 'heating_type', 'ev', 'heat_pump'})}"
    session_id = hashlib.sha256(cache_key.encode()).hexdigest()[:16]
    _cache_put(session_id, parse)

    efficiency = req.efficiency_pct / 100.0

    matrix = build_opt_matrix(
        days=parse.days,
        current_rate=parse.inferred_rate,
        max_rate_kw=req.max_charge_rate_kw,
        efficiency=efficiency,
        selected_cap_kwh=10.0,
        selected_cost_gbp=6000.0,
        inflation_pct=req.inflation_pct,
        current_sc_pd=req.current_sc_pd,
    )

    # ── Battery-only: best combo from matrix ────────────────────────────────
    all_combos = _all_combinations(matrix)

    # Apply sidebar overrides
    if req.battery_cap_kwh_override or req.tariff_key_override:
        candidates = all_combos or []
        if req.battery_cap_kwh_override:
            # Filter to within 2.5 kWh of requested size; take the best tariff for that size
            near = [c for c in candidates if abs(c['battery_kwh'] - req.battery_cap_kwh_override) <= 2.5]
            if near:
                if req.tariff_key_override:
                    tariff_near = [c for c in near if c['tariff_key'] == req.tariff_key_override]
                    candidates = tariff_near or near
                else:
                    candidates = near
        elif req.tariff_key_override:
            tariff_cands = [c for c in candidates if c['tariff_key'] == req.tariff_key_override]
            if tariff_cands:
                candidates = tariff_cands
        override_best = candidates[0] if candidates else (all_combos[0] if all_combos else None)
    else:
        override_best = all_combos[0] if all_combos else None

    best_batt = override_best if (override_best and override_best['total_saving'] > 0) else None

    # Recalculate payback with override cost if supplied
    if best_batt and req.battery_cost_gbp_override:
        pb_override = calc_payback(req.battery_cost_gbp_override, best_batt['total_saving'], req.inflation_pct)
        best_batt = {**best_batt,
                     'battery_cost': req.battery_cost_gbp_override,
                     'payback_years': round(pb_override.years, 1) if pb_override.years != math.inf else None,
                     'roi_10yr': round(pb_override.roi_10yr, 0),
                     'cumulative_savings': pb_override.cumulative}

    if best_batt:
        battery_scenario = {
            "label":          "Battery Only",
            "icon":           "🔋",
            "tech":           f"{best_batt['battery_label']} · {best_batt['tariff_name']}",
            "annual_saving":  round(best_batt["total_saving"], 0),
            "installed_cost": best_batt["battery_cost"],
            "payback_years":  best_batt["payback_years"],
            "roi_10yr":       round(best_batt["roi_10yr"], 0),
            "cumulative":     best_batt.get("cumulative_savings", []),
            "breakdown": {
                "tariff_switch_saving": round(best_batt["saving_tariff_switch"], 0),
                "battery_arbitrage":    round(best_batt["saving_battery_only"], 0),
                "export_revenue":       0,
                "battery_kwh":          best_batt["battery_kwh"],
                "best_tariff":          best_batt["tariff_name"],
                "best_tariff_key":      best_batt["tariff_key"],
            },
        }
    else:
        battery_scenario = {
            "label": "Battery Only", "icon": "🔋",
            "tech": "No saving found for current profile",
            "annual_saving": 0, "installed_cost": 6000,
            "payback_years": None, "roi_10yr": -6000,
            "cumulative": [], "breakdown": {},
        }

    # ── Build solar profile and representative average day ───────────────────
    solar_daily_kwh = req.solar_kwp * SOLAR_GEN_PER_KWP / 365.0
    solar_profile   = [v * solar_daily_kwh for v in UK_SOLAR_PROFILE_NORM]
    avg_day_kwh     = _average_day(parse.days)   # year-average day (days now vary by season)

    # Battery-only flows — use best tariff, no solar
    if best_batt:
        batt_tariff = TARIFFS.get(best_batt["tariff_key"], TARIFFS["octopusGo"])
        battery_scenario["daily_flows"] = calc_day_flows(
            avg_day_kwh, batt_tariff,
            best_batt["battery_kwh"], req.max_charge_rate_kw, efficiency, None,
        )

    # ── Solar-only and Solar+battery scenarios ───────────────────────────────
    solar_scenario = _solar_only_scenario(
        unit_rate, req.inflation_pct, avg_day_kwh, solar_profile,
        solar_kwp=req.solar_kwp, installed_cost=req.solar_installed_cost,
    )
    sb_scenario = _solar_battery_scenario(
        matrix, unit_rate, req.inflation_pct, avg_day_kwh, solar_profile,
        efficiency, req.max_charge_rate_kw,
        solar_kwp=req.solar_kwp, solar_installed_cost=req.solar_installed_cost,
    )

    # ── Carbon intensity ─────────────────────────────────────────────────────
    carbon_profile = fetch_carbon_intensity_profile()
    for scen in [battery_scenario, solar_scenario, sb_scenario]:
        flows = scen.get("daily_flows")
        if flows:
            scen["carbon"] = calc_carbon_savings(avg_day_kwh, flows, carbon_profile)

    # ── Context-aware scenario filtering, relabelling & incremental financials ──
    hs = req.context_has_solar
    hb = req.context_has_battery

    if hs and not hb:
        # User has solar already.
        # Show: "Your solar today" (baseline) + "Add a battery" (incremental).
        # Drop battery-only — irrelevant when solar is already installed.
        solar_scenario["label"] = "Your solar today"
        solar_scenario["icon"]  = "☀️"
        solar_scenario["tech"]  = (
            f"{req.solar_kwp:.1f} kWp solar · SEG export · no battery"
        )

        # Incremental cost = battery portion only (total - solar already paid for)
        batt_cost_only = max(
            round(sb_scenario.get("installed_cost", 0) - req.solar_installed_cost, 0),
            best_batt["battery_cost"] if best_batt else 3500,
        )
        incr_saving = (sb_scenario.get("annual_saving") or 0) - (solar_scenario.get("annual_saving") or 0)
        if incr_saving > 0:
            pb_incr = calc_payback(batt_cost_only, incr_saving, req.inflation_pct)
            add_batt_payback = round(pb_incr.years, 1) if pb_incr.years != math.inf else None
            add_batt_roi     = round(pb_incr.roi_10yr, 0)
            add_batt_cum     = pb_incr.cumulative
        else:
            add_batt_payback = None
            add_batt_roi     = round(-batt_cost_only, 0)
            add_batt_cum     = []

        add_battery = {
            **sb_scenario,
            "label":         "Add a battery",
            "icon":          "☀️🔋",
            "tech":          (
                f"Add {sb_scenario['breakdown'].get('battery_kwh', '?')} kWh battery "
                f"· {sb_scenario['breakdown'].get('best_tariff', 'best TOU tariff')}"
            ),
            "installed_cost": batt_cost_only,
            "annual_saving":  round(incr_saving, 0),
            "payback_years":  add_batt_payback,
            "roi_10yr":       add_batt_roi,
            "cumulative":     add_batt_cum,
            "breakdown": {
                **sb_scenario.get("breakdown", {}),
                "incremental_note": f"Additional saving over your existing {req.solar_kwp:.1f} kWp solar",
            },
        }

        scenarios = {
            "solar":         solar_scenario,
            "solar_battery": add_battery,
        }
        best_key = "solar_battery"

    elif hb and not hs:
        # User has a battery already.
        # Show: "Your battery today" (baseline) + "Add solar panels" (incremental).
        # Drop solar-only — irrelevant when a battery is already installed.
        batt_label = battery_scenario["breakdown"].get("battery_kwh", "?")
        battery_scenario["label"] = "Your battery today"
        battery_scenario["icon"]  = "🔋"
        battery_scenario["tech"]  = (
            f"{batt_label} kWh battery · "
            f"{battery_scenario['breakdown'].get('best_tariff', 'best TOU tariff')}"
        )

        # Incremental cost = solar panels only
        solar_cost_only = req.solar_installed_cost
        incr_saving = (sb_scenario.get("annual_saving") or 0) - (battery_scenario.get("annual_saving") or 0)
        if incr_saving > 0:
            pb_incr = calc_payback(solar_cost_only, incr_saving, req.inflation_pct)
            add_sol_payback = round(pb_incr.years, 1) if pb_incr.years != math.inf else None
            add_sol_roi     = round(pb_incr.roi_10yr, 0)
            add_sol_cum     = pb_incr.cumulative
        else:
            add_sol_payback = None
            add_sol_roi     = round(-solar_cost_only, 0)
            add_sol_cum     = []

        add_solar = {
            **sb_scenario,
            "label":         "Add solar panels",
            "icon":          "☀️🔋",
            "tech":          (
                f"Add {req.solar_kwp:.1f} kWp solar · "
                f"works alongside your existing battery"
            ),
            "installed_cost": round(solar_cost_only, 0),
            "annual_saving":  round(incr_saving, 0),
            "payback_years":  add_sol_payback,
            "roi_10yr":       add_sol_roi,
            "cumulative":     add_sol_cum,
            "breakdown": {
                **sb_scenario.get("breakdown", {}),
                "incremental_note": (
                    f"Additional saving over your existing {batt_label} kWh battery"
                ),
            },
        }

        scenarios = {
            "battery":       battery_scenario,
            "solar_battery": add_solar,
        }
        best_key = "solar_battery"

    elif hs and hb:
        # User has both.
        # Show one card: their current setup (solar + battery) at full financials.
        sb_scenario["label"] = "Your current setup"
        sb_scenario["icon"]  = "🏠"
        sb_scenario["tech"]  = (
            f"{req.solar_kwp:.1f} kWp solar + "
            f"{sb_scenario['breakdown'].get('battery_kwh', '?')} kWh battery"
            f" · {sb_scenario['breakdown'].get('best_tariff', 'best tariff')}"
        )
        scenarios = {
            "solar_battery": sb_scenario,
        }
        best_key = "solar_battery"

    else:
        # Starting fresh — show all three, pick best by ROI.
        scenarios = {
            "battery":       battery_scenario,
            "solar":         solar_scenario,
            "solar_battery": sb_scenario,
        }
        best_key = max(
            scenarios,
            key=lambda k: scenarios[k].get("roi_10yr", -math.inf)
            if scenarios[k].get("roi_10yr") is not None else -math.inf,
        )

    # ── Full estimate result for drill-down sections ─────────────────────────
    best_tariff_key = (
        best_batt["tariff_key"] if best_batt else "octopusGo"
    )
    best_batt_kwh = best_batt["battery_kwh"] if best_batt else 10.0
    best_batt_cost = best_batt["battery_cost"] if best_batt else 6000.0

    full_result = _build_response(
        parse=parse,
        tariff_key=best_tariff_key,
        battery_cap_kwh=best_batt_kwh,
        battery_cost_gbp=best_batt_cost,
        max_charge_rate_kw=req.max_charge_rate_kw,
        efficiency_pct=req.efficiency_pct,
        inflation_pct=req.inflation_pct,
        current_sc_pd=req.current_sc_pd,
        session_id=session_id,
        source="estimate",
        export_rate_p=0.0,
    )

    return {
        "session_id":    session_id,
        "best_scenario": best_key,
        "scenarios":     scenarios,
        "full_result":   full_result,
    }
