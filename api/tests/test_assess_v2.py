"""Task 1.9 — POST /api/v2/assess: contract test against the published schema, plus behaviour."""
import json
from pathlib import Path

import jsonschema
import pytest
from fastapi.testclient import TestClient

from main import app
from routers import analyse
from scripts.export_v2_schema import OUT as SCHEMA_FILE, build
from tests.test_full_year import octopus_csv

client = TestClient(app)
URL = "/api/v2/assess"
EST = {"usage": {"route": "estimate", "annual_kwh": 3500, "property_type": "semi"}}


def assess(body=EST, **kw):
    return client.post(URL, json=body, **kw)


def upload(inputs, files):
    return client.post(URL, data={"inputs": json.dumps(inputs)},
                       files=[("files", (f"u{i}.csv", f, "text/csv")) for i, f in enumerate(files)])


# ── Contract ──────────────────────────────────────────────────────────────────

def test_published_schema_matches_the_models():
    """docs/api-v2.schema.json must be regenerated whenever models/assess.py changes."""
    assert json.loads(Path(SCHEMA_FILE).read_text()) == json.loads(json.dumps(build(), sort_keys=True)), \
        "Run: cd api && python scripts/export_v2_schema.py"


@pytest.fixture(scope="module")
def response_schema():
    return json.loads(Path(SCHEMA_FILE).read_text())["response"]


SAMPLES = {
    "estimate, best value": EST,
    "estimate, chosen battery": {**EST, "battery": {"size_kwh": 5, "price_gbp": 3000, "tariff_key": "octopusCosy"}},
    "estimate, EV + heat pump": {**EST, "ev": {"status": "planning", "annual_miles": 10000},
                                 "heat_pump": {"status": "planning", "floor_area_m2": 90, "epc_rating": "D"}},
    "estimate, already on Go": {**EST, "tariff": {"current_tariff_key": "octopusGo"}},
}


@pytest.mark.parametrize("name", SAMPLES)
def test_sample_responses_validate_against_the_schema(name, response_schema):
    r = assess(SAMPLES[name])
    assert r.status_code == 200, r.text
    jsonschema.validate(r.json(), response_schema)


def test_upload_response_validates_against_the_schema(response_schema):
    r = upload({"usage": {"route": "upload"}}, [octopus_csv("2025-03-01", "2025-09-01")])
    assert r.status_code == 200, r.text
    jsonschema.validate(r.json(), response_schema)


def test_request_examples_validate_against_the_request_schema():
    schema = json.loads(Path(SCHEMA_FILE).read_text())["request"]
    for body in SAMPLES.values():
        jsonschema.validate(body, schema)


# ── Behaviour ─────────────────────────────────────────────────────────────────

def test_recommends_the_best_value_size_when_none_is_given():
    j = assess().json()
    best = j["size_comparison"]["best_value"]
    rec = j["recommendation"]
    assert rec["chosen_by"] == "best_value"
    assert (rec["battery_kwh"], rec["tariff_key"]) == (best["kwh"], best["tariff_key"])
    assert j["headline"]["lifetime_net_gain"]["likely"] == best["lifetime_net_gain"]
    assert j["verdict"] == best["verdict"]


def test_uses_the_battery_asked_about():
    j = assess({**EST, "battery": {"size_kwh": 5, "price_gbp": 3000, "tariff_key": "octopusCosy"}}).json()
    rec = j["recommendation"]
    assert rec == {**rec, "battery_kwh": 5, "tariff_key": "octopusCosy", "installed_price": 3000, "chosen_by": "you"}
    assert j["fair_price"]["your_price_is"] == "below_range"


def test_headline_and_break_even_agree():
    j = assess().json()
    be, h = j["break_even"], j["headline"]
    assert be["years"] == list(range(16))
    assert all(len(be[c]) == 16 for c in ("optimistic", "likely", "pessimistic"))
    assert be["likely"][0] == -h["installed_cost"]["likely"]
    assert be["likely"][-1] == h["lifetime_net_gain"]["likely"]


def test_saving_breakdown_adds_up():
    b = assess().json()["saving_breakdown"]
    assert abs(b["time_shifting"] + b["solar_storage"] + b["other"] - b["total"]) < 1


def test_levers_only_when_not_yet():
    for body in SAMPLES.values():
        j = assess(body).json()
        assert (j["what_would_make_it_pay_back"] is None) == (j["verdict"] != "not_yet")


def test_day_in_life_has_summer_and_winter():
    d = assess().json()["day_in_life"]
    assert d["summer"] and d["winter"] and d["average"]
    assert sum(d["winter"]["load"]) > sum(d["summer"]["load"])
    assert all(len(d["average"][k]) == 48 for k in ("load", "grid_to_battery", "from_battery",
                                                    "grid_to_home", "battery_level"))


def test_upload_route_reports_coverage():
    j = upload({"usage": {"route": "upload"}, "tariff": {"unit_rate_p": 25}},
               [octopus_csv("2025-01-01", "2025-04-01")]).json()
    u = j["usage"]
    assert u["route"] == "upload" and u["days_found"] == 90 and u["confidence"] == "medium"
    assert u["coverage"]["first_date"] == "2025-01-01" and u["unit_rate_p"] == 25


def test_assumptions_carry_the_dates():
    a = assess().json()["assumptions"]
    assert a["costs_as_of"] and a["tariffs_checked"]
    assert a["verdict_thresholds"] == {"worth_it_share_of_warranty": 0.7, "borderline_share_of_warranty": 1.0}


def test_nothing_is_cached_between_requests():
    before = len(analyse._session_cache)
    assess()
    upload({"usage": {"route": "upload"}}, [octopus_csv("2025-01-01", "2025-02-01")])
    assert len(analyse._session_cache) == before


# ── Validation ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("body", [
    {"usage": {"route": "estimate"}},                                          # no annual_kwh
    {"usage": {"route": "estimate", "annual_kwh": 3500}, "colour": "blue"},    # unknown field
    {"usage": {"route": "guess", "annual_kwh": 3500}},
    {"usage": {"route": "estimate", "annual_kwh": 100}},
    {"usage": {"route": "upload"}},                                            # no files
    {**EST, "ev": {"status": "planning", "charge_start": "25:00"}},
])
def test_bad_requests_are_422(body):
    assert assess(body).status_code == 422


def test_unknown_tariff_keys_are_400():
    assert assess({**EST, "battery": {"tariff_key": "nope"}}).status_code == 400
    assert assess({**EST, "tariff": {"current_tariff_key": "nope"}}).status_code == 400


def test_multipart_without_inputs_is_422():
    r = client.post(URL, files=[("files", ("u.csv", octopus_csv("2025-01-01", "2025-01-08"), "text/csv"))])
    assert r.status_code == 422


def test_bad_csv_is_422():
    r = upload({"usage": {"route": "upload"}}, [b"no,useful,columns\n1,2,3\n"])
    assert r.status_code == 422
