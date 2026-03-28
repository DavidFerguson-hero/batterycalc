"""
POST /api/analyse   — upload CSV(s), return full results
POST /api/recalculate — re-run with new slider params against cached days
"""
from __future__ import annotations
import math
import hashlib
from typing import Annotated, Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from engine.csv_parser import parse_csv_bytes, merge_parse_results, ParseResult
from engine.simulator import run_simulation, calc_day_flows
from engine.optimiser import build_opt_matrix
from engine.payback import calc_payback
from engine.tariffs import TARIFFS, OPT_TARIFF_KEYS, IMPLIED_RATE
from engine.profile_estimator import make_parse_result, SUGGESTED_KWH

# In-memory session cache (replace with Redis in production)
_session_cache: dict[str, dict] = {}

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
            "avg_consumption_profile": [
                round(sum(day[i] for day in parse.days) / len(parse.days), 4)
                for i in range(48)
            ],
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

    # Cache parsed days against a session id based on raw content hash
    combined_raw = b"".join([str(r.days).encode() for r in parse_results])
    session_id = _session_key(combined_raw)
    _session_cache[session_id] = {
        "days": merged.days,
        "inferred_rate": merged.inferred_rate,
        "days_count": merged.days_count,
        "total_kwh": merged.total_kwh,
        "daily_avg_kwh": merged.daily_avg_kwh,
        "annual_kwh_estimate": merged.annual_kwh_estimate,
    }

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

    parse = make_parse_result(req.annual_kwh, req.property_type, req.unit_rate_p)

    cache_key = f"est|{req.annual_kwh}|{req.property_type}|{req.unit_rate_p}"
    session_id = hashlib.sha256(cache_key.encode()).hexdigest()[:16]
    _session_cache[session_id] = {
        "days":                parse.days,
        "inferred_rate":       parse.inferred_rate,
        "days_count":          parse.days_count,
        "total_kwh":           parse.total_kwh,
        "daily_avg_kwh":       parse.daily_avg_kwh,
        "annual_kwh_estimate": parse.annual_kwh_estimate,
    }

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
    cached = _session_cache.get(req.session_id)
    if cached is None:
        raise HTTPException(
            status_code=404,
            detail="Session not found. Please re-upload your CSV files.",
        )

    from engine.csv_parser import ParseResult as PR
    parse = PR(
        days=cached["days"],
        inferred_rate=cached["inferred_rate"],
        days_count=cached["days_count"],
        total_kwh=cached["total_kwh"],
        daily_avg_kwh=cached["daily_avg_kwh"],
        annual_kwh_estimate=cached["annual_kwh_estimate"],
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

    parse = make_parse_result(req.annual_kwh, req.property_type, req.unit_rate_p)
    unit_rate = parse.inferred_rate if parse.inferred_rate else IMPLIED_RATE

    cache_key  = f"est|{req.annual_kwh}|{req.property_type}|{req.unit_rate_p}"
    session_id = hashlib.sha256(cache_key.encode()).hexdigest()[:16]
    _session_cache[session_id] = {
        "days":                parse.days,
        "inferred_rate":       parse.inferred_rate,
        "days_count":          parse.days_count,
        "total_kwh":           parse.total_kwh,
        "daily_avg_kwh":       parse.daily_avg_kwh,
        "annual_kwh_estimate": parse.annual_kwh_estimate,
    }

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
    avg_day_kwh     = parse.days[0]   # synthetic profile: all 35 days identical

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
