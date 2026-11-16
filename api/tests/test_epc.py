"""
EPC lookup on the GOV.UK "Get energy performance of buildings data" API, and the
annual electricity estimate. The network is replaced by published sample certificates
(tests/fixtures/epc/, from communitiesuk/epb-data-warehouse), so no real calls are made.
"""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import routers.epc as epc
from main import app

FIX = Path(__file__).parent / "fixtures" / "epc"
CERTS = {
    "0001-0001-0001-0001-0001": "rdsap17_flat_storage_heaters",
    "0002-0002-0002-0002-0002": "rdsap20_terrace_gas",
    "0003-0003-0003-0003-0003": "sap16_semi_storage_heaters",
    "0004-0004-0004-0004-0004": "rdsap21_terrace_gas_battery",
}


def cert(name: str) -> dict:
    return json.loads((FIX / f"{name}.json").read_text())


def summary(n: str, line1: str, date="2024-01-01", band="D") -> dict:
    return {"certificateNumber": n, "addressLine1": line1, "addressLine2": "EXAMPLE ROAD",
            "postTown": "TESTTOWN", "postcode": "AB1 2CD", "registrationDate": date,
            "currentEnergyEfficiencyBand": band}


SEARCH = {"data": [
    summary("0002-0002-0002-0002-0002", "10"),
    summary("0001-0001-0001-0001-0001", "FLAT 2"),
    summary("0003-0003-0003-0003-0003", "2"),
    summary("0004-0004-0004-0004-0004", "2", date="2025-04-04"),     # same address, newer: wins
    summary("9999-9999-9999-9999-9999", "2", date="2019-01-01"),     # same address, older: dropped
], "pagination": {"totalRecords": 5}}


@pytest.fixture
def fake_epc(monkeypatch):
    calls = []

    async def fake_get(client, path, params):
        calls.append((path, dict(params), client.headers.get("Authorization")))
        if path == "/api/domestic/search":
            return (200, SEARCH) if params["postcode"] == "AB1 2CD" else (404, {"error": "none"})
        if path == "/api/certificate":
            name = CERTS.get(params["certificate_number"])
            return (200, {"data": cert(name)}) if name else (404, None)
        raise AssertionError(path)

    monkeypatch.setattr(epc, "_get_json", fake_get)
    monkeypatch.setenv("EPC_API_TOKEN", "test-token")
    return calls


client = TestClient(app)


# ── Lookup ────────────────────────────────────────────────────────────────────

def test_lookup_lists_newest_certificate_per_address_in_natural_order(fake_epc):
    r = client.get("/api/epc/lookup", params={"postcode": "ab12cd"})
    assert r.status_code == 200, r.text
    homes = r.json()["properties"]
    assert [h["address"] for h in homes] == [
        "2, Example Road, Testtown", "10, Example Road, Testtown", "Flat 2, Example Road, Testtown"]
    assert homes[0]["certificate_number"] == "0004-0004-0004-0004-0004"


def test_lookup_sends_bearer_token_and_normalised_postcode(fake_epc):
    client.get("/api/epc/lookup", params={"postcode": " ab1 2cd "})
    search = [c for c in fake_epc if c[0] == "/api/domestic/search"][0]
    assert search[1]["postcode"] == "AB1 2CD" and search[2] == "Bearer test-token"


def test_unknown_postcode_is_not_found(fake_epc):
    j = client.get("/api/epc/lookup", params={"postcode": "ZZ9 9ZZ"}).json()
    assert j == {"found": False, "properties": []}


def test_bad_postcode_is_rejected_before_calling_out(fake_epc):
    r = client.get("/api/epc/lookup", params={"postcode": "HELLO"})
    assert r.status_code == 422 and not fake_epc


def test_not_configured(monkeypatch):
    monkeypatch.delenv("EPC_API_TOKEN", raising=False)
    assert client.get("/api/epc/lookup", params={"postcode": "AB1 2CD"}).status_code == 503


@pytest.mark.parametrize("status,expected", [(401, 503), (403, 503), (429, 503), (500, 502)])
def test_service_errors_are_explained(monkeypatch, status, expected):
    async def fail(client, path, params):
        return status, None
    monkeypatch.setattr(epc, "_get_json", fail)
    monkeypatch.setenv("EPC_API_TOKEN", "t")
    r = client.get("/api/epc/lookup", params={"postcode": "AB1 2CD"})
    assert r.status_code == expected and r.json()["detail"]


def test_a_missing_certificate_is_skipped(monkeypatch, fake_epc):
    original = epc._get_json

    async def one_missing(client, path, params):
        if params.get("certificate_number") == "0002-0002-0002-0002-0002":
            return 404, None
        return await original(client, path, params)
    monkeypatch.setattr(epc, "_get_json", one_missing)
    homes = client.get("/api/epc/lookup", params={"postcode": "AB1 2CD"}).json()["properties"]
    assert len(homes) == 2


# ── Reading certificates ──────────────────────────────────────────────────────

def parse(name):
    return epc.parse_certificate(summary("x", "1 TEST STREET"), cert(name))


def test_flat_with_storage_heaters():
    h = parse("rdsap17_flat_storage_heaters")      # dwelling_type wrapped as {"value": ...}
    assert (h["property_type"], h["heating_kind"], h["heating_type"]) == ("flat", "electric", "electric")
    assert h["floor_area_m2"] == 55 and h["epc_rating"] == "D" and h["bedrooms"] == 2
    assert h["has_gas"] is False and h["has_solar"] is False


def test_gas_terrace_with_solar():
    h = parse("rdsap20_terrace_gas")
    assert (h["property_type"], h["heating_kind"], h["heating_type"]) == ("terraced", "gas", "gas")
    assert h["has_gas"] is True and h["has_solar"] is True      # 50% of roof
    assert "mains gas" in h["heating_description"]


def test_older_sap_spells_it_main_gas():
    h = parse("sap16_semi_storage_heaters")
    assert h["property_type"] == "semi" and h["heating_kind"] == "electric" and h["has_gas"] is False


def test_existing_battery_detected():
    assert parse("rdsap21_terrace_gas_battery")["has_battery"] is True
    assert parse("rdsap20_terrace_gas")["has_battery"] is False


def test_classic_calculator_fields_are_all_present():
    h = parse("rdsap20_terrace_gas")
    for k in ("lmk_key", "address", "property_type", "bedrooms", "annual_kwh", "has_solar", "has_gas",
              "floor_area_m2", "energy_per_m2", "epc_rating", "confidence"):
        assert k in h


# ── The estimate (the old one inflated gas-heated homes 2–4×) ─────────────────

def test_gas_heated_home_gets_the_beis_baseline():
    assert epc.estimate_annual_kwh("semi", 3, 90, "gas", "D") == (3500, "medium")
    assert epc.estimate_annual_kwh("detached", 4, 150, "other_fuel", "F") == (5100, "medium")


def test_storage_heaters_add_full_heat_demand():
    kwh, _ = epc.estimate_annual_kwh("flat", 2, 55, "electric", "D")
    assert kwh == 2400 + 55 * 120


def test_heat_pump_adds_a_third():
    kwh, _ = epc.estimate_annual_kwh("semi", 3, 90, "heat_pump", "C")
    assert kwh == 3500 + 90 * 90 // 3


def test_estimate_is_capped_and_rounded():
    kwh, _ = epc.estimate_annual_kwh("detached", 5, 400, "electric", "G")
    assert kwh == 20000
    assert epc.estimate_annual_kwh("semi", 3, 90, "gas", "D")[0] % 100 == 0


def test_unknown_bedrooms_is_low_confidence():
    assert epc.estimate_annual_kwh("semi", None, 90, "gas", "D")[1] == "low"


def test_postcode_normalising():
    assert epc.normalise_postcode("sw1a1aa") == "SW1A 1AA"
    assert epc.normalise_postcode("M1 1AE") == "M1 1AE"
