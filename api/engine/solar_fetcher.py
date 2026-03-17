"""
Solar generation data fetcher.

Resolves a UK postcode → lat/lon via postcodes.io, then pulls one year of
hourly PV output from the PVGIS API (re.jrc.ec.europa.eu) and converts to
12 monthly half-hourly (48-slot) generation profiles.
"""
from __future__ import annotations
import httpx

PVGIS_URL    = "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc"
POSTCODE_URL = "https://api.postcodes.io/postcodes/{}"
DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

ORIENTATION_ASPECT: dict[str, float] = {
    "south":      0.0,
    "south_east": -45.0,
    "south_west":  45.0,
    "east":       -90.0,
    "west":        90.0,
    "north":      180.0,
}


async def resolve_postcode(postcode: str) -> tuple[float, float]:
    """Return (lat, lon) for a UK postcode, raises ValueError if not found."""
    clean = postcode.strip().replace(" ", "").upper()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(POSTCODE_URL.format(clean))
    if resp.status_code != 200:
        raise ValueError(f"Postcode '{postcode}' not found.")
    data = resp.json()
    result = data.get("result")
    if not result:
        raise ValueError(f"Postcode '{postcode}' not found.")
    return float(result["latitude"]), float(result["longitude"])


async def fetch_solar_profiles(
    lat: float,
    lon: float,
    peak_power_kwp: float,
    tilt_deg: float,
    orientation: str,
    loss_pct: float = 14.0,
) -> dict:
    """
    Fetch hourly PV output from PVGIS for one calendar year (2023) and return:
      monthly_profiles  — list[list[float]], 12 × 48, kWh per half-hour slot
      annual_kwh        — float, estimated annual generation
    """
    aspect = ORIENTATION_ASPECT.get(orientation, 0.0)

    params = {
        "lat":           lat,
        "lon":           lon,
        "peakpower":     peak_power_kwp,
        "loss":          loss_pct,
        "angle":         tilt_deg,
        "aspect":        aspect,
        "pvcalculation": 1,
        "outputformat":  "json",
        "startyear":     2023,
        "endyear":       2023,
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.get(PVGIS_URL, params=params)
    if resp.status_code != 200:
        raise ValueError(f"PVGIS request failed (HTTP {resp.status_code}). Check coordinates.")
    hourly = resp.json()["outputs"]["hourly"]

    # Accumulate sum and count for each (month, hour) pair
    # time format: "20230115:1010" → month = int([4:6])-1, hour = int([9:11])
    monthly_hour_sum   = [[0.0] * 24 for _ in range(12)]
    monthly_hour_count = [[0]   * 24 for _ in range(12)]
    for row in hourly:
        t = row["time"]
        m = int(t[4:6]) - 1
        h = int(t[9:11])
        monthly_hour_sum[m][h]   += float(row.get("P", 0.0))
        monthly_hour_count[m][h] += 1

    # Average watts per (month, hour), then expand to 48 half-hour slots
    monthly_profiles: list[list[float]] = []
    for m in range(12):
        profile: list[float] = []
        for h in range(24):
            cnt = monthly_hour_count[m][h] or 1
            avg_w = monthly_hour_sum[m][h] / cnt
            slot_kwh = avg_w * 0.5 / 1000.0   # 30-min energy in kWh
            profile.append(slot_kwh)
            profile.append(slot_kwh)           # duplicate for second half-hour
        monthly_profiles.append(profile)

    annual_kwh = sum(
        sum(monthly_profiles[m]) * DAYS_IN_MONTH[m]
        for m in range(12)
    )

    return {
        "monthly_profiles": monthly_profiles,
        "annual_kwh":       round(annual_kwh, 0),
    }


def weighted_avg_profile(monthly_profiles: list[list[float]]) -> list[float]:
    """Compute day-weighted annual average of 12 monthly 48-slot profiles."""
    avg = [0.0] * 48
    for m, profile in enumerate(monthly_profiles):
        days = DAYS_IN_MONTH[m]
        for s in range(48):
            avg[s] += profile[s] * days
    return [v / 365.0 for v in avg]
