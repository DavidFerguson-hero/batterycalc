"""
Task 1.1 — full-year modelling.

Estimate route: 365 seasonal days that add up to the annual figure.
CSV route: dated readings become one full year, with gaps filled and coverage reported.
Simulator: battery charge carries over from one day to the next.
"""
from dataclasses import replace
from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from engine.csv_parser import merge_parse_results, parse_csv_bytes
from engine.profile_estimator import generate_days, make_parse_result, model_year_dates
from engine.simulator import run_simulation, simulate_day_full
from engine.tariffs import TARIFFS
from main import app


# ── Helpers ───────────────────────────────────────────────────────────────────

def octopus_csv(start: str, end: str, kwh=lambda ts: 0.25, drop=()) -> bytes:
    """An Octopus-style export: ' Consumption (kWh)', ' Start', ' End' with UTC offsets."""
    idx = pd.date_range(start, end, freq="30min", tz="Europe/London", inclusive="left")
    rows = [
        (kwh(ts), ts.isoformat(), (ts + pd.Timedelta(minutes=30)).isoformat())
        for ts in idx if ts not in drop
    ]
    df = pd.DataFrame(rows, columns=[" Consumption (kWh)", " Start", " End"])
    return df.to_csv(index=False).encode()


def winter_heavy(ts) -> float:
    return 0.35 if ts.month in (11, 12, 1, 2) else 0.2


def month_total(days, dates, month):
    return sum(sum(d) for d, x in zip(days, dates) if x.month == month)


# ── Estimate route ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("heating", ["gas", "electric"])
@pytest.mark.parametrize("annual", [1800, 3500, 6500])
def test_estimate_365_days_sum_to_annual_within_1pct(annual, heating):
    days = generate_days(annual, "semi", heating)
    assert len(days) == 365
    assert all(len(d) == 48 for d in days)
    assert abs(sum(map(sum, days)) - annual) / annual < 0.01


def test_estimate_december_above_june_typical_house():
    days, dates = generate_days(3500, "semi"), model_year_dates()
    dec, jun = month_total(days, dates, 12) / 31, month_total(days, dates, 6) / 30
    assert dec > jun * 1.2, f"Dec {dec:.2f} vs Jun {jun:.2f} kWh/day"


def test_electric_heating_swings_more_than_gas():
    dates = model_year_dates()
    ratio = {}
    for h in ("gas", "electric"):
        days = generate_days(3500, "semi", h)
        ratio[h] = (month_total(days, dates, 12) / 31) / (month_total(days, dates, 6) / 30)
    assert ratio["electric"] > ratio["gas"] * 1.5, ratio


def test_estimate_rejects_unknown_heating():
    with pytest.raises(ValueError):
        generate_days(3500, "semi", "coal")


def test_make_parse_result_reports_a_full_year():
    p = make_parse_result(3500, "semi", 28.16)
    assert p.days_count == 365 and len(p.dates) == 365
    assert p.confidence == "estimate"
    assert abs(p.total_kwh - 3500) < 1


# ── CSV route ─────────────────────────────────────────────────────────────────

def test_csv_full_year_is_used_as_is():
    raw = octopus_csv("2025-01-01", "2026-01-01", winter_heavy)
    p = parse_csv_bytes(raw)
    assert len(p.days) == 365
    assert p.dates[0] == date(2025, 1, 1) and p.dates[-1] == date(2025, 12, 31)
    assert p.confidence == "high"
    c = p.coverage
    assert c["days_found"] == 365 and c["days_scaled_from_estimate"] == 0
    # Every reading lands somewhere: nothing is lost, including on clock-change days.
    expected = sum(winter_heavy(ts) for ts in pd.date_range("2025-01-01", "2026-01-01", freq="30min",
                                                             tz="Europe/London", inclusive="left"))
    assert abs(sum(map(sum, p.days)) - expected) < 1e-6
    assert abs(p.total_kwh - expected) < 1e-3


def test_csv_clock_change_days():
    p = parse_csv_bytes(octopus_csv("2025-03-29", "2025-03-31"))     # 30 Mar: clocks go forward
    spring = p.days[p.dates.index(date(2025, 3, 30))]
    assert abs(sum(spring) - 46 * 0.25) < 1e-9, "01:00–01:59 never happened, so it is zero, not invented"
    assert p.coverage["partial_days_filled"] == 0 and p.coverage["half_hours_filled"] == 0
    p = parse_csv_bytes(octopus_csv("2025-10-25", "2025-10-27"))     # 26 Oct: clocks go back
    autumn = p.days[p.dates.index(date(2025, 10, 26))]
    assert abs(sum(autumn) - 50 * 0.25) < 1e-9, "the repeated hour is added, not lost"


def test_csv_gaps_are_filled_and_reported():
    gone_day = set(pd.date_range("2025-02-10", "2025-02-11", freq="30min", tz="Europe/London", inclusive="left"))
    gone_slots = set(pd.date_range("2025-02-20 18:00", "2025-02-20 20:00", freq="30min",
                                   tz="Europe/London", inclusive="left"))
    p = parse_csv_bytes(octopus_csv("2025-01-01", "2025-04-01", drop=gone_day | gone_slots))
    c = p.coverage
    assert c["missing_days_filled"] == 1
    assert c["partial_days_filled"] == 1
    assert c["half_hours_filled"] == 48 + 4
    assert abs(sum(p.days[p.dates.index(date(2025, 2, 10))]) - 48 * 0.25) < 1e-9


def test_csv_part_year_is_scaled_and_confidence_lowered():
    p = parse_csv_bytes(octopus_csv("2025-11-01", "2026-01-01", winter_heavy))   # Nov–Dec only
    assert len(p.days) == 365 and p.dates[-1] == date(2025, 12, 31)
    assert p.confidence == "low"
    assert p.coverage["days_found"] == 61
    assert p.coverage["days_scaled_from_estimate"] == 304
    jun = month_total(p.days, p.dates, 6) / 30
    dec = month_total(p.days, p.dates, 12) / 31
    assert 0 < jun < dec, "scaled summer days come out lower than the real winter days"


def test_csv_medium_confidence_for_a_few_months():
    p = parse_csv_bytes(octopus_csv("2025-01-01", "2025-05-01"))
    assert p.confidence == "medium"


def test_csv_more_than_a_year_keeps_latest_365_days():
    p = parse_csv_bytes(octopus_csv("2024-11-01", "2026-01-01"))
    assert len(p.days) == 365 and p.dates[-1] == date(2025, 12, 31)
    assert p.coverage["days_dropped_older_than_a_year"] == 61


def test_csv_without_timestamps_falls_back():
    raw = pd.DataFrame({"Electricity consumption (kWh)": [0.2] * 48 * 10}).to_csv(index=False).encode()
    p = parse_csv_bytes(raw)
    assert p.dates is None and len(p.days) == 10
    assert p.confidence == "low" and p.coverage["has_dates"] is False
    assert abs(p.annual_kwh_estimate - 0.2 * 48 * 365) < 1


def test_merging_overlapping_files_does_not_double_count():
    a = parse_csv_bytes(octopus_csv("2025-01-01", "2025-03-01"))
    b = parse_csv_bytes(octopus_csv("2025-02-01", "2025-04-01"))
    m = merge_parse_results([a, b])
    assert m.coverage["first_date"] == "2025-01-01" and m.coverage["last_date"] == "2025-03-31"
    assert m.coverage["days_found"] == 90
    assert m.total_kwh == pytest.approx(90 * 48 * 0.25 - 0.5)   # spring clock change: one hour shorter


# ── Simulator: charge carries over between days ───────────────────────────────

LOAD = [0.2] * 48


def test_day_starts_where_the_last_ended():
    go = TARIFFS["octopusGo"]
    d1 = simulate_day_full(LOAD, go, 10, 3.6, 0.9)
    d2 = simulate_day_full(LOAD, go, 10, 3.6, 0.9, start_soc=d1.end_soc)
    assert d1.end_soc == d1.soc_profile[-1]
    assert d2.soc_profile[0] <= d1.end_soc + 1e-9   # slot 0 is a Go day-rate slot: no charging


def test_start_soc_is_clamped_to_battery_limits():
    go = TARIFFS["octopusGo"]
    assert simulate_day_full(LOAD, go, 10, 3.6, 0.9, start_soc=99).soc_profile[0] <= 10
    assert simulate_day_full(LOAD, go, 10, 3.6, 0.9, start_soc=0).soc_profile[0] >= 1 - 1e-9


def test_cosy_late_window_is_no_longer_wasted():
    """Regression for task 0.4: with the midnight reset, charging at 22:00–00:00 was paid
    for and thrown away, cutting Cosy's battery saving from about £313 to £73 a year.
    With carry-over that charge is used the next morning, so the window costs nothing."""
    cosy = TARIFFS["octopusCosy"]
    assert all(cosy.charge_slots[i] for i in range(44, 48))
    no_late = replace(cosy, charge_slots=[c and i < 44 for i, c in enumerate(cosy.charge_slots)])
    days = generate_days(3500, "semi")
    for cap in (5.0, 10.0):
        with_late = run_simulation(cosy, cap, 3.6, 0.9, days, 0.2816, 53.0).saving_battery_only
        without = run_simulation(no_late, cap, 3.6, 0.9, days, 0.2816, 53.0).saving_battery_only
        assert with_late > without - 5, f"{cap} kWh: £{with_late:.0f} vs £{without:.0f} without the window"


# ── API ───────────────────────────────────────────────────────────────────────

client = TestClient(app)


def test_estimate_endpoint_models_a_full_year():
    r = client.post("/api/estimate", json={"annual_kwh": 3500, "property_type": "semi", "heating_type": "electric"})
    assert r.status_code == 200, r.text
    s = r.json()["summary"]
    assert s["days_modelled"] == 365 and s["confidence"] == "estimate"
    sid = r.json()["session_id"]
    r2 = client.post("/api/recalculate", json={"session_id": sid, "tariff_key": "octopusCosy"})
    assert r2.status_code == 200, r2.text


def test_estimate_rejects_unknown_heating_type():
    r = client.post("/api/estimate", json={"annual_kwh": 3500, "heating_type": "coal"})
    assert r.status_code == 422


def test_upload_endpoint_reports_coverage():
    raw = octopus_csv("2025-06-01", "2025-09-01")
    r = client.post("/api/analyse", files=[("files", ("usage.csv", raw, "text/csv"))])
    assert r.status_code == 200, r.text
    s = r.json()["summary"]
    assert s["days_modelled"] == 365
    assert s["coverage"]["days_found"] == 92
    assert s["confidence"] == "medium"
