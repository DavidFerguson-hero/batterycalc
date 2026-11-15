"""Task 1.3 — lifetime finance with ranges, payback and verdict."""
import pytest
from fastapi.testclient import TestClient

from engine.lifetime import (
    LifetimeAssumptions, cash_by_year, lifetime_finance, payback_from_cash, verdict_for,
)
from main import app

NO_WEAR_NO_GROWTH = LifetimeAssumptions(
    capacity_loss_per_year=0.0,
    price_growth={"low": 0.0, "central": 0.0, "high": 0.0},
    inverter_replacement_year=None,
)


# ── Cash series ───────────────────────────────────────────────────────────────

def test_series_runs_from_install_to_end_of_life():
    cash = cash_by_year(6000, 800, 0.03, LifetimeAssumptions())
    assert len(cash) == 16 and cash[0] == -6000


def test_simple_case_matches_hand_calculation():
    r = lifetime_finance(5000, 1000, assumptions=NO_WEAR_NO_GROWTH)
    assert r.cases["likely"].cash_by_year[:6] == [-5000, -4000, -3000, -2000, -1000, 0]
    assert r.payback_years["likely"] == pytest.approx(5.0)
    assert r.lifetime_net_gain["likely"] == pytest.approx(15 * 1000 - 5000)


def test_capacity_loss_and_price_growth_compound():
    a = LifetimeAssumptions(inverter_replacement_year=None)
    cash = cash_by_year(0, 1000, 0.03, a)
    year5 = cash[5] - cash[4]
    assert year5 == pytest.approx(1000 * 0.98 ** 4 * 1.03 ** 4)


def test_payback_interpolates_within_a_year():
    assert payback_from_cash([-1000, -400, 200]) == pytest.approx(1 + 400 / 600)


# ── Required cases (plan: never pays back, inverter dip, verdict boundaries) ──

def test_never_pays_back():
    r = lifetime_finance(9000, 300)
    assert r.payback_years == {"low": None, "likely": None, "high": None}
    assert r.verdict == "not_yet"
    assert r.lifetime_net_gain["likely"] < 0


def test_zero_or_negative_saving_never_pays_back():
    for saving in (0, -50):
        r = lifetime_finance(6000, saving)
        assert r.payback_years["likely"] is None and r.verdict == "not_yet"


def test_mid_life_inverter_dip():
    a = LifetimeAssumptions(
        capacity_loss_per_year=0.0,
        price_growth={"low": 0.0, "central": 0.0, "high": 0.0},
        inverter_replacement_cost=1500,
    )
    cash = cash_by_year(4500, 500, 0.0, a)
    # Breaks even at the end of year 9, the inverter in year 10 pushes it back below zero...
    assert cash[9] == pytest.approx(0) and cash[10] == pytest.approx(-1000)
    assert cash[10] < cash[9], "the year-10 inverter replacement shows as a dip"
    # ...so it only pays back for good during year 12.
    assert payback_from_cash(cash) == pytest.approx(12.0)


def test_inverter_cost_lands_in_its_year_only():
    a = LifetimeAssumptions(capacity_loss_per_year=0.0, price_growth={"low": 0, "central": 0, "high": 0})
    cash = cash_by_year(0, 800, 0.0, a)
    steps = [b - a_ for a_, b in zip(cash, cash[1:])]
    assert steps[9] == pytest.approx(800 - 1000)
    assert all(s == pytest.approx(800) for i, s in enumerate(steps) if i != 9)


@pytest.mark.parametrize("payback,expected", [
    (5.0, "worth_it"),
    (7.0, "worth_it"),      # exactly 70% of a 10-year warranty
    (7.01, "borderline"),
    (10.0, "borderline"),   # exactly 100%
    (10.01, "not_yet"),
    (None, "not_yet"),
])
def test_verdict_boundaries(payback, expected):
    assert verdict_for(payback, 10) == expected


def test_verdict_uses_the_likely_case():
    # Typical £7,000 at £1,000/yr with no wear or growth: likely payback 7.0 → worth it,
    # even though the pessimistic case (higher cost) is longer.
    r = lifetime_finance(7000, 1000, assumptions=NO_WEAR_NO_GROWTH)
    assert r.payback_years["likely"] == pytest.approx(7.0)
    assert r.payback_years["high"] > 7.0
    assert r.verdict == "worth_it"


# ── Ranges ────────────────────────────────────────────────────────────────────

def test_ranges_are_ordered():
    r = lifetime_finance(6000, 700)
    p = r.payback_years
    assert p["low"] < p["likely"] < p["high"]
    g = r.lifetime_net_gain
    assert g["low"] < g["likely"] < g["high"]


def test_explicit_cost_range_is_used():
    r = lifetime_finance(6000, 700, cost_low=5000, cost_high=8000)
    d = r.to_dict()["installed_cost"]
    assert d == {"low": 5000, "typical": 6000, "high": 8000}


def test_to_dict_is_json_ready():
    d = lifetime_finance(6000, 700).to_dict()
    assert d["verdict"] in ("worth_it", "borderline", "not_yet")
    assert set(d["cash_by_year"]) == {"optimistic", "likely", "pessimistic"}
    assert all(len(v) == 16 for v in d["cash_by_year"].values())
    assert d["assumptions"]["price_growth_pct"]["central"] == pytest.approx(3.0)


# ── API ───────────────────────────────────────────────────────────────────────

def test_estimate_returns_lifetime_block():
    r = TestClient(app).post("/api/estimate", json={"annual_kwh": 3500, "property_type": "semi"})
    assert r.status_code == 200, r.text
    j = r.json()
    lt = j["lifetime"]
    f = j["financials"]
    # Since task 1.5: credited only beyond the best tariff available without a battery.
    expected = j["tariff_check"]["best_no_battery"]["annual_cost"] - f["ann_cost_with_battery"]
    assert lt["year1_battery_saving"] == pytest.approx(expected, abs=0.02)
    assert lt["verdict"] in ("worth_it", "borderline", "not_yet")
    assert lt["installed_cost"]["typical"] == 6000
