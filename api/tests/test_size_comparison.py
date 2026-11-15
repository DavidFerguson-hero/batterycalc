"""Task 1.6 — best-value battery size (highest lifetime net gain) and its neighbours."""
import pytest
from fastapi.testclient import TestClient

from engine.lifetime import lifetime_finance
from engine.size_comparison import SizeOption, compare_sizes, options_from_matrix
from engine.tariffs import OPT_BATTERIES
from main import app

BASE = 1500.0   # £/yr on the best tariff without a battery


def opt(kwh, cost, annual_cost, tariff="octopusGo"):
    return SizeOption(kwh, f"{kwh} kWh", cost, tariff, tariff, annual_cost)


def test_best_value_is_highest_net_gain_not_biggest_saving():
    # The 20 kWh battery saves the most each year but costs far more.
    options = [
        opt(5, 3500, BASE - 450),
        opt(10, 6000, BASE - 700),
        opt(20, 11000, BASE - 820),
    ]
    r = compare_sizes(options, BASE)
    gains = {row["kwh"]: row["lifetime_net_gain"] for row in r["all_sizes"]}
    assert r["best_value"]["kwh"] == max(gains, key=gains.get)
    assert r["biggest_saving_kwh"] == 20
    assert r["best_value"]["kwh"] != 20


def test_rows_use_the_lifetime_model():
    r = compare_sizes([opt(10, 6000, BASE - 700)], BASE)
    row = r["best_value"]
    lt = lifetime_finance(6000, 700)
    assert row["year1_battery_saving"] == pytest.approx(700)
    assert row["lifetime_net_gain"] == round(lt.lifetime_net_gain["likely"])
    assert row["verdict"] == lt.verdict


def test_neighbours_either_side():
    options = [opt(k, 600 * k, BASE - 60 * k + (k - 10) ** 2) for k in (5, 7.5, 10, 13.5, 15)]
    r = compare_sizes(options, BASE)
    sizes = [row["kwh"] for row in r["all_sizes"]]
    i = sizes.index(r["best_value"]["kwh"])
    assert (r["smaller"] or {}).get("kwh") == (sizes[i - 1] if i > 0 else None)
    assert (r["larger"] or {}).get("kwh") == (sizes[i + 1] if i + 1 < len(sizes) else None)


def test_smallest_best_has_no_smaller_neighbour():
    r = compare_sizes([opt(5, 2000, BASE - 500), opt(10, 9000, BASE - 600)], BASE)
    assert r["best_value"]["kwh"] == 5
    assert r["smaller"] is None and r["larger"]["kwh"] == 10


def test_largest_best_has_no_larger_neighbour():
    r = compare_sizes([opt(5, 4000, BASE - 200), opt(10, 5000, BASE - 900)], BASE)
    assert r["best_value"]["kwh"] == 10
    assert r["larger"] is None and r["smaller"]["kwh"] == 5


def test_tie_prefers_the_smaller_battery():
    r = compare_sizes([opt(10, 6000, BASE - 700), opt(5, 6000, BASE - 700)], BASE)
    assert r["best_value"]["kwh"] == 5


def test_when_nothing_pays_back_the_least_bad_is_shown_with_its_verdict():
    r = compare_sizes([opt(5, 5000, BASE - 100), opt(10, 9000, BASE - 150)], BASE)
    assert r["best_value"]["kwh"] == 5
    assert r["best_value"]["verdict"] == "not_yet" and r["best_value"]["lifetime_net_gain"] < 0


def test_empty_is_an_error():
    with pytest.raises(ValueError):
        compare_sizes([], BASE)


def test_options_from_matrix_takes_cheapest_tariff_per_size():
    matrix = {
        "a": [{"battery_kwh": 5, "battery_label": "5 kWh", "battery_cost": 3500, "ann_cost_with_battery": 900}],
        "b": [{"battery_kwh": 5, "battery_label": "5 kWh", "battery_cost": 3500, "ann_cost_with_battery": 850}],
    }
    opts = options_from_matrix(matrix, {"a": "A", "b": "B"})
    assert len(opts) == 1 and opts[0].tariff_key == "b" and opts[0].tariff_name == "B"


def test_flat_current_tariff_can_win_when_it_is_cheapest():
    matrix = {"a": [{"battery_kwh": 5, "battery_label": "5 kWh", "battery_cost": 3500, "ann_cost_with_battery": 900}]}
    current = {"key": "current", "name": "Your current tariff", "annual_cost_with_battery": 800}
    opts = options_from_matrix(matrix, {"a": "A"}, current)
    assert opts[0].tariff_key == "current" and opts[0].installed_cost == 3500


# ── API ───────────────────────────────────────────────────────────────────────

def test_estimate_returns_size_comparison():
    r = TestClient(app).post("/api/estimate", json={"annual_kwh": 3500, "property_type": "semi"})
    assert r.status_code == 200, r.text
    sc = r.json()["size_comparison"]
    assert [row["kwh"] for row in sc["all_sizes"]] == sorted(b["kwh"] for b in OPT_BATTERIES)
    best = sc["best_value"]
    assert best["lifetime_net_gain"] == max(row["lifetime_net_gain"] for row in sc["all_sizes"])
    # Each size's saving is measured against the best tariff without a battery.
    bnb = r.json()["tariff_check"]["best_no_battery"]["annual_cost"]
    assert all(row["year1_battery_saving"] <= bnb for row in sc["all_sizes"])


def test_user_price_applies_to_their_size():
    r = TestClient(app).post("/api/estimate", json={
        "annual_kwh": 3500, "battery_cap_kwh": 10, "battery_cost_gbp": 4000})
    rows = {row["kwh"]: row for row in r.json()["size_comparison"]["all_sizes"]}
    assert rows[10.0]["installed_cost"] == 4000
