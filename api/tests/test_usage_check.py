"""Task 2.4 — reading different supplier/app CSV layouts, and POST /api/v2/usage/check."""
import json
from datetime import date
from pathlib import Path

import jsonschema
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from engine.csv_parser import parse_csv_bytes
from main import app
from routers import analyse
from scripts.export_v2_schema import OUT as SCHEMA_FILE
from tests.test_full_year import octopus_csv

client = TestClient(app)
URL = "/api/v2/usage/check"


def csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode()


def half_hours(start, end, tz=None):
    return pd.date_range(start, end, freq="30min", inclusive="left", tz=tz)


# ── Layouts ───────────────────────────────────────────────────────────────────

def test_n3rgy_style_utc_column_is_read_as_utc():
    """A '(UTC)' time column in summer: 00:00 UTC is 01:00 in the UK."""
    idx = half_hours("2025-07-01", "2025-07-08")          # 1 Jul 00:00 UTC to 8 Jul 00:00 UTC
    raw = csv(pd.DataFrame({"timestamp (UTC)": idx.strftime("%Y-%m-%d %H:%M"),
                            "energyConsumption (kWh)": [0.2] * len(idx)}))
    p = parse_csv_bytes(raw)
    first, last = p.readings[date(2025, 7, 1)], p.readings[date(2025, 7, 8)]
    assert first[0] is None and first[1] is None, "00:00-00:59 UK on 1 July was 30 June in UTC"
    assert first[2] == pytest.approx(0.2), "the first reading lands at 01:00 UK"
    assert last[0] == pytest.approx(0.2) and last[1] == pytest.approx(0.2) and last[2] is None
    assert p.coverage["last_date"] == "2025-07-08"
    assert p.total_kwh == pytest.approx(0.2 * len(idx))


def test_separate_date_and_time_columns():
    idx = half_hours("2025-03-03", "2025-03-10")
    raw = csv(pd.DataFrame({"Date": idx.strftime("%d/%m/%Y"), "Time": idx.strftime("%H:%M"), "kWh": [0.3] * len(idx)}))
    p = parse_csv_bytes(raw)
    assert p.coverage["days_found"] == 7 and p.coverage["half_hours_filled"] == 0
    assert p.total_kwh == pytest.approx(0.3 * len(idx))


def test_column_names_recognised_by_content():
    idx = half_hours("2025-02-01", "2025-02-08")
    raw = csv(pd.DataFrame({"Read Start": idx.strftime("%Y-%m-%dT%H:%M:%S"),
                            "Import Usage kWh": [0.25] * len(idx),
                            "Export kWh": [0.9] * len(idx)}))
    p = parse_csv_bytes(raw)
    assert p.total_kwh == pytest.approx(0.25 * len(idx)), "export must not be read as consumption"


def test_hourly_readings_are_split_into_half_hours():
    idx = pd.date_range("2025-04-07", "2025-04-14", freq="1h", inclusive="left")
    raw = csv(pd.DataFrame({"Timestamp": idx.strftime("%Y-%m-%d %H:%M"), "Consumption (kWh)": [0.6] * len(idx)}))
    p = parse_csv_bytes(raw)
    assert p.coverage["days_found"] == 7 and p.coverage["half_hours_filled"] == 0
    day = p.days[p.dates.index(date(2025, 4, 8))]
    assert all(v == pytest.approx(0.3) for v in day)
    assert p.total_kwh == pytest.approx(0.6 * len(idx))


def test_daily_readings_are_rejected_plainly():
    idx = pd.date_range("2025-01-01", "2025-03-01", freq="1D", inclusive="left")
    raw = csv(pd.DataFrame({"Date": idx.strftime("%Y-%m-%d"), "kWh": [9.0] * len(idx)}))
    with pytest.raises(ValueError, match="half-hourly"):
        parse_csv_bytes(raw)


def test_no_usage_column_gives_a_plain_message():
    raw = csv(pd.DataFrame({"Date": ["2025-01-01"], "Notes": ["hello"]}))
    with pytest.raises(ValueError, match="couldn't find the electricity use"):
        parse_csv_bytes(raw)


# ── Endpoint ──────────────────────────────────────────────────────────────────

def post(*files):
    return client.post(URL, files=[("files", (name, data, "text/csv")) for name, data in files])


def test_reports_coverage_for_good_files():
    r = post(("jan.csv", octopus_csv("2025-01-01", "2025-02-01")), ("feb.csv", octopus_csv("2025-02-01", "2025-03-01")))
    assert r.status_code == 200, r.text
    j = r.json()
    assert [f["ok"] for f in j["files"]] == [True, True]
    assert j["files"][0]["days_found"] == 31 and j["files"][1]["first_date"] == "2025-02-01"
    c = j["combined"]
    assert c["days_found"] == 59 and c["first_date"] == "2025-01-01" and c["last_date"] == "2025-02-28"
    assert c["confidence"] == "low" and c["days_scaled_from_estimate"] == 365 - 59
    jsonschema.validate(j, json.loads(Path(SCHEMA_FILE).read_text())["usage_check_response"])


def test_one_bad_file_does_not_hide_the_good_one():
    r = post(("good.csv", octopus_csv("2025-05-01", "2025-08-01")), ("bad.csv", b"just,some,columns\n1,2,3\n"))
    j = r.json()
    assert j["files"][0]["ok"] is True
    assert j["files"][1]["ok"] is False and "couldn't find" in j["files"][1]["error"]
    assert j["combined"]["days_found"] == 92 and j["combined"]["confidence"] == "medium"


def test_all_bad_files_give_no_combined_result():
    j = post(("bad.csv", b"x\n1\n")).json()
    assert j["files"][0]["ok"] is False and j["combined"] is None


def test_needs_multipart_files():
    assert client.post(URL, json={}).status_code == 422
    assert client.post(URL, files=[("other", ("a.csv", b"x", "text/csv"))]).status_code == 422


def test_too_many_files():
    r = post(*[(f"{i}.csv", b"x\n1\n") for i in range(21)])
    assert r.status_code == 422


def test_check_stores_nothing():
    before = len(analyse._session_cache)
    post(("jan.csv", octopus_csv("2025-01-01", "2025-02-01")))
    assert len(analyse._session_cache) == before
