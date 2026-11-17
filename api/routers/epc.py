"""
GET /api/epc/lookup — look up the homes at a postcode on the EPC register, so the
homeowner can pick theirs and we can pre-fill property type, size, heating and an
estimate of annual electricity use.

Source: the GOV.UK "Get energy performance of buildings data" API, which replaced
epc.opendatacommunities.org on 30 May 2026.
  1. GET /api/domestic/search?postcode=…           → the certificates at the postcode
  2. GET /api/certificate?certificate_number=…       → each certificate's details
Auth: a bearer token from a GOV.UK One Login account on that service, in the
EPC_API_TOKEN environment variable. Docs:
https://get-energy-performance-data.communities.gov.uk/api-technical-documentation

Certificate fields differ slightly between schema versions (RdSAP/SAP), so each one
is read defensively. Postcodes and addresses are never logged.
"""
from __future__ import annotations

import asyncio
import os
import re

import httpx
from fastapi import APIRouter, HTTPException, Query

from engine.extra_loads import DEFAULT_FLOOR_AREA_M2, HEAT_DEMAND_PER_M2, HEAT_DEMAND_PER_M2_UNKNOWN
from engine.profile_estimator import SUGGESTED_KWH

router = APIRouter(tags=["epc"])

EPC_API = "https://api.get-energy-performance-data.communities.gov.uk"
# Shown to homeowners (followed by "Please enter your home's details below instead."), so no server jargon.
LOOKUP_OFF = "Looking up homes by postcode isn't available right now."
TIMEOUT_S = 10.0
MAX_HOMES = 40          # homes shown per postcode (newest certificate per address)
CONCURRENCY = 8         # certificate fetches in flight at once (service limit: 6000 per 5 minutes)

HEAT_PUMP_EFFICIENCY = 3.0   # heat delivered per kWh of electricity (same default as extra_loads)


class EpcUnavailable(Exception):
    def __init__(self, status: int, detail: str):
        self.status, self.detail = status, detail


# ── Talking to the service ────────────────────────────────────────────────────

async def _get_json(client: httpx.AsyncClient, path: str, params: dict) -> tuple[int, dict | None]:
    """GET a path on the EPC API. Returns (status, json body or None). Patched in tests."""
    resp = await client.get(f"{EPC_API}{path}", params=params)
    try:
        body = resp.json()
    except ValueError:
        body = None
    return resp.status_code, body


def _raise_for(status: int) -> None:
    if status in (401, 403):   # the token is missing, wrong or expired: fix EPC_API_TOKEN on the server
        raise EpcUnavailable(503, LOOKUP_OFF)
    if status == 429:
        raise EpcUnavailable(503, "The EPC register is busy. Please try again in a minute.")
    raise EpcUnavailable(502, "The EPC register returned an unexpected error. Please try again later.")


def _records(body: dict | None) -> list[dict]:
    """The certificate list from a search response (the docs show it wrapped in "data")."""
    data = (body or {}).get("data", body)
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list):
                return [r for r in v if isinstance(r, dict)]
    return []


# ── Reading a certificate ─────────────────────────────────────────────────────

def _val(x):
    """Some schemas wrap text as {"value": …, "language": …}."""
    return x.get("value") if isinstance(x, dict) and "value" in x else x


def _num(x) -> float | None:
    try:
        v = float(_val(x))
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def map_property_type(dwelling_type: str | None) -> str:
    t = (dwelling_type or "").lower()
    if "flat" in t or "maisonette" in t:
        return "flat"
    if "semi" in t:
        return "semi"
    if "terrace" in t:
        return "terraced"
    if "detached" in t:
        return "detached"
    return "semi"


def map_bedrooms(habitable_rooms) -> int | None:
    rooms = _num(habitable_rooms)
    return None if rooms is None else int(min(max(1, rooms - 1), 5))


def heating_kind(cert: dict) -> tuple[str, str]:
    """
    ("heat_pump" | "electric" | "gas" | "other_fuel" | "unknown", description).
    A heat pump or electric heating anywhere in the main heating wins, because that's
    what changes the electricity bill; otherwise mains gas, then other fuels.
    """
    descs = [str(_val(h.get("description")) or "") for h in cert.get("main_heating") or [] if isinstance(h, dict)]
    text = " | ".join(descs).lower()
    source = cert.get("sap_energy_source") or {}
    mains_gas = str(source.get("mains_gas", source.get("main_gas", ""))).upper() in ("Y", "TRUE")
    if "heat pump" in text:
        kind = "heat_pump"
    elif "electric" in text or "storage heater" in text:
        kind = "electric"
    elif "gas" in text or mains_gas:
        kind = "gas"
    elif any(w in text for w in ("oil", "lpg", "coal", "anthracite", "wood", "biomass", "smokeless", "solid fuel")):
        kind = "other_fuel"
    else:
        kind = "unknown"
    return kind, " | ".join(d for d in descs if d)


def has_solar(cert: dict) -> bool:
    source = cert.get("sap_energy_source") or {}
    pv = source.get("photovoltaic_supply") or {}
    if isinstance(pv, dict):
        if pv.get("pv_arrays"):
            return True
        # The share of roof covered by panels sits either directly here (older SAP) or one level down.
        nd = pv.get("none_or_no_details")
        for holder in (pv, nd if isinstance(nd, dict) else {}):
            if (_num(holder.get("percent_roof_area")) or 0) > 0:
                return True
    return bool(source.get("pv_arrays"))


def has_battery(cert: dict) -> bool:
    return bool((cert.get("sap_energy_source") or {}).get("pv_batteries"))


# ── Estimating annual electricity use ─────────────────────────────────────────

def _beis_baseline(prop_type: str, beds: int | None) -> int | None:
    table = SUGGESTED_KWH.get(prop_type, {})
    if not table:
        return None
    if beds is None:
        beds = sorted(table)[len(table) // 2]
    if beds in table:
        return table[beds]
    return table[min(table, key=lambda k: abs(k - beds))]


def estimate_annual_kwh(
    prop_type: str,
    beds: int | None,
    floor_area: float | None,
    kind: str,
    epc_band: str | None,
) -> tuple[int, str]:
    """
    Annual electricity use (kWh) and a confidence label.

    Start from the BEIS metered baseline for the property type and bedrooms: typical
    electricity use for lights, appliances and cooking in homes heated by other fuels.
    Only when the home is heated by electricity is heating added: the home's heat demand
    (floor area × a rate for its EPC band) at full rate for direct electric heating such
    as storage heaters, or divided by 3 for a heat pump. The EPC's own energy figure is
    mostly about the heating fuel, so it isn't used for electricity.
    """
    base = _beis_baseline(prop_type, beds)
    if base is None:
        base = int(round((floor_area or 85) * 40 / 100) * 100)
    heat = None
    if kind in ("electric", "heat_pump"):
        area = floor_area or DEFAULT_FLOOR_AREA_M2.get(prop_type, 90)
        per_m2 = HEAT_DEMAND_PER_M2.get((epc_band or "").upper()[:1], HEAT_DEMAND_PER_M2_UNKNOWN)
        heat = area * per_m2 / (HEAT_PUMP_EFFICIENCY if kind == "heat_pump" else 1.0)
    kwh = base + (heat or 0)
    kwh = int(round(min(max(kwh, 500), 20000) / 100) * 100)
    confidence = "medium" if beds is not None else "low"
    return kwh, confidence


def parse_certificate(summary: dict, cert: dict) -> dict:
    """One home for the address picker, with what we can pre-fill from its certificate."""
    dwelling = _val(cert.get("dwelling_type"))
    prop_type = map_property_type(dwelling)
    beds = map_bedrooms(cert.get("habitable_room_count"))
    floor_area = _num(cert.get("total_floor_area"))
    band = _val(cert.get("current_energy_efficiency_band")) or summary.get("currentEnergyEfficiencyBand")
    kind, heating_desc = heating_kind(cert)
    kwh, confidence = estimate_annual_kwh(prop_type, beds, floor_area, kind, band)
    source = cert.get("sap_energy_source") or {}
    return {
        "certificate_number": summary.get("certificateNumber"),
        "lmk_key": summary.get("certificateNumber"),        # old field name, kept for the classic calculator
        "address": _address(summary),
        "dwelling_type": dwelling,
        "property_type": prop_type,
        "bedrooms": beds if beds is not None else 3,
        "floor_area_m2": floor_area,
        "epc_rating": band,
        "energy_per_m2": _num(cert.get("energy_consumption_current")),
        "registration_date": summary.get("registrationDate") or cert.get("registration_date"),
        "heating_kind": kind,
        "heating_description": heating_desc or None,
        "heating_type": "electric" if kind in ("electric", "heat_pump") else "gas",   # for /estimate
        "has_gas": str(source.get("mains_gas", source.get("main_gas", ""))).upper() in ("Y", "TRUE") or kind == "gas",
        "has_heat_pump": kind == "heat_pump",
        "has_solar": has_solar(cert),
        "has_battery": has_battery(cert),
        "annual_kwh": kwh,
        "confidence": confidence,
    }


def _address(summary: dict) -> str:
    parts = [summary.get(f"addressLine{i}") for i in range(1, 5)] + [summary.get("postTown")]
    text = ", ".join(str(p).strip() for p in parts if p and str(p).strip())
    text = re.sub(r"\s+", " ", text)
    return text.title() if text.isupper() or text.islower() else text


def _sort_key(address: str):
    """Natural order: 2 Example Street before 10 Example Street."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", address)]


def _newest_per_address(records: list[dict]) -> list[dict]:
    newest: dict[str, dict] = {}
    for r in records:
        key = _address(r).lower()
        if not key:
            continue
        if key not in newest or str(r.get("registrationDate", "")) > str(newest[key].get("registrationDate", "")):
            newest[key] = r
    return sorted(newest.values(), key=lambda r: _sort_key(_address(r)))[:MAX_HOMES]


async def lookup_postcode(postcode: str, token: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=TIMEOUT_S, headers=headers) as client:
        status, body = await _get_json(client, "/api/domestic/search", {"postcode": postcode, "page_size": 200})
        if status == 404:
            return []
        if status != 200:
            _raise_for(status)
        summaries = _newest_per_address(_records(body))

        sem = asyncio.Semaphore(CONCURRENCY)

        async def fetch(summary: dict) -> dict | None:
            async with sem:
                try:
                    s, b = await _get_json(client, "/api/certificate",
                                           {"certificate_number": summary.get("certificateNumber")})
                except httpx.HTTPError:
                    return None
            if s in (401, 403, 429):
                _raise_for(s)
            if s != 200 or not isinstance(b, dict):
                return None
            cert = b.get("data", b)
            return parse_certificate(summary, cert) if isinstance(cert, dict) else None

        homes = [h for h in await asyncio.gather(*(fetch(s) for s in summaries)) if h]
    if summaries and not homes:
        raise EpcUnavailable(502, "We found certificates at this postcode but couldn't read their details. Please try again later.")
    return homes


def normalise_postcode(postcode: str) -> str:
    clean = re.sub(r"\s+", "", postcode).upper()
    if not re.fullmatch(r"[A-Z]{1,2}\d[A-Z\d]?\d[A-Z]{2}", clean):
        raise HTTPException(status_code=422, detail="That doesn't look like a UK postcode.")
    return f"{clean[:-3]} {clean[-3:]}"


@router.get("/epc/lookup")
async def epc_lookup(postcode: str = Query(..., min_length=5, max_length=10)):
    token = os.getenv("EPC_API_TOKEN", "")
    if not token:
        raise HTTPException(status_code=503, detail=LOOKUP_OFF)   # EPC_API_TOKEN isn't set
    pc = normalise_postcode(postcode)
    try:
        homes = await lookup_postcode(pc, token)
    except EpcUnavailable as e:
        raise HTTPException(status_code=e.status, detail=e.detail)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="The EPC register took too long to answer. Please try again.")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="We couldn't reach the EPC register. Please try again later.")
    if not homes:
        return {"found": False, "properties": []}
    return {"found": True, "properties": homes}
