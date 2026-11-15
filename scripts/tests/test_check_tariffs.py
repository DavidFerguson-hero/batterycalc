"""
Tests for the Octopus part of scripts/check_tariffs.py, using real API
responses saved on 15 Nov 2026 (scripts/tests/fixtures/, trimmed to region A).

Run from scripts/:  pytest
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import check_tariffs as ct  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(scope="module")
def products() -> list[dict]:
    return load("products.json")["results"]


# ── Product selection ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("key,expected_code", [
    ("octopusGo",          "GO-VAR-22-10-14"),
    ("intelligentOctopus", "IOG-SMB-VAR-26-11-04"),
    ("octopusCosy",        "COSY-22-12-08"),
])
def test_picks_the_variable_product(products, key, expected_code):
    prod = ct.pick_octopus_product(products, ct.OCTOPUS_PRODUCTS[key])
    assert prod is not None
    assert prod["code"] == expected_code


def test_old_substring_match_picked_intelligent_flux(products):
    """Regression: the old 'Intelligent Octopus' substring match chose a Flux product,
    which is why day and night were both logged as 24.27p."""
    old_pick = next(p for p in products if "Intelligent Octopus" in p["display_name"])
    assert old_pick["code"].startswith("INTELLI-FLUX")
    new_pick = ct.pick_octopus_product(products, "Intelligent Octopus Go")
    assert new_pick["code"] != old_pick["code"]


def test_no_match_returns_none(products):
    assert ct.pick_octopus_product(products, "Octopus Nonexistent") is None


def test_ignores_withdrawn_and_business_products(products):
    withdrawn = dict(products[0], display_name="Test Tariff", available_to="2026-01-01T00:00:00Z")
    business = dict(products[0], display_name="Test Tariff", is_business=True)
    assert ct.pick_octopus_product([withdrawn, business], "Test Tariff") is None


# ── Rate parsing ──────────────────────────────────────────────────────────────

def test_parse_go():
    rates = ct.parse_octopus_go(
        load("product_GO-VAR-22-10-14.json"),
        load("unit_rates_GO-VAR-22-10-14.json"),
    )
    assert rates == {"night_p": 9.4, "day_p": 34.71, "standing_p": 51.67}


def test_parse_intelligent_octopus_four_rate_format():
    detail = load("product_IOG-SMB-VAR-26-11-04.json")
    group, _ = ct.octopus_tariff_terms(detail)
    assert group == "four_rate_ev_electricity_tariffs"
    rates = ct.parse_intelligent_octopus(detail)
    assert rates == {"night_p": 9.9, "day_p": 34.46, "standing_p": 51.94}
    assert rates["night_p"] < rates["day_p"]


def test_parse_cosy_three_distinct_rates():
    rates = ct.parse_octopus_cosy(
        load("product_COSY-22-12-08.json"),
        load("unit_rates_COSY-22-12-08.json"),
    )
    assert rates == {"cosy_p": 14.13, "standard_p": 28.82, "peak_p": 43.22, "standing_p": 51.67}


def test_cosy_standard_is_not_the_product_headline_rate():
    """Regression: the product's standard_unit_rate field holds the Cosy rate, not the
    standard rate, so reading it logged standard_p = cosy_p = 14.13p."""
    detail = load("product_COSY-22-12-08.json")
    _, terms = ct.octopus_tariff_terms(detail)
    rates = ct.parse_octopus_cosy(detail, load("unit_rates_COSY-22-12-08.json"))
    assert round(terms["standard_unit_rate_inc_vat"], 2) == rates["cosy_p"]
    assert rates["standard_p"] != rates["cosy_p"]


# ── Implausible data is reported as an error, never as a rate change ──────────

def test_go_with_one_rate_is_an_error():
    flat = {"results": [{"value_inc_vat": 24.27}, {"value_inc_vat": 24.27}]}
    with pytest.raises(ct.OctopusParseError):
        ct.parse_octopus_go(load("product_GO-VAR-22-10-14.json"), flat)


def test_cosy_with_two_rates_is_an_error():
    two = {"results": [{"value_inc_vat": 14.13}, {"value_inc_vat": 28.82}]}
    with pytest.raises(ct.OctopusParseError):
        ct.parse_octopus_cosy(load("product_COSY-22-12-08.json"), two)


def test_intelligent_night_not_below_day_is_an_error():
    detail = load("product_IOG-SMB-VAR-26-11-04.json")
    terms = detail["four_rate_ev_electricity_tariffs"]["_A"]["direct_debit_monthly"]
    terms["night_unit_rate_inc_vat"] = terms["day_unit_rate_inc_vat"]
    with pytest.raises(ct.OctopusParseError):
        ct.parse_intelligent_octopus(detail)


def test_missing_region_is_an_error():
    with pytest.raises(ct.OctopusParseError):
        ct.octopus_tariff_terms({"single_register_electricity_tariffs": {"_B": {}}})


# ── End to end, with the network replaced by the saved responses ──────────────

@pytest.fixture
def offline_api(monkeypatch):
    def fake_get_json(url: str) -> dict:
        for code in ("GO-VAR-22-10-14", "IOG-SMB-VAR-26-11-04", "COSY-22-12-08"):
            if f"/{code}/electricity-tariffs/" in url:
                return load(f"unit_rates_{code}.json")
            if url.endswith(f"/{code}/"):
                return load(f"product_{code}.json")
        raise AssertionError(f"Unexpected URL in test: {url}")
    monkeypatch.setattr(ct, "_get_json", fake_get_json)


@pytest.mark.parametrize("key", list(ct.OCTOPUS_PRODUCTS))
def test_check_octopus_matches_current_rates(offline_api, products, key):
    """The saved responses are the rates approved in task 0.4, so all three report ok."""
    result = ct.check_octopus(key, products)
    assert result["status"] == "ok", result.get("changes") or result.get("error")
    assert result["found_rates"] == ct.CURRENT[key]


def test_check_octopus_reports_error_not_change_for_bad_data(monkeypatch, products):
    def bad_get_json(url: str) -> dict:
        if "/electricity-tariffs/" in url:
            return {"results": [{"value_inc_vat": 24.27}]}
        return load("product_GO-VAR-22-10-14.json")
    monkeypatch.setattr(ct, "_get_json", bad_get_json)
    result = ct.check_octopus("octopusGo", products)
    assert result["status"] == "error"
