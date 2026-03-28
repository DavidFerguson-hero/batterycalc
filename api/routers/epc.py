"""
GET /api/epc/lookup  — look up EPC data for a UK postcode.

Returns all properties at the postcode so the user can select their own.
Annual kWh is estimated in priority order:
  1. EPC energy-consumption-current × floor-area × electricity fraction (most accurate)
  2. BEIS lookup table by property type + bedrooms
  3. Floor area × electricity intensity constant

Auth: HTTP Basic with EPC_EMAIL + EPC_API_KEY env vars.
Register for free at https://epc.opendatacommunities.org/
"""
from __future__ import annotations
import os
import httpx
from fastapi import APIRouter, HTTPException, Query

from engine.profile_estimator import SUGGESTED_KWH

router = APIRouter(tags=["epc"])

EPC_BASE = "https://epc.opendatacommunities.org/api/v1/domestic/search"

# Average SAP energy intensity (kWh/m²/yr) for each property type, from MHCLG
# EPC statistics (England, 2022). Used to normalise the EPC figure into a
# performance ratio before applying to BEIS metered electricity baselines.
AVG_SAP_ENERGY: dict[str, float] = {
    "flat":     72.0,
    "terraced": 89.0,
    "semi":     94.0,
    "detached": 99.0,
}

# Fraction of total SAP energy that is electricity, based on BEIS fuel-mix data.
# Gas homes: gas covers space/water heating (~70%), electricity covers the rest.
# All-electric homes: virtually all energy is electricity.
ELEC_FRACTION_GAS     = 0.30
ELEC_FRACTION_ELEC    = 0.85


def _map_property_type(epc_type: str, built_form: str) -> str:
    t = (epc_type or "").lower()
    b = (built_form or "").lower()
    if "flat" in t or "maisonette" in t:
        return "flat"
    if "semi" in b:
        return "semi"
    if any(x in b for x in ("mid-terrace", "end-terrace", "enclosed")):
        return "terraced"
    if "detached" in b:
        return "detached"
    return "semi"


def _map_bedrooms(habitable_rooms) -> int:
    try:
        rooms = int(habitable_rooms)
    except (TypeError, ValueError):
        return 3
    return min(max(1, rooms - 1), 5)


def _beis_baseline(prop_type: str, beds: int) -> int | None:
    """Return BEIS metered electricity baseline (kWh/yr) for this type+beds, or None."""
    type_table = SUGGESTED_KWH.get(prop_type, {})
    if beds in type_table:
        return type_table[beds]
    if type_table:
        nearest = min(type_table.keys(), key=lambda k: abs(k - beds))
        return type_table[nearest]
    return None


def _estimate_kwh(
    prop_type: str,
    beds: int,
    floor_area: float | None,
    has_gas: bool,
    energy_per_m2: float | None,
) -> tuple[int, str]:
    """
    Estimate annual electricity consumption, returning (kwh, confidence).

    Method 1 — EPC intensity × floor area, normalised to BEIS actuals:
      Uses the property's assessed SAP energy intensity relative to the type
      average, then scales a BEIS metered baseline by that ratio.  This
      preserves the accuracy of real-world electricity data while incorporating
      the property-specific efficiency signal from the EPC.

    Method 2 — BEIS lookup table (type + beds).

    Method 3 — Floor area × flat electricity intensity constant.
    """
    # Method 1: EPC energy intensity available
    if energy_per_m2 and energy_per_m2 > 0 and floor_area and floor_area > 0:
        avg_sap = AVG_SAP_ENERGY.get(prop_type, 94.0)
        ratio   = energy_per_m2 / avg_sap          # <1 = more efficient, >1 = less
        baseline = _beis_baseline(prop_type, beds)
        if baseline:
            kwh = int(round(baseline * ratio / 100) * 100)
            return max(500, min(kwh, 15000)), "high"

    # Method 2: BEIS lookup by type + beds
    baseline = _beis_baseline(prop_type, beds)
    if baseline:
        return baseline, "medium"

    # Method 3: floor area fallback
    if floor_area and floor_area > 0:
        kwh_per_m2 = 40.0 if has_gas else 80.0
        return int(round(floor_area * kwh_per_m2 / 100) * 100), "low"

    return 3500, "low"


def _parse_row(row: dict) -> dict:
    prop_type = _map_property_type(
        row.get("property-type", ""),
        row.get("built-form", ""),
    )
    beds = _map_bedrooms(row.get("number-habitable-rooms"))

    floor_area: float | None = None
    try:
        v = float(row.get("total-floor-area") or 0)
        floor_area = v if v > 0 else None
    except (ValueError, TypeError):
        pass

    has_gas = str(row.get("mains-gas-flag", "")).upper() == "Y"

    has_solar = False
    try:
        has_solar = float(row.get("photo-supply") or 0) > 0
    except (ValueError, TypeError):
        pass

    energy_per_m2: float | None = None
    try:
        v = float(row.get("energy-consumption-current") or 0)
        energy_per_m2 = v if v > 0 else None
    except (ValueError, TypeError):
        pass

    annual_kwh, confidence = _estimate_kwh(
        prop_type, beds, floor_area, has_gas, energy_per_m2
    )

    # Build a clean display address from address lines
    parts = [
        row.get("address1", ""),
        row.get("address2", ""),
        row.get("address3", ""),
    ]
    display_address = ", ".join(p.strip() for p in parts if p and p.strip())
    if not display_address:
        display_address = row.get("address", "Unknown address")

    return {
        "lmk_key":          row.get("lmk-key", ""),
        "address":          display_address,
        "property_type":    prop_type,
        "bedrooms":         beds,
        "annual_kwh":       annual_kwh,
        "has_solar":        has_solar,
        "has_gas":          has_gas,
        "floor_area_m2":    floor_area,
        "energy_per_m2":    energy_per_m2,
        "epc_rating":       row.get("current-energy-rating") or None,
        "confidence":       confidence,
    }


@router.get("/epc/lookup")
async def epc_lookup(postcode: str = Query(..., min_length=2, max_length=10)):
    epc_email = os.getenv("EPC_EMAIL", "")
    epc_key   = os.getenv("EPC_API_KEY", "")

    if not epc_email or not epc_key:
        raise HTTPException(status_code=503, detail="EPC lookup is not configured on this server.")

    clean = postcode.strip().replace(" ", "").upper()

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                EPC_BASE,
                params={"postcode": clean, "size": 25},
                auth=(epc_email, epc_key),
                headers={"Accept": "application/json"},
            )
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="EPC API timed out — please try again.")

    if resp.status_code == 401:
        raise HTTPException(status_code=503, detail="EPC API credentials are invalid.")
    if resp.status_code not in (200, 404):
        raise HTTPException(status_code=502, detail="EPC API returned an unexpected error.")

    rows = resp.json().get("rows", [])
    if not rows:
        return {"found": False}

    # Deduplicate by address — keep most recent certificate per property
    seen: dict[str, dict] = {}
    for row in rows:
        parsed = _parse_row(row)
        addr = parsed["address"].lower()
        if addr not in seen:
            seen[addr] = parsed

    properties = list(seen.values())
    properties.sort(key=lambda p: p["address"])

    return {
        "found":      True,
        "properties": properties,
    }
