"""
Installed cost figures (decision D4), read from api/data/costs.json.

Everything that needs a price — the standard battery sizes, the classic calculator's
price slider, the lifetime model's cost range and inverter replacement, and the
context costs for solar, heat pumps and EV chargers — comes from that one file.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

COSTS_FILE = Path(__file__).resolve().parent.parent / "data" / "costs.json"


@lru_cache(maxsize=1)
def load_costs() -> dict:
    return json.loads(COSTS_FILE.read_text())


def _sizes() -> list[dict]:
    return sorted(load_costs()["battery"]["sizes"], key=lambda s: s["kwh"])


def battery_price(kwh: float) -> dict[str, float]:
    """
    Installed price range {low, typical, high} for a battery of any size.
    Between standard sizes the price is interpolated; outside them it scales
    with the per-kWh price of the nearest standard size.
    """
    sizes = _sizes()
    if kwh <= 0:
        raise ValueError("Battery size must be positive.")
    lo, hi = sizes[0], sizes[-1]
    if kwh <= lo["kwh"] or kwh >= hi["kwh"]:
        ref = lo if kwh <= lo["kwh"] else hi
        return {k: ref[k] * kwh / ref["kwh"] for k in ("low", "typical", "high")}
    for a, b in zip(sizes, sizes[1:]):
        if a["kwh"] <= kwh <= b["kwh"]:
            f = (kwh - a["kwh"]) / (b["kwh"] - a["kwh"])
            return {k: a[k] + f * (b[k] - a[k]) for k in ("low", "typical", "high")}
    raise AssertionError("unreachable")


def price_range_for(kwh: float, price: float) -> tuple[float, float]:
    """Low and high prices around a given price, using this size's low/typical and high/typical ratios."""
    p = battery_price(kwh)
    return price * p["low"] / p["typical"], price * p["high"] / p["typical"]


def fair_price(kwh: float, your_price: float | None = None) -> dict:
    """The fair installed price range for a size, and where a quoted price sits in it."""
    p = battery_price(kwh)
    out = {
        "kwh": kwh,
        "low": round(p["low"], -1),
        "typical": round(p["typical"], -1),
        "high": round(p["high"], -1),
        "as_of": load_costs()["as_of"],
    }
    if your_price is not None:
        out["your_price"] = round(your_price)
        out["your_price_is"] = (
            "below_range" if your_price < p["low"] else
            "above_range" if your_price > p["high"] else
            "within_range"
        )
    return out


def standard_batteries() -> list[dict]:
    """The standard sizes the optimiser sweeps, priced at their typical installed cost."""
    return [{"kwh": s["kwh"], "cost": s["typical"], "label": s["label"]} for s in _sizes()]


def slider_costs() -> dict[float, int]:
    """Typical installed price by size for the classic calculator's price slider (3–25 kWh)."""
    sizes = [float(k) for k in range(3, 26)] + [7.5, 13.5]
    return {(int(k) if k.is_integer() else k): int(round(battery_price(k)["typical"], -2))
            for k in sorted(sizes)}


def inverter_replacement() -> dict[str, float]:
    c = load_costs()["inverter_replacement"]
    return {k: c[k] for k in ("low", "typical", "high")}


def default_cost_range_ratios() -> tuple[float, float]:
    """Average low/typical and high/typical across the standard sizes."""
    sizes = _sizes()
    return (
        sum(s["low"] / s["typical"] for s in sizes) / len(sizes),
        sum(s["high"] / s["typical"] for s in sizes) / len(sizes),
    )


def context_costs() -> dict:
    """Solar, heat pump and EV charger costs for the results page's context panel."""
    out = {}
    for key, c in load_costs()["context"].items():
        item = {"label": c["label"], "low": c["low"], "typical": c["typical"], "high": c["high"]}
        if "grant" in c:
            item["grant"] = c["grant"]
            item["grant_name"] = c["grant_name"]
            item["after_grant"] = {k: max(0, c[k] - c["grant"]) for k in ("low", "typical", "high")}
        out[key] = item
    return out
