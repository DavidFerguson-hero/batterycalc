"""
POST /api/analyse   — upload CSV(s), return full results
POST /api/recalculate — re-run with new slider params against cached days
"""
from __future__ import annotations
import math
import hashlib
from typing import Annotated

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from engine.csv_parser import parse_csv_bytes, merge_parse_results, ParseResult
from engine.simulator import run_simulation
from engine.optimiser import build_opt_matrix
from engine.payback import calc_payback
from engine.tariffs import TARIFFS, OPT_TARIFF_KEYS, IMPLIED_RATE

# In-memory session cache (replace with Redis in production)
_session_cache: dict[str, dict] = {}

router = APIRouter(tags=["analyse"])


# ── Pydantic models ────────────────────────────────────────────────────────────

class RecalculateRequest(BaseModel):
    session_id: str
    tariff_key: str = "octopusGo"
    battery_cap_kwh: float = Field(10.0, ge=1, le=50)
    battery_cost_gbp: float = Field(6000, ge=500, le=50000)
    max_charge_rate_kw: float = Field(3.6, ge=0.5, le=15)
    efficiency_pct: float = Field(90.0, ge=50, le=100)
    inflation_pct: float = Field(5.0, ge=0, le=20)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_response(
    parse: ParseResult,
    tariff_key: str,
    battery_cap_kwh: float,
    battery_cost_gbp: float,
    max_charge_rate_kw: float,
    efficiency_pct: float,
    inflation_pct: float,
    session_id: str,
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
        },
        "charts": {
            "soc_profile": [round(v, 3) for v in sim.avg_soc_profile],
            "cumulative_savings": pb.cumulative,
            "heatmap": heatmap,
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
        session_id=session_id,
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
        session_id=req.session_id,
    )
