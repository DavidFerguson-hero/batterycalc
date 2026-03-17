"""
POST /api/solar  — fetch PVGIS data and compute solar-augmented savings
"""
from __future__ import annotations
import math
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from engine.solar_fetcher import resolve_postcode, fetch_solar_profiles, weighted_avg_profile
from engine.simulator import run_simulation, calc_solar_impact
from engine.tariffs import TARIFFS
from engine.payback import calc_payback
from routers.analyse import _session_cache, _build_response
from engine.csv_parser import ParseResult

router = APIRouter(tags=["solar"])


class SolarRequest(BaseModel):
    session_id:         str
    postcode:           str
    panel_kwp:          float = Field(4.0,  ge=0.5,  le=20.0)
    orientation:        str   = "south"   # south | south_east | south_west | east | west | north
    tilt_deg:           float = Field(35.0, ge=5.0,  le=75.0)
    seg_rate_p:         float = Field(15.0, ge=0.0,  le=50.0)   # pence/kWh export
    panel_cost_gbp:     float = Field(0.0,  ge=0.0,  le=50000)  # 0 = existing panels
    # Slider params (same as recalculate)
    tariff_key:         str   = "octopusGo"
    battery_cap_kwh:    float = Field(10.0, ge=1,    le=50)
    battery_cost_gbp:   float = Field(6000, ge=500,  le=50000)
    max_charge_rate_kw: float = Field(3.6,  ge=0.5,  le=15)
    efficiency_pct:     float = Field(90.0, ge=50,   le=100)
    inflation_pct:      float = Field(5.0,  ge=0,    le=20)
    current_sc_pd:      float = Field(53.0, ge=0,    le=200)
    export_rate_p:      float = Field(0.0,  ge=0,    le=50)


@router.post("/solar")
async def solar(req: SolarRequest):
    cached = _session_cache.get(req.session_id)
    if cached is None:
        raise HTTPException(
            status_code=404,
            detail="Session not found. Please upload or estimate your consumption first.",
        )

    # ── Resolve postcode → lat/lon ──────────────────────────────────────────
    try:
        lat, lon = await resolve_postcode(req.postcode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # ── Fetch PVGIS data ────────────────────────────────────────────────────
    try:
        solar_data = await fetch_solar_profiles(
            lat=lat,
            lon=lon,
            peak_power_kwp=req.panel_kwp,
            tilt_deg=req.tilt_deg,
            orientation=req.orientation,
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch solar data: {e}",
        )

    avg_solar = weighted_avg_profile(solar_data["monthly_profiles"])

    # Store in session so future recalculations can include solar
    _session_cache[req.session_id]["solar_avg_profile"] = avg_solar
    _session_cache[req.session_id]["solar_seg_rate"]    = req.seg_rate_p / 100.0
    _session_cache[req.session_id]["solar_annual_kwh"]  = solar_data["annual_kwh"]
    _session_cache[req.session_id]["solar_panel_kwp"]   = req.panel_kwp

    # ── Rebuild parse object from cache ────────────────────────────────────
    parse = ParseResult(
        days=cached["days"],
        inferred_rate=cached["inferred_rate"],
        days_count=cached["days_count"],
        total_kwh=cached["total_kwh"],
        daily_avg_kwh=cached["daily_avg_kwh"],
        annual_kwh_estimate=cached["annual_kwh_estimate"],
    )

    tariff = TARIFFS.get(req.tariff_key)
    if tariff is None:
        raise HTTPException(status_code=400, detail=f"Unknown tariff: {req.tariff_key}")

    # ── Run base simulation (no solar) for ann_cost_current ─────────────────
    efficiency   = req.efficiency_pct / 100.0
    export_rate  = req.export_rate_p  / 100.0
    seg_rate     = req.seg_rate_p     / 100.0

    sim = run_simulation(
        tariff=tariff,
        cap_kwh=req.battery_cap_kwh,
        max_rate_kw=req.max_charge_rate_kw,
        efficiency=efficiency,
        days=cached["days"],
        current_rate=cached["inferred_rate"],
        current_sc_pd=req.current_sc_pd,
        export_rate=export_rate,
    )
    if sim is None:
        raise HTTPException(status_code=422, detail="No usable session data.")

    # ── Compute solar impact ────────────────────────────────────────────────
    sc_new = tariff.standing_charge * 365
    solar_result = calc_solar_impact(
        tariff=tariff,
        cap_kwh=req.battery_cap_kwh,
        max_rate_kw=req.max_charge_rate_kw,
        efficiency=efficiency,
        days=cached["days"],
        avg_solar_profile=avg_solar,
        seg_rate=seg_rate,
        ann_cost_current=sim.ann_cost_current,
        sc_new=sc_new,
    )

    # ── Payback for battery (on top of solar) ───────────────────────────────
    incremental_battery_saving = (
        solar_result.saving_solar_battery - solar_result.saving_solar_only
    )
    pb_batt = calc_payback(req.battery_cost_gbp, incremental_battery_saving, req.inflation_pct)

    # ── Payback for panels (if new install) ─────────────────────────────────
    pb_panels = None
    pb_combined = None
    if req.panel_cost_gbp > 0:
        pb_panels   = calc_payback(req.panel_cost_gbp, solar_result.saving_solar_only, req.inflation_pct)
        pb_combined = calc_payback(
            req.panel_cost_gbp + req.battery_cost_gbp,
            solar_result.saving_solar_battery,
            req.inflation_pct,
        )

    # ── Build full base response then attach solar block ───────────────────
    base = _build_response(
        parse=parse,
        tariff_key=req.tariff_key,
        battery_cap_kwh=req.battery_cap_kwh,
        battery_cost_gbp=req.battery_cost_gbp,
        max_charge_rate_kw=req.max_charge_rate_kw,
        efficiency_pct=req.efficiency_pct,
        inflation_pct=req.inflation_pct,
        current_sc_pd=req.current_sc_pd,
        session_id=req.session_id,
        source=cached.get("source", "upload"),
    )

    base["solar"] = {
        "annual_generation_kwh":       solar_data["annual_kwh"],
        "annual_self_consumed_kwh":    solar_result.ann_self_consumed_kwh,
        "annual_exported_no_batt_kwh": solar_result.ann_exported_no_batt_kwh,
        "annual_exported_with_batt_kwh": solar_result.ann_exported_with_batt_kwh,
        "self_consumption_pct":        solar_result.self_consumption_pct,
        "seg_income_no_batt":          solar_result.ann_seg_income_no_batt,
        "seg_income_with_batt":        solar_result.ann_seg_income_with_batt,
        "ann_cost_solar_only":         solar_result.ann_cost_solar_only,
        "ann_cost_solar_battery":      solar_result.ann_cost_solar_battery,
        "saving_solar_only":           solar_result.saving_solar_only,
        "saving_solar_battery":        solar_result.saving_solar_battery,
        "incremental_battery_saving":  round(incremental_battery_saving, 2),
        "payback_battery_years":       round(pb_batt.years, 2) if pb_batt.years != math.inf else None,
        "payback_panels_years":        round(pb_panels.years, 2) if pb_panels and pb_panels.years != math.inf else None,
        "payback_combined_years":      round(pb_combined.years, 2) if pb_combined and pb_combined.years != math.inf else None,
        "location": {"lat": round(lat, 4), "lon": round(lon, 4)},
        "panel_kwp": req.panel_kwp,
        "orientation": req.orientation,
        "tilt_deg": req.tilt_deg,
    }

    return base
