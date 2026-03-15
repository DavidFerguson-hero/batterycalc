#!/usr/bin/env python3
"""
Nightly tariff rate checker for BatterySizer.

Checks known sources for each tariff and compares against the rates
currently stored in engine/tariffs.py.

Sources:
  - Octopus Energy public API  (Octopus Go, Intelligent Go, Cosy)
  - Ofgem price cap page        (Standard Variable, British Gas SV)
  - Manual links                (Economy 7, E.ON, EDF, Scottish Power)

Never auto-edits tariffs.py — all changes require human review.
Appends a JSON entry to frontend/public/tariff-logs.json.
"""
from __future__ import annotations

import json
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_FILE  = REPO_ROOT / "frontend" / "public" / "tariff-logs.json"
MAX_RUNS  = 90
TIMEOUT   = 20

# ── Rates currently in engine/tariffs.py ──────────────────────────────────────
# Keep this in sync whenever tariffs.py is manually updated.
CURRENT: dict[str, dict[str, float]] = {
    "octopusGo":          {"night_p": 7.0,  "day_p": 38.72, "standing_p": 47.0},
    "intelligentOctopus": {"night_p": 9.0,  "day_p": 38.0,  "standing_p": 47.0},
    "octopusCosy":        {"cosy_p": 12.0,  "peak_p": 50.0, "standard_p": 28.0, "standing_p": 47.0},
    "economy7":           {"night_p": 9.0,  "day_p": 33.0,  "standing_p": 53.0},
    "eonNextDrive":       {"night_p": 8.5,  "day_p": 35.0,  "standing_p": 53.0},
    "edfGoElectric":      {"night_p": 8.0,  "day_p": 34.0,  "standing_p": 50.0},
    "edfFreePhase":       {"night_p": 17.0, "day_p": 22.1,  "peak_p": 38.4, "standing_p": 53.2},
    "scottishPower":      {"night_p": 10.0, "day_p": 36.0,  "standing_p": 55.0},
    "currentFlat":        {"unit_p": 28.16, "standing_p": 53.0},
    "britishGasSV":       {"unit_p": 24.5,  "standing_p": 61.0},
}

TARIFF_NAMES: dict[str, str] = {
    "octopusGo":          "Octopus Go",
    "intelligentOctopus": "Intelligent Octopus Go",
    "octopusCosy":        "Octopus Cosy",
    "economy7":           "Economy 7",
    "eonNextDrive":       "E.ON Next Drive",
    "edfGoElectric":      "EDF GoElectric Overnight",
    "edfFreePhase":       "EDF FreePhase",
    "scottishPower":      "Scottish Power Smart",
    "currentFlat":        "Current Flat Rate (SVT)",
    "britishGasSV":       "British Gas Standard Variable",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _changes(current: dict[str, float], found: dict[str, float]) -> list[str]:
    """Return human-readable descriptions of changed rates (>0.05p threshold)."""
    out = []
    for k in sorted(set(current) & set(found)):
        cv, fv = current[k], found[k]
        if abs(cv - fv) > 0.05:
            out.append(f"{k}: {cv}p → {fv}p")
    return out


def _ok(key: str, source: str, source_url: str, found: dict, extra: dict | None = None) -> dict:
    diffs = _changes(CURRENT[key], found)
    result = {
        "key": key,
        "name": TARIFF_NAMES[key],
        "status": "changed" if diffs else "ok",
        "source": source,
        "source_url": source_url,
        "current_rates": CURRENT[key],
        "found_rates": found,
        "changes": diffs,
    }
    if extra:
        result.update(extra)
    return result


def _err(key: str, source: str, error: str) -> dict:
    return {
        "key": key,
        "name": TARIFF_NAMES[key],
        "status": "error",
        "source": source,
        "error": error,
        "current_rates": CURRENT[key],
    }


def _manual(key: str, url: str, notes: str) -> dict:
    return {
        "key": key,
        "name": TARIFF_NAMES[key],
        "status": "manual",
        "source": "Manual verification required",
        "source_url": url,
        "current_rates": CURRENT[key],
        "notes": notes,
    }


# ── Octopus Energy API ────────────────────────────────────────────────────────

def _octopus_products() -> list[dict]:
    """Fetch all currently-active Octopus import products."""
    url = "https://api.octopus.energy/v1/products/?brand=OCTOPUS_ENERGY&page_size=100&is_prepay=false"
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return [
        p for p in r.json().get("results", [])
        if p.get("available_to") is None and p.get("direction") == "IMPORT"
    ]


def _octopus_product_rates(code: str) -> dict | None:
    """Day unit rate + standing charge (pence inc VAT, region A, direct debit monthly)."""
    r = requests.get(f"https://api.octopus.energy/v1/products/{code}/", timeout=TIMEOUT)
    r.raise_for_status()
    dd = (
        r.json()
        .get("single_register_electricity_tariffs", {})
        .get("_A", {})
        .get("direct_debit_monthly", {})
    )
    if not dd:
        return None
    return {
        "day_p":       round(dd.get("standard_unit_rate_inc_vat", 0), 2),
        "standing_p":  round(dd.get("standing_charge_inc_vat", 0), 2),
    }


def _octopus_night_rate(code: str) -> float | None:
    """
    For Go/Intelligent/Cosy, the cheap overnight rate is the minimum
    across all 48 half-hourly slots in the unit-rates endpoint.
    """
    tariff_code = f"E-1R-{code}-A"
    url = (
        f"https://api.octopus.energy/v1/products/{code}/"
        f"electricity-tariffs/{tariff_code}/standard-unit-rates/?page_size=48"
    )
    try:
        r = requests.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        vals = [s["value_inc_vat"] for s in r.json().get("results", []) if "value_inc_vat" in s]
        return round(min(vals), 2) if vals else None
    except Exception:
        return None


def _octopus_cosy_slot_rates(code: str) -> tuple[float | None, float | None]:
    """Return (cosy_rate, peak_rate) from Cosy slot rates."""
    tariff_code = f"E-1R-{code}-A"
    url = (
        f"https://api.octopus.energy/v1/products/{code}/"
        f"electricity-tariffs/{tariff_code}/standard-unit-rates/?page_size=48"
    )
    try:
        r = requests.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        vals = [s["value_inc_vat"] for s in r.json().get("results", []) if "value_inc_vat" in s]
        if vals:
            return round(min(vals), 2), round(max(vals), 2)
    except Exception:
        pass
    return None, None


def check_octopus_go(products: list[dict]) -> dict:
    try:
        prod = next(
            (p for p in products
             if "Octopus Go" in p.get("display_name", "")
             and "Intelligent" not in p.get("display_name", "")),
            None,
        )
        if not prod:
            return _err("octopusGo", "Octopus Energy API", "No active Octopus Go product found")

        code  = prod["code"]
        rates = _octopus_product_rates(code)
        if not rates:
            return _err("octopusGo", "Octopus Energy API", f"Could not retrieve rates for {code}")

        night = _octopus_night_rate(code)
        if night is not None:
            rates["night_p"] = night

        return _ok(
            "octopusGo",
            "Octopus Energy API",
            f"https://api.octopus.energy/v1/products/{code}/",
            rates,
            {"product_code": code, "product_name": prod.get("display_name", "")},
        )
    except Exception as e:
        return _err("octopusGo", "Octopus Energy API", f"{e}\n{traceback.format_exc()}")


def check_intelligent_octopus(products: list[dict]) -> dict:
    try:
        prod = next(
            (p for p in products if "Intelligent Octopus" in p.get("display_name", "")),
            None,
        )
        if not prod:
            return _err("intelligentOctopus", "Octopus Energy API", "No active Intelligent Octopus product found")

        code  = prod["code"]
        rates = _octopus_product_rates(code)
        if not rates:
            return _err("intelligentOctopus", "Octopus Energy API", f"Could not retrieve rates for {code}")

        night = _octopus_night_rate(code)
        if night is not None:
            rates["night_p"] = night

        return _ok(
            "intelligentOctopus",
            "Octopus Energy API",
            f"https://api.octopus.energy/v1/products/{code}/",
            rates,
            {"product_code": code, "product_name": prod.get("display_name", "")},
        )
    except Exception as e:
        return _err("intelligentOctopus", "Octopus Energy API", f"{e}")


def check_octopus_cosy(products: list[dict]) -> dict:
    try:
        prod = next(
            (p for p in products if "Cosy" in p.get("display_name", "")),
            None,
        )
        if not prod:
            return _err("octopusCosy", "Octopus Energy API", "No active Octopus Cosy product found")

        code  = prod["code"]
        rates = _octopus_product_rates(code)
        if not rates:
            return _err("octopusCosy", "Octopus Energy API", f"Could not retrieve rates for {code}")

        cosy, peak = _octopus_cosy_slot_rates(code)
        if cosy is not None:
            rates["cosy_p"]     = cosy
            rates["peak_p"]     = peak
            rates["standard_p"] = rates.pop("day_p", CURRENT["octopusCosy"]["standard_p"])

        return _ok(
            "octopusCosy",
            "Octopus Energy API",
            f"https://api.octopus.energy/v1/products/{code}/",
            rates,
            {"product_code": code, "product_name": prod.get("display_name", "")},
        )
    except Exception as e:
        return _err("octopusCosy", "Octopus Energy API", f"{e}")


# ── Ofgem price cap ───────────────────────────────────────────────────────────

def check_ofgem() -> tuple[dict, dict]:
    """Returns (currentFlat_result, britishGasSV_result)."""
    source_url = "https://www.ofgem.gov.uk/check-if-energy-price-cap-affects-you"
    try:
        r = requests.get(
            source_url, timeout=TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 BatterySizer-TariffBot/1.0"},
        )
        r.raise_for_status()
        text = BeautifulSoup(r.text, "html.parser").get_text(" ")

        # Look for unit-rate figures in pence e.g. "24.5p per kWh" or "24.50 pence/kWh"
        matches = re.findall(
            r"(\d{1,2}(?:\.\d{1,2})?)\s*p(?:ence)?\s*(?:per\s*)?(?:kWh|kilowatt.hour)",
            text, re.IGNORECASE,
        )
        rates_found = [float(m) for m in matches if 10 <= float(m) <= 50]

        if rates_found:
            unit_p = round(max(set(rates_found), key=rates_found.count), 2)
            flat   = _ok("currentFlat",  "Ofgem Price Cap", source_url, {"unit_p": unit_p, "standing_p": CURRENT["currentFlat"]["standing_p"]})
            bg     = _ok("britishGasSV", "Ofgem Price Cap", source_url, {"unit_p": unit_p, "standing_p": CURRENT["britishGasSV"]["standing_p"]})
            return flat, bg
        else:
            note = "Rate not extracted automatically — check Ofgem page manually"
            flat = {**_manual("currentFlat",  source_url, note)}
            bg   = {**_manual("britishGasSV", source_url, note)}
            return flat, bg

    except Exception as e:
        return (
            _err("currentFlat",  "Ofgem Price Cap", str(e)),
            _err("britishGasSV", "Ofgem Price Cap", str(e)),
        )


# ── Main ──────────────────────────────────────────────────────────────────────

def run_check() -> dict:
    now    = datetime.now(timezone.utc)
    run_id = now.strftime("%Y%m%dT%H%M%SZ")
    print(f"🔍 BatterySizer Tariff Check — {now.strftime('%Y-%m-%d %H:%M UTC')}")

    results: dict[str, dict] = {}

    # ── Octopus (official API) ─────────────────────────────────────────────
    print("  Fetching Octopus products…")
    try:
        products = _octopus_products()
        results["octopusGo"]          = check_octopus_go(products)
        results["intelligentOctopus"] = check_intelligent_octopus(products)
        results["octopusCosy"]        = check_octopus_cosy(products)
    except Exception as e:
        err_msg = str(e)
        for k in ("octopusGo", "intelligentOctopus", "octopusCosy"):
            results[k] = _err(k, "Octopus Energy API", f"Products fetch failed: {err_msg}")

    for k in ("octopusGo", "intelligentOctopus", "octopusCosy"):
        st = results[k]["status"]
        icon = {"ok": "✓", "changed": "⚡", "error": "✗"}.get(st, "?")
        print(f"    {icon} {TARIFF_NAMES[k]}: {st}")

    # ── Ofgem price cap ────────────────────────────────────────────────────
    print("  Fetching Ofgem price cap…")
    flat, bg = check_ofgem()
    results["currentFlat"]  = flat
    results["britishGasSV"] = bg
    for k in ("currentFlat", "britishGasSV"):
        st = results[k]["status"]
        icon = {"ok": "✓", "changed": "⚡", "error": "✗", "manual": "—"}.get(st, "?")
        print(f"    {icon} {TARIFF_NAMES[k]}: {st}")

    # ── Manual checks ──────────────────────────────────────────────────────
    results["economy7"]     = _manual(
        "economy7",
        "https://www.uswitch.com/gas-electricity/guides/economy-7/",
        "Economy 7 rates vary by region and supplier. Check comparison sites for current regional averages.",
    )
    results["eonNextDrive"] = _manual(
        "eonNextDrive",
        "https://www.eonenergy.com/electric-vehicle-charging/next-drive-tariff.html",
        "Check E.ON tariff page — night 00:00–07:00, standing charge may vary.",
    )
    results["edfGoElectric"] = _manual(
        "edfGoElectric",
        "https://www.edfenergy.com/electric-cars/goelectric-overnight",
        "Check EDF GoElectric Overnight page for current night/day rates.",
    )
    results["edfFreePhase"] = _manual(
        "edfFreePhase",
        "https://www.edfenergy.com/for-homes/tariffs/freephase",
        "EDF FreePhase static rates — check EDF tariff page.",
    )
    results["scottishPower"] = _manual(
        "scottishPower",
        "https://www.scottishpower.co.uk/energy/time-of-use-tariff",
        "Scottish Power Smart Tariff — night 23:00–07:00.",
    )
    print(f"    — {len([k for k in results if results[k]['status'] == 'manual'])} tariffs flagged for manual verification")

    # ── Tally ──────────────────────────────────────────────────────────────
    statuses = [v["status"] for v in results.values()]
    summary = {
        "total":   len(results),
        "ok":      statuses.count("ok"),
        "changed": statuses.count("changed"),
        "manual":  statuses.count("manual"),
        "error":   statuses.count("error"),
    }
    overall = (
        "alert"  if summary["changed"] > 0 else
        "error"  if summary["error"]   > 0 else
        "ok"
    )

    print(f"\n  Summary: {summary['ok']} ok · {summary['changed']} changed · "
          f"{summary['manual']} manual · {summary['error']} errors → overall: {overall}")

    return {
        "id":        run_id,
        "timestamp": now.isoformat(),
        "overall":   overall,
        "summary":   summary,
        "tariffs":   results,
    }


def save_log(entry: dict) -> None:
    data = {"runs": []}
    if LOG_FILE.exists():
        try:
            data = json.loads(LOG_FILE.read_text())
        except Exception:
            pass
    data.setdefault("runs", []).insert(0, entry)
    data["runs"] = data["runs"][:MAX_RUNS]
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(json.dumps(data, indent=2))
    print(f"✅  Log saved → {LOG_FILE.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    entry = run_check()

    if entry["overall"] == "alert":
        print("\n⚡ RATE CHANGES DETECTED — review and update engine/tariffs.py:")
        for t in entry["tariffs"].values():
            if t.get("status") == "changed":
                for ch in t.get("changes", []):
                    print(f"   {t['name']}: {ch}")

    save_log(entry)
    sys.exit(0 if entry["overall"] in ("ok", "alert") else 1)
