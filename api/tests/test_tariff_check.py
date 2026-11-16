"""Task 1.5 — the four-case tariff check and the "switch tariff first" flag."""
import pytest
from fastapi.testclient import TestClient

from engine.extra_loads import EVSettings, apply_extra_loads
from engine.profile_estimator import generate_days, model_year_dates
from engine.tariff_check import current_tariff, tariff_check
from main import app

DAYS = generate_days(3500, "semi")
def with_ev(miles):
    return apply_extra_loads(
        DAYS, model_year_dates(), EVSettings(status="planning", annual_miles=miles), route="estimate"
    ).days


EV_DAYS = with_ev(10000)
HIGH_MILEAGE_DAYS = with_ev(20000)


def check(days=DAYS, **kw):
    args = dict(unit_rate=0.2816, standing_pd=53.0, cap_kwh=10, max_rate_kw=3.6, efficiency=0.9)
    args.update(kw)
    return tariff_check(days, **args)


def test_always_four_cases():
    t = check()
    a = t["current"]["annual_cost_no_battery"]
    b = t["best_no_battery"]["annual_cost"]
    c = t["current"]["annual_cost_with_battery"]
    d = t["best_with_battery"]["annual_cost"]
    assert all(isinstance(x, float) for x in (a, b, c, d))
    s = t["savings"]
    assert s["switch_tariff_only"] == pytest.approx(a - b, abs=0.01)
    assert s["battery_on_current_tariff"] == pytest.approx(a - c, abs=0.01)
    assert s["best_tariff_and_battery"] == pytest.approx(a - d, abs=0.01)
    assert t["battery_adds"] == pytest.approx(b - d, abs=0.01)


def test_best_is_never_worse_than_staying():
    t = check()
    a = t["current"]["annual_cost_no_battery"]
    assert t["best_no_battery"]["annual_cost"] <= a
    assert t["best_with_battery"]["annual_cost"] <= t["current"]["annual_cost_with_battery"]
    assert t["savings"]["switch_tariff_only"] >= 0


def test_flat_current_tariff_battery_does_nothing():
    t = check()
    assert t["current"]["annual_cost_with_battery"] == pytest.approx(t["current"]["annual_cost_no_battery"])
    assert t["savings"]["battery_on_current_tariff"] == pytest.approx(0)


def test_current_cost_uses_the_households_own_price():
    t = check(unit_rate=0.25, standing_pd=50)
    assert t["current"]["annual_cost_no_battery"] == pytest.approx(3500 * 0.25 + 0.50 * 365, abs=0.5)


def test_standalone_battery_is_not_flagged_switch_first():
    """H20: a typical home with no EV — the tariff alone saves little; the battery does the work."""
    t = check()
    assert t["switch_first"] is False
    assert t["switch_share_of_best"] < 0.7
    assert t["battery_adds"] > 0


def test_an_ev_shifts_the_saving_towards_the_tariff():
    """H18: an EV makes the tariff switch a much bigger part of the saving.
    (Since the measured daily shape (task 3.1), more of a home's use is overnight, so switching
    already counts for about a fifth of the saving without an EV; an EV roughly triples that.)"""
    assert check(EV_DAYS)["switch_share_of_best"] > 2.5 * check()["switch_share_of_best"]
    assert check(EV_DAYS)["savings"]["switch_tariff_only"] > 500


def test_high_mileage_ev_owner_is_told_to_switch_first():
    """H18: at 20,000 miles with a 5 kWh battery, switching alone is most of the saving."""
    t = check(HIGH_MILEAGE_DAYS, cap_kwh=5)
    assert t["switch_first"] is True
    assert t["switch_share_of_best"] >= 0.7


def test_flag_follows_the_70_percent_rule():
    for days in (DAYS, EV_DAYS, HIGH_MILEAGE_DAYS):
        for cap in (5, 10):
            t = check(days, cap_kwh=cap)
            assert t["switch_first"] == (t["switch_share_of_best"] >= 0.7)


def test_already_on_a_time_of_use_tariff():
    t = check(current_tariff_key="octopusGo")
    assert t["current"]["key"] == "octopusGo"
    assert t["savings"]["battery_on_current_tariff"] > 0
    assert sum(1 for r in t["by_tariff"] if r["key"] == "octopusGo") == 1


def test_unknown_current_tariff_is_an_error():
    with pytest.raises(ValueError):
        current_tariff("noSuchTariff", 0.28, 53)


def test_by_tariff_lists_every_option_sorted():
    t = check()
    rows = t["by_tariff"]
    assert len(rows) == 11   # staying put + 10 time-of-use tariffs
    costs = [r["annual_cost_with_battery"] for r in rows]
    assert costs == sorted(costs)
    assert rows[0]["key"] == t["best_with_battery"]["key"]


def test_zero_best_saving_has_no_share():
    t = check(unit_rate=0.05)   # a very cheap flat rate beats every time-of-use tariff
    assert t["best_no_battery"]["key"] == "current"
    if t["savings"]["best_tariff_and_battery"] <= 0:
        assert t["switch_share_of_best"] is None and t["switch_first"] is False


# ── API ───────────────────────────────────────────────────────────────────────

client = TestClient(app)


def test_estimate_includes_tariff_check():
    r = client.post("/api/estimate", json={"annual_kwh": 3500, "property_type": "semi"})
    assert r.status_code == 200, r.text
    j = r.json()
    t = j["tariff_check"]
    assert t["switch_first"] is False
    assert j["lifetime"]["year1_battery_saving"] == pytest.approx(
        t["best_no_battery"]["annual_cost"] - j["financials"]["ann_cost_with_battery"], abs=0.02)


def test_estimate_with_high_mileage_ev_flags_switch_first_and_credits_battery_less():
    body = {"annual_kwh": 3500, "property_type": "semi", "battery_cap_kwh": 5, "battery_cost_gbp": 3500,
            "tariff_key": "edfFreePhaseDynamic", "ev": {"status": "planning", "annual_miles": 20000}}
    ev = client.post("/api/estimate", json=body).json()
    assert ev["tariff_check"]["switch_first"] is True
    # The EV tariff saving belongs to the switch, not the battery.
    assert ev["lifetime"]["year1_battery_saving"] < ev["financials"]["total_saving"] / 2


def test_current_tariff_key_on_api():
    r = client.post("/api/estimate", json={"annual_kwh": 3500, "current_tariff_key": "octopusCosy"})
    assert r.status_code == 200
    assert r.json()["tariff_check"]["current"]["key"] == "octopusCosy"
    r = client.post("/api/estimate", json={"annual_kwh": 3500, "current_tariff_key": "nope"})
    assert r.status_code == 400
