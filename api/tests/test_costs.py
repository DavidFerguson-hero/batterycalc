"""Task 1.8 — cost data file (decision D4) and the fair price range."""
import pytest
from fastapi.testclient import TestClient

from engine.costs import (
    battery_price, context_costs, fair_price, inverter_replacement, load_costs,
    price_range_for, slider_costs, standard_batteries,
)
from engine.lifetime import INVERTER_REPLACEMENT_COST
from main import app


# ── The data file ─────────────────────────────────────────────────────────────

def _priced_items():
    c = load_costs()
    yield "battery", c["battery"]
    yield "inverter_replacement", c["inverter_replacement"]
    for k, v in c["context"].items():
        yield k, v


def test_every_figure_has_a_source_and_date():
    c = load_costs()
    assert c["as_of"]
    for name, item in list(_priced_items()) + [("vat", c["vat"])]:
        assert item["sources"], name
        for s in item["sources"]:
            assert s["url"].startswith("https://") and s["date"] and s["name"], (name, s)


def test_low_typical_high_are_ordered():
    for s in load_costs()["battery"]["sizes"]:
        assert s["low"] <= s["typical"] <= s["high"], s["kwh"]
    for name, item in _priced_items():
        if "typical" in item:
            assert item["low"] <= item["typical"] <= item["high"], name


def test_component_split_adds_up_to_typical():
    for s in load_costs()["battery"]["sizes"]:
        assert sum(s["components_typical"].values()) == s["typical"], s["kwh"]


def test_bigger_batteries_cost_more_but_less_per_kwh():
    sizes = sorted(load_costs()["battery"]["sizes"], key=lambda s: s["kwh"])
    typ = [s["typical"] for s in sizes]
    per_kwh = [s["typical"] / s["kwh"] for s in sizes]
    assert typ == sorted(typ)
    assert per_kwh[0] > per_kwh[-1]


def test_vat_is_zero_rated_with_an_end_date():
    v = load_costs()["vat"]
    assert v["battery_rate_pct"] == 0 and v["battery_rate_until"] == "2027-03-31"


# ── Lookups ───────────────────────────────────────────────────────────────────

def test_standard_size_prices_come_straight_from_the_file():
    for s in load_costs()["battery"]["sizes"]:
        assert battery_price(s["kwh"]) == {k: s[k] for k in ("low", "typical", "high")}


def test_prices_interpolate_between_sizes():
    a, b = battery_price(10), battery_price(13.5)
    mid = battery_price(11.75)
    for k in ("low", "typical", "high"):
        assert mid[k] == pytest.approx((a[k] + b[k]) / 2)


def test_prices_scale_per_kwh_outside_the_table():
    assert battery_price(2.5)["typical"] == pytest.approx(battery_price(5)["typical"] / 2)
    assert battery_price(25)["typical"] == pytest.approx(battery_price(20)["typical"] * 1.25)


def test_bad_size_is_an_error():
    with pytest.raises(ValueError):
        battery_price(0)


def test_price_range_follows_the_size_ratios():
    low, high = price_range_for(10, 5000)
    p = battery_price(10)
    assert low == pytest.approx(5000 * p["low"] / p["typical"])
    assert high == pytest.approx(5000 * p["high"] / p["typical"])


@pytest.mark.parametrize("price,where", [(3000, "below_range"), (6500, "within_range"), (9500, "above_range")])
def test_fair_price_says_where_a_quote_sits(price, where):
    f = fair_price(10, price)
    assert (f["low"], f["typical"], f["high"]) == (4500, 6500, 8900)
    assert f["your_price_is"] == where


def test_inverter_replacement_feeds_the_lifetime_model():
    assert INVERTER_REPLACEMENT_COST == inverter_replacement()["typical"]


def test_heat_pump_after_grant():
    hp = context_costs()["heat_pump_ashp"]
    assert hp["after_grant"]["typical"] == hp["typical"] - hp["grant"]
    assert all(v >= 0 for v in hp["after_grant"].values())


def test_standard_batteries_and_slider_for_the_classic_calculator():
    std = standard_batteries()
    assert [b["kwh"] for b in std] == [5.0, 7.5, 10.0, 13.5, 15.0, 20.0]
    assert all(set(b) == {"kwh", "cost", "label"} for b in std)
    sc = slider_costs()
    assert set(sc) >= set(range(3, 26)) | {7.5, 13.5}
    assert sc[10] == 6500


# ── API ───────────────────────────────────────────────────────────────────────

client = TestClient(app)


def test_batteries_endpoint_keeps_its_shape():
    j = client.get("/api/batteries").json()
    assert j["standard_sizes"] == standard_batteries()
    assert j["default_costs"]["10"] == 6500 and j["default_costs"]["7.5"] == 5500
    assert j["as_of"] == load_costs()["as_of"]


def test_estimate_without_a_price_uses_the_typical_price():
    j = client.post("/api/estimate", json={"annual_kwh": 3500, "battery_cap_kwh": 7.5}).json()
    assert j["selected"]["battery_cost_gbp"] == 5500
    assert j["fair_price"]["your_price_is"] == "within_range"


def test_estimate_returns_fair_price_and_context_costs():
    j = client.post("/api/estimate", json={"annual_kwh": 3500, "battery_cost_gbp": 9500}).json()
    assert j["fair_price"]["your_price_is"] == "above_range"
    assert set(j["context_costs"]) == {"solar_4kwp", "heat_pump_ashp", "ev_charger_7kw"}
    best = j["size_comparison"]["best_value"]
    assert best["fair_price"]["kwh"] == best["kwh"]


def test_lifetime_cost_range_comes_from_the_table():
    j = client.post("/api/estimate", json={"annual_kwh": 3500, "battery_cap_kwh": 10}).json()
    assert j["lifetime"]["installed_cost"] == {"low": 4500, "typical": 6500, "high": 8900}
