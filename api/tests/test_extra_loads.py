"""Task 1.2 — EV and heat pump loads."""
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from engine.extra_loads import (
    HP_DAILY, EVSettings, HeatPumpSettings, apply_extra_loads, ev_day, ev_window_slots, hp_days,
)
from engine.profile_estimator import generate_days, model_year_dates
from main import app

DATES = model_year_dates()


def total(days):
    return sum(map(sum, days))


def month_daily(days, month):
    sel = [sum(d) for d, x in zip(days, DATES) if x.month == month]
    return sum(sel) / len(sel)


# ── EV ────────────────────────────────────────────────────────────────────────

def test_ev_miles_to_kwh():
    assert EVSettings(annual_miles=10000).annual_kwh == pytest.approx(3000)


def test_ev_charges_only_in_its_window():
    day = ev_day(EVSettings(annual_miles=10000))
    window = set(ev_window_slots("00:30", "04:30"))
    assert window == set(range(1, 9))
    assert all(v == 0 for i, v in enumerate(day) if i not in window)
    assert sum(day) == pytest.approx(3000 / 365)


def test_ev_window_can_wrap_midnight():
    assert ev_window_slots("23:30", "01:00") == [47, 0, 1]


def test_ev_window_too_short_is_an_error():
    with pytest.raises(ValueError):
        ev_day(EVSettings(annual_miles=40000, charge_start="02:00", charge_end="02:30"))


def test_ev_planning_adds_on_top():
    base = generate_days(3500, "semi")
    res = apply_extra_loads(base, DATES, EVSettings(status="planning", annual_miles=10000), route="estimate")
    assert total(res.days) == pytest.approx(3500 + 3000)
    assert res.ev_kwh_added == pytest.approx(3000)


def test_ev_have_on_estimate_moves_kwh_overnight_keeping_the_total():
    base = generate_days(5000, "semi")
    res = apply_extra_loads(base, DATES, EVSettings(status="have", annual_miles=7000), route="estimate")
    assert total(res.days) == pytest.approx(5000)
    assert res.ev_kwh_reshaped == pytest.approx(2100)
    overnight = sum(d[i] for d in res.days for i in range(1, 9))
    overnight_before = sum(d[i] for d in base for i in range(1, 9))
    # The household share shrinks to (5000 − 2100) / 5000; the EV's 2,100 kWh all lands overnight.
    assert overnight == pytest.approx(overnight_before * 2900 / 5000 + 2100)


def test_have_on_upload_changes_nothing():
    base = generate_days(3500, "semi")
    res = apply_extra_loads(base, DATES, EVSettings(status="have"), HeatPumpSettings(status="have"), route="upload")
    assert res.days == base
    assert res.ev_kwh_added == res.hp_kwh_added == 0


def test_have_never_strips_more_than_the_household_can_hold():
    base = generate_days(2000, "flat")
    res = apply_extra_loads(base, DATES, EVSettings(status="have", annual_miles=20000), route="estimate")
    assert total(res.days) == pytest.approx(2000)
    assert all(v >= 0 for d in res.days for v in d)
    assert res.ev_kwh_reshaped == pytest.approx(2000 * 0.7)


# ── Heat pump ─────────────────────────────────────────────────────────────────

def test_heat_pump_electricity_is_heat_over_efficiency():
    hp = HeatPumpSettings(status="planning", heat_demand_kwh=9000, efficiency=3.0)
    assert hp.annual_kwh() == pytest.approx(3000)


def test_heat_demand_from_floor_area_and_epc_rating():
    assert HeatPumpSettings(floor_area_m2=100, epc_rating="d").heat_demand() == 12000
    assert HeatPumpSettings(floor_area_m2=100, epc_rating="B").heat_demand() == 6500
    assert HeatPumpSettings().heat_demand("detached") == 130 * 120   # defaults when nothing known


def test_heat_pump_year_totals_and_is_winter_heavy():
    hp = HeatPumpSettings(status="planning", heat_demand_kwh=9000)
    days = hp_days(hp, DATES, 365, "semi")
    assert total(days) == pytest.approx(3000)
    assert month_daily(days, 1) > 4 * month_daily(days, 7)


def test_heat_pump_daily_shape_morning_and_evening():
    morning, midday, evening = HP_DAILY[14], HP_DAILY[24], HP_DAILY[38]
    assert morning > midday and evening > midday
    assert min(HP_DAILY) > 0, "runs a little all day"


def test_heat_pump_planning_adds_winter_load():
    base = generate_days(3500, "semi")
    hp = HeatPumpSettings(status="planning", heat_demand_kwh=9000)
    res = apply_extra_loads(base, DATES, None, hp, route="estimate")
    assert total(res.days) == pytest.approx(6500)
    added_jan = month_daily(res.days, 1) - month_daily(base, 1)
    added_jul = month_daily(res.days, 7) - month_daily(base, 7)
    assert added_jan > 4 * added_jul > 0


def test_heat_pump_on_undated_data_spreads_evenly():
    hp = HeatPumpSettings(status="planning", heat_demand_kwh=3650, efficiency=1.5 * 2)
    days = hp_days(hp, None, 10, "semi")
    assert all(sum(d) == pytest.approx(3650 / 3 / 365) for d in days)


def test_part_year_dates_scale_to_their_share():
    nov_dec = [d for d in DATES if d.month >= 11]
    hp = HeatPumpSettings(status="planning", heat_demand_kwh=9000)
    days = hp_days(hp, nov_dec, len(nov_dec), "semi")
    # A 61-day run is scaled as if annualised: run total × 365/61 = the annual figure.
    assert total(days) * 365 / 61 == pytest.approx(3000)


# ── API ───────────────────────────────────────────────────────────────────────

client = TestClient(app)


def test_estimate_with_planned_ev_and_heat_pump():
    body = {"annual_kwh": 3500, "property_type": "semi"}
    base = client.post("/api/estimate", json=body).json()
    r = client.post("/api/estimate", json={
        **body,
        "ev": {"status": "planning", "annual_miles": 10000},
        "heat_pump": {"status": "planning", "floor_area_m2": 90, "epc_rating": "D"},
    })
    assert r.status_code == 200, r.text
    s = r.json()["summary"]
    assert s["extra_loads"]["ev_kwh_added"] == pytest.approx(3000, abs=1)
    assert s["extra_loads"]["heat_pump_kwh_added"] == pytest.approx(90 * 120 / 3, abs=1)
    assert s["annual_kwh_estimate"] == pytest.approx(3500 + 3000 + 3600, abs=2)
    assert r.json()["session_id"] != base["session_id"]
    assert base["summary"]["extra_loads"] is None


def test_estimate_rejects_bad_load_settings():
    for bad in ({"ev": {"status": "maybe"}}, {"ev": {"status": "planning", "charge_start": "25:00"}},
                {"heat_pump": {"status": "planning", "epc_rating": "Z"}}):
        r = client.post("/api/estimate", json={"annual_kwh": 3500, **bad})
        assert r.status_code == 422, bad


def test_compare_accepts_loads():
    r = client.post("/api/compare", json={"annual_kwh": 3500, "ev": {"status": "planning"}})
    assert r.status_code == 200, r.text
    assert r.json()["full_result"]["summary"]["extra_loads"]["ev_kwh_added"] == pytest.approx(2100, abs=1)


def test_upload_with_planned_ev():
    from tests.test_full_year import octopus_csv
    raw = octopus_csv("2025-01-01", "2026-01-01")
    r = client.post(
        "/api/analyse",
        files=[("files", ("usage.csv", raw, "text/csv"))],
        data={"ev": json.dumps({"status": "planning", "annual_miles": 10000})},
    )
    assert r.status_code == 200, r.text
    s = r.json()["summary"]
    assert s["extra_loads"]["ev_kwh_added"] == pytest.approx(3000, abs=1)


def test_upload_rejects_bad_json():
    from tests.test_full_year import octopus_csv
    raw = octopus_csv("2025-01-01", "2025-02-01")
    r = client.post("/api/analyse", files=[("files", ("u.csv", raw, "text/csv"))], data={"ev": "{not json"})
    assert r.status_code == 422
