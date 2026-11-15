"""Task 1.7 — what would make a 'not yet' battery pay back."""
import pytest
from fastapi.testclient import TestClient

from engine.levers import max_price_for_payback, price_lever, verdict_change
from engine.lifetime import LifetimeAssumptions, lifetime_finance
from main import app

FLAT = LifetimeAssumptions(
    capacity_loss_per_year=0.0,
    price_growth={"low": 0.0, "central": 0.0, "high": 0.0},
    inverter_replacement_year=None,
)


# ── Price lever ───────────────────────────────────────────────────────────────

def test_price_hand_calculation():
    # £500 a year, no wear, no growth, no inverter: pays back in 10 years at £5,000.
    assert max_price_for_payback(500, 10, FLAT) == pytest.approx(5000)
    assert max_price_for_payback(500, 7, FLAT) == pytest.approx(3500)


def test_inverter_in_year_10_lowers_the_price():
    a = LifetimeAssumptions(capacity_loss_per_year=0.0, price_growth={"low": 0, "central": 0, "high": 0})
    # Year-10 cumulative = 10 × 500 − 1,000 inverter = 4,000.
    assert max_price_for_payback(500, 10, a) == pytest.approx(4000)


def test_price_is_exactly_the_break_even():
    for saving in (300, 450, 700):
        p = max_price_for_payback(saving, 10)
        assert lifetime_finance(p, saving).payback_years["likely"] <= 10 + 1e-6
        assert lifetime_finance(p + 50, saving).payback_years["likely"] is None \
            or lifetime_finance(p + 50, saving).payback_years["likely"] > 10


def test_worth_it_price_gives_worth_it():
    p = max_price_for_payback(600, 7)
    assert lifetime_finance(p, 600).verdict == "worth_it"


def test_no_positive_price_when_saving_is_too_small():
    assert max_price_for_payback(0, 10) is None
    assert max_price_for_payback(50, 10) is None     # £50 a year never covers the £1,000 inverter
    assert max_price_for_payback(-10, 10) is None


def test_price_lever_rounds_down():
    lever = price_lever(500, 6000, FLAT)
    assert lever == {"current_price": 6000, "price_for_payback_within_warranty": 5000,
                     "price_for_worth_it": 3500}


# ── Verdict change ────────────────────────────────────────────────────────────

def test_verdict_change_only_counts_improvements():
    better = verdict_change(1200, 6000, "not_yet")
    assert better["verdict"] == "worth_it" and better["changes_verdict"] is True
    same = verdict_change(300, 6000, "not_yet")
    assert same["verdict"] == "not_yet" and same["changes_verdict"] is False


# ── API ───────────────────────────────────────────────────────────────────────

client = TestClient(app)
BODY = {"annual_kwh": 3500, "property_type": "semi"}


def test_levers_only_when_not_yet():
    good = client.post("/api/estimate", json={**BODY, "tariff_key": "edfFreePhaseDynamic"}).json()
    assert good["lifetime"]["verdict"] != "not_yet"
    assert good["what_would_make_it_pay_back"] is None


def test_not_yet_battery_gets_all_three_levers():
    j = client.post("/api/estimate", json={**BODY, "tariff_key": "octopusGo"}).json()
    assert j["lifetime"]["verdict"] == "not_yet"
    lv = j["what_would_make_it_pay_back"]
    p = lv["price"]
    assert p["current_price"] == 6000
    assert p["price_for_worth_it"] < p["price_for_payback_within_warranty"] < 6000
    # Lowering the price to the quoted figure does change the verdict.
    at_price = client.post("/api/estimate", json={
        **BODY, "tariff_key": "octopusGo", "battery_cost_gbp": p["price_for_payback_within_warranty"]}).json()
    assert at_price["lifetime"]["verdict"] in ("borderline", "worth_it")
    # The best tariff for a 10 kWh battery here is FreePhase Dynamic, which is borderline.
    sw = lv["switch_tariff"]
    assert sw["tariff_key"] == "edfFreePhaseDynamic" and sw["changes_verdict"] is True
    ev = lv["add_ev"]
    assert ev["annual_miles"] == 7000 and ev["verdict"] in ("not_yet", "borderline", "worth_it")


def test_no_ev_lever_when_an_ev_is_already_included():
    j = client.post("/api/estimate", json={
        **BODY, "tariff_key": "octopusGo", "ev": {"status": "planning", "annual_miles": 10000}}).json()
    assert j["lifetime"]["verdict"] == "not_yet"
    assert j["what_would_make_it_pay_back"]["add_ev"] is None
