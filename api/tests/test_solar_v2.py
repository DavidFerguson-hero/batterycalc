"""Story H17 — solar panels in POST /api/v2/assess, and the generation model behind it."""
import json
from datetime import date, timedelta
from pathlib import Path

import jsonschema
import pytest
from fastapi.testclient import TestClient

from engine.simulator import run_simulation, simulate_day_full
from engine.solar_profile import annual_generation_kwh, generation_days, monthly_profiles
from engine.tariffs import TARIFFS
from main import app
from scripts.export_v2_schema import OUT as SCHEMA_FILE
from tests.test_full_year import octopus_csv

client = TestClient(app)
URL = "/api/v2/assess"
EST = {"usage": {"route": "estimate", "annual_kwh": 3500, "property_type": "semi"}}
# A fixed battery and tariff keep the comparisons like for like.
BATT = {"size_kwh": 5, "price_gbp": 4000, "tariff_key": "octopusGo"}


def assess(body):
    r = client.post(URL, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def upload(inputs, files):
    r = client.post(URL, data={"inputs": json.dumps(inputs)},
                    files=[("files", (f"u{i}.csv", f, "text/csv")) for i, f in enumerate(files)])
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def response_schema():
    return json.loads(Path(SCHEMA_FILE).read_text())["response"]


# ── Generation model ──────────────────────────────────────────────────────────

def test_a_year_of_generation_matches_the_annual_figure():
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(365)]
    gen = generation_days(365, dates, 4.0)
    assert sum(map(sum, gen)) == pytest.approx(annual_generation_kwh(4.0), rel=0.001)
    assert annual_generation_kwh(4.0) == pytest.approx(3400)


def test_generation_is_daytime_and_higher_in_summer():
    jan, jun = monthly_profiles(4.0)[0], monthly_profiles(4.0)[5]
    assert sum(jun) > 3 * sum(jan)
    assert jan[0] == jan[47] == 0 and jun[2] == 0          # nothing at night
    assert max(range(48), key=lambda i: jun[i]) in range(24, 30)   # peaks around 1pm


def test_east_peaks_earlier_and_makes_less_than_south():
    south, east = monthly_profiles(4.0)[5], monthly_profiles(4.0, "east")[5]
    assert sum(east) < sum(south)
    assert max(range(48), key=lambda i: east[i]) < max(range(48), key=lambda i: south[i])


def test_without_dates_every_day_is_the_average_day():
    gen = generation_days(10, None, 4.0)
    assert len(gen) == 10 and sum(gen[0]) * 365 == pytest.approx(annual_generation_kwh(4.0), rel=0.001)


# ── Simulator with spare solar ────────────────────────────────────────────────

def _solar_day():
    """0.3 kWh each half hour, with 1 kWh of spare solar in each of the eight midday half hours."""
    return [-1.0 if 20 <= i < 28 else 0.3 for i in range(48)]


def test_spare_solar_is_exported_without_a_battery():
    sim = run_simulation(TARIFFS["octopusGo"], 5, 3.6, 0.9, [_solar_day()], export_rate=0.15)
    flat = run_simulation(TARIFFS["octopusGo"], 5, 3.6, 0.9, [[0.3 if d > 0 else 0 for d in _solar_day()]])
    assert flat.ann_cost_no_battery - sim.ann_cost_no_battery == pytest.approx(8 * 0.15 * 365, rel=0.001)


def test_spare_solar_charges_the_battery_and_is_used_later():
    day = simulate_day_full(_solar_day(), TARIFFS["currentFlat"], 5, 3.6, 0.9, export_rate=0.0)
    # A flat rate has no cheap hours, so without solar the battery would do nothing.
    assert day.cost_with_battery < day.cost_no_battery
    assert day.solar_storage_value > 0


def test_grid_charging_leaves_room_for_the_solar():
    day = simulate_day_full(_solar_day(), TARIFFS["octopusGo"], 5, 3.6, 0.9, export_rate=0.15)
    before_sun = day.soc_profile[19]
    assert before_sun <= 5 - 3.5   # about 7.2 kWh of spare solar is coming, so not filled overnight


def test_breakdown_adds_up_with_solar():
    sim = run_simulation(TARIFFS["octopusGo"], 5, 3.6, 0.9, [_solar_day()] * 3, export_rate=0.15)
    b = sim.saving_breakdown()
    assert b["solar_storage"] > 0
    assert b["time_shifting"] + b["solar_storage"] + b["other"] == pytest.approx(b["total"], abs=0.02)


def test_no_solar_gives_the_same_result_as_before():
    """Days with no spare solar take the battery-only path unchanged."""
    days = [[0.2] * 14 + [0.4] * 34] * 5
    a = run_simulation(TARIFFS["octopusGo"], 5, 3.6, 0.9, days, export_rate=0.15)
    assert a.ann_solar_storage == 0
    assert a.saving_breakdown()["solar_storage"] == 0


# ── Estimate route ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def estimate_by_status():
    return {s: assess({**EST, "battery": BATT, "tariff": {"export_rate_p": 15},
                       "solar": {"status": s, "kwp": 4}})
            for s in ("none", "have", "planning")}


def test_estimate_none_has_no_solar(estimate_by_status):
    r = estimate_by_status["none"]
    assert r["usage"]["solar"] is None
    assert r["saving_breakdown"]["solar_storage"] == 0
    assert r["day_in_life"]["average"]["solar_generation"] is None


@pytest.mark.parametrize("status", ["have", "planning"])
def test_estimate_models_solar_for_have_and_planning(estimate_by_status, status):
    r, none = estimate_by_status[status], estimate_by_status["none"]
    s = r["usage"]["solar"]
    assert s["status"] == status and s["modelled"] is True
    assert s["annual_generation_kwh"] == 3400
    assert s["used_at_home_kwh"] + s["spare_kwh"] == pytest.approx(3400, abs=2)
    assert r["saving_breakdown"]["solar_storage"] > 0
    # The bill falls, and the home's own use is still reported before solar.
    assert r["tariff_check"]["current"]["annual_cost_no_battery"] < \
        none["tariff_check"]["current"]["annual_cost_no_battery"]
    assert r["usage"]["annual_kwh"] == none["usage"]["annual_kwh"]
    assert sum(r["day_in_life"]["summer"]["solar_generation"]) > 0


def test_estimate_have_and_planning_give_the_same_answer(estimate_by_status):
    assert estimate_by_status["have"]["saving_breakdown"] == estimate_by_status["planning"]["saving_breakdown"]


def test_bigger_panels_store_more_solar():
    small = assess({**EST, "battery": BATT, "solar": {"status": "planning", "kwp": 2}})
    big = assess({**EST, "battery": BATT, "solar": {"status": "planning", "kwp": 6}})
    assert big["saving_breakdown"]["solar_storage"] > small["saving_breakdown"]["solar_storage"]


@pytest.mark.parametrize("status", ["have", "planning"])
def test_estimate_solar_validates_against_the_schema(status, response_schema):
    jsonschema.validate(assess({**EST, "solar": {"status": status}}), response_schema)


# ── Upload route ──────────────────────────────────────────────────────────────

CSV = octopus_csv("2025-03-01", "2025-09-01")


@pytest.fixture(scope="module")
def upload_by_status():
    return {s: upload({"usage": {"route": "upload"}, "battery": BATT, "tariff": {"export_rate_p": 15},
                       "solar": {"status": s}}, [CSV])
            for s in ("none", "have", "planning")}


def test_upload_none_has_no_solar(upload_by_status):
    assert upload_by_status["none"]["usage"]["solar"] is None
    assert upload_by_status["none"]["saving_breakdown"]["solar_storage"] == 0


def test_upload_have_leaves_the_meter_readings_alone(upload_by_status):
    r, none = upload_by_status["have"], upload_by_status["none"]
    s = r["usage"]["solar"]
    assert s["status"] == "have" and s["modelled"] is False
    assert s["used_at_home_kwh"] is None and s["spare_kwh"] is None
    assert r["saving_breakdown"] == none["saving_breakdown"]
    assert r["tariff_check"] == none["tariff_check"]


def test_upload_planning_takes_solar_off_the_readings(upload_by_status, response_schema):
    r, none = upload_by_status["planning"], upload_by_status["none"]
    assert r["usage"]["solar"]["modelled"] is True
    assert r["saving_breakdown"]["solar_storage"] > 0
    assert r["tariff_check"]["current"]["annual_cost_no_battery"] < \
        none["tariff_check"]["current"]["annual_cost_no_battery"]
    jsonschema.validate(r, response_schema)


# ── Validation ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("solar", [
    {"status": "maybe"}, {"status": "have", "kwp": 0}, {"status": "have", "kwp": 50},
    {"status": "have", "orientation": "north"}, {"status": "have", "postcode": "SW1A 1AA"},
])
def test_bad_solar_inputs_are_422(solar):
    assert client.post(URL, json={**EST, "solar": solar}).status_code == 422
