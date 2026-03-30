"""
Carbon intensity integration using the National Grid ESO Carbon Intensity API.
https://api.carbonintensity.org.uk/
"""
from __future__ import annotations

import json
import logging
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

# UK average carbon intensity (gCO2/kWh) — 48 half-hourly slots, midnight to 23:30.
# Derived from National Grid ESO data; higher at morning/evening peaks,
# lower overnight (wind/nuclear baseload) and midday (solar contribution).
UK_CARBON_INTENSITY_FALLBACK: list[float] = [
    # 00:00–03:30  overnight, low demand, renewables dominant
    180, 175, 170, 165, 160, 158, 157, 156,
    # 04:00–07:30  pre-dawn ramp-up
    158, 162, 170, 182, 195, 210, 225, 235,
    # 08:00–11:30  morning peak
    240, 245, 242, 238, 232, 225, 218, 210,
    # 12:00–15:30  midday solar contribution lowers intensity
    205, 200, 195, 192, 190, 192, 195, 200,
    # 16:00–19:30  evening peak — highest demand, most carbon-intensive
    205, 215, 228, 242, 250, 252, 248, 240,
    # 20:00–23:30  evening wind-down
    228, 215, 205, 195, 190, 186, 183, 181,
]


def fetch_carbon_intensity_profile() -> list[float]:
    """
    Fetch today's 48-slot half-hourly carbon intensity profile (gCO2/kWh) from
    the National Grid ESO Carbon Intensity API.
    Falls back to UK_CARBON_INTENSITY_FALLBACK on any network/parse error.
    """
    try:
        url = "https://api.carbonintensity.org.uk/intensity/date"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            payload = json.loads(resp.read())
        slots = payload.get("data", [])
        intensities: list[float] = []
        for slot in slots:
            val = (slot.get("intensity") or {})
            # prefer actual reading, fall back to forecast
            v = val.get("actual") or val.get("forecast")
            if v is not None:
                intensities.append(float(v))
        if len(intensities) == 48:
            return intensities
        if intensities:
            # pad / trim to exactly 48
            while len(intensities) < 48:
                intensities.append(intensities[-1])
            return intensities[:48]
    except Exception as exc:
        logger.warning("Carbon Intensity API unavailable (%s) — using fallback profile", exc)
    return list(UK_CARBON_INTENSITY_FALLBACK)


def calc_carbon_savings(
    avg_day_kwh: list[float],
    daily_flows: dict,
    intensity_profile: list[float],
) -> dict:
    """
    Calculate annual CO₂ savings vs baseline (no system installed) for one scenario.

    Parameters
    ----------
    avg_day_kwh :        48-slot average daily consumption profile (kWh per slot)
    daily_flows :        dict returned by calc_day_flows() for this scenario
    intensity_profile :  48-slot carbon intensity in gCO2/kWh

    Returns
    -------
    dict with keys:
      baseline_kg_annual   — kg CO₂/yr without any system
      scenario_kg_annual   — kg CO₂/yr with this system (grid draw only)
      kg_saved_annual      — kg CO₂ saved per year
      pct_reduction        — percentage CO₂ reduction
      trees_equivalent     — trees needed to absorb the same CO₂ annually
      car_miles_equivalent — equivalent petrol-car miles not driven per year
    """
    intensity = intensity_profile if len(intensity_profile) == 48 else UK_CARBON_INTENSITY_FALLBACK

    # Baseline: entire load drawn from grid, slot by slot
    baseline_g_day = sum(avg_day_kwh[i] * intensity[i] for i in range(48))

    # With system: only direct grid-to-load + grid-to-battery draw
    grid_to_load = daily_flows.get("grid_to_load", [0.0] * 48)
    grid_to_batt = daily_flows.get("grid_to_batt", [0.0] * 48)

    scenario_g_day = sum(
        (grid_to_load[i] + grid_to_batt[i]) * intensity[i]
        for i in range(48)
    )

    baseline_g_yr  = baseline_g_day  * 365
    scenario_g_yr  = scenario_g_day  * 365

    kg_saved   = (baseline_g_yr - scenario_g_yr) / 1000.0
    baseline_kg = baseline_g_yr / 1000.0
    pct         = (kg_saved / baseline_kg * 100.0) if baseline_kg > 0 else 0.0

    return {
        "baseline_kg_annual":    round(baseline_kg,           1),
        "scenario_kg_annual":    round(scenario_g_yr / 1000.0, 1),
        "kg_saved_annual":       round(kg_saved,              1),
        "pct_reduction":         round(pct,                   1),
        # 1 tree absorbs ~21.7 kg CO₂/yr
        "trees_equivalent":      round(kg_saved / 21.7,       1),
        # UK petrol car emits ~0.21 kg CO₂/mile
        "car_miles_equivalent":  int(round(kg_saved / 0.21,   0)),
    }
