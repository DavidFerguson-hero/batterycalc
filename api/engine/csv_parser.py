"""
CSV parser for half-hourly smart meter exports.

Columns (matched case-insensitively, surrounding spaces ignored):
  - consumption, e.g. 'Electricity consumption (kWh)' or Octopus ' Consumption (kWh)'  (required)
  - cost, e.g. 'Electricity cost (£)'                         (optional — infers the unit rate)
  - timestamp, e.g. 'Start', 'Timestamp', 'Interval start'    (optional but strongly preferred)

With timestamps, readings are placed on the right calendar day and half-hour
(UK local time, so clock-change days work), and the result is always one full
year of 365 days:
  - up to 12 months of data is used; anything older than the latest 365 days is dropped
  - missing half-hours and missing days inside the data are filled from similar days
  - if less than a year is uploaded, the missing months are scaled from the uploaded
    data using the seasonal shape in profile_estimator, and confidence is lowered
Without timestamps, rows are read as consecutive 48-slot days (the old behaviour)
and the result is annualised by simple scaling, with low confidence.

Uploaded data is processed in memory only and never written to disk or logs.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

SLOTS = 48
UK_TZ = "Europe/London"
MAX_DAYS = 365


@dataclass
class ParseResult:
    days: list[list[float]]
    inferred_rate: float | None
    days_count: int                 # days with real readings (estimate route: modelled days)
    total_kwh: float                # kWh actually read from the file(s)
    daily_avg_kwh: float
    annual_kwh_estimate: float
    dates: list[date] | None = None  # calendar date of each entry in days, when known
    coverage: dict | None = None     # what was found and what was filled (CSV route)
    confidence: str | None = None    # "high" | "medium" | "low" | "estimate"
    # Raw readings keyed by date, kept only so several files can be merged.
    readings: dict = field(default_factory=dict, repr=False)


_CONSUMPTION_ALIASES = [
    "electricity consumption (kwh)",
    "consumption (kwh)",
    "consumption",
    "kwh",
    "energy (kwh)",
    "import (kwh)",
]

_COST_ALIASES = [
    "electricity cost (£)",
    "cost (£)",
    "cost",
    "charge (£)",
    "amount (£)",
]

_START_ALIASES = [
    "start", "start time", "interval start", "start date", "start datetime",
    "timestamp", "datetime", "date time", "read date time", "reading time",
]
_END_ALIASES = ["end", "end time", "interval end"]

_TZ_SUFFIX = re.compile(r"(Z|[+-]\d{2}:?\d{2})$")


def _find_col(columns: list[str], aliases: list[str]) -> str | None:
    lower = {c.lower().strip(): c for c in columns}
    for alias in aliases:
        if alias in lower:
            return lower[alias]
    return None


def _to_uk_local(raw: pd.Series) -> pd.Series:
    """Parse timestamps to naive UK local time. Offsets/Z are honoured; naive values are taken as UK local."""
    text = raw.astype(str).str.strip()
    sample = text.dropna().head(20)
    if any(_TZ_SUFFIX.search(s) for s in sample):
        ts = pd.to_datetime(text, utc=True, errors="coerce", format="mixed")
        return ts.dt.tz_convert(UK_TZ).dt.tz_localize(None)
    return pd.to_datetime(text, errors="coerce", dayfirst=True, format="mixed")


def _readings_by_date(local: pd.Series, kwh: list[float]) -> dict[date, list[float | None]]:
    """{date: 48 slots}, None where no reading. Two readings in one slot (clocks going back) are added."""
    out: dict[date, list[float | None]] = {}
    for ts, v in zip(local, kwh):
        if pd.isna(ts):
            continue
        d = ts.date()
        slot = ts.hour * 2 + (1 if ts.minute >= 30 else 0)
        day = out.setdefault(d, [None] * SLOTS)
        day[slot] = v if day[slot] is None else day[slot] + v
    return out


def _nonexistent_slots(d: date) -> list[int]:
    """Half-hours that don't exist on d in UK local time (01:00–01:59 when the clocks go forward)."""
    out = []
    for slot in range(SLOTS):
        local = pd.Timestamp(d) + pd.Timedelta(minutes=30 * slot)
        if pd.isna(local.tz_localize(UK_TZ, nonexistent="NaT", ambiguous=True)):
            out.append(slot)
    return out


def _with_clock_gaps_zeroed(readings: dict[date, list[float | None]]) -> dict[date, list[float | None]]:
    """A meter has no reading for an hour that never happened; record it as 0, not as a gap."""
    out = {}
    for d, day in readings.items():
        if d.month == 3 and d.weekday() == 6 and d.day >= 25:      # last Sunday in March
            day = list(day)
            for slot in _nonexistent_slots(d):
                if day[slot] is None:
                    day[slot] = 0.0
        out[d] = day
    return out


def _infer_rate(values: list[float], costs: list[float] | None) -> float | None:
    if not costs:
        return None
    total_kwh, total_cost = sum(values), sum(costs)
    if total_kwh <= 0:
        return None
    raw_rate = total_cost / total_kwh
    # Sanity check: plausible UK rate 5p–80p
    return round(raw_rate, 4) if 0.05 <= raw_rate <= 0.80 else None


def parse_csv_bytes(raw: bytes, heating: str = "gas") -> ParseResult:
    """Parse one CSV file's bytes. See the module docstring for what comes back."""
    df = pd.read_csv(io.BytesIO(raw))
    cols = list(df.columns)

    cons_col = _find_col(cols, _CONSUMPTION_ALIASES)
    if cons_col is None:
        raise ValueError(
            f"Could not find consumption column. Expected one of: {_CONSUMPTION_ALIASES}. "
            f"Found: {cols}"
        )
    cost_col = _find_col(cols, _COST_ALIASES)

    values = pd.to_numeric(df[cons_col], errors="coerce").fillna(0.0).tolist()
    costs = pd.to_numeric(df[cost_col], errors="coerce").fillna(0.0).tolist() if cost_col else None
    rate = _infer_rate(values, costs)

    start_col = _find_col(cols, _START_ALIASES)
    end_col = _find_col(cols, _END_ALIASES)
    local = None
    if start_col is not None:
        local = _to_uk_local(df[start_col])
    elif end_col is not None:
        local = _to_uk_local(df[end_col]) - pd.Timedelta(minutes=30)

    if local is not None and local.notna().mean() >= 0.9:
        readings = _readings_by_date(local, values)
        return build_year(readings, rate, heating)

    return _parse_undated(values, rate)


def _parse_undated(values: list[float], rate: float | None) -> ParseResult:
    """No usable timestamps: consecutive 48-slot days, annualised by simple scaling."""
    days: list[list[float]] = []
    for start in range(0, len(values), SLOTS):
        chunk = values[start:start + SLOTS]
        if len(chunk) < SLOTS:
            chunk = chunk + [0.0] * (SLOTS - len(chunk))
        days.append(chunk)
    days = days[-MAX_DAYS:]
    total = sum(sum(d) for d in days)
    n = len(days)
    daily_avg = total / n if n else 0.0
    return ParseResult(
        days=days,
        inferred_rate=rate,
        days_count=n,
        total_kwh=round(total, 3),
        daily_avg_kwh=round(daily_avg, 3),
        annual_kwh_estimate=round(daily_avg * 365, 1),
        dates=None,
        coverage={
            "has_dates": False,
            "days_found": n,
            "note": "No timestamps found, so seasons and gaps could not be checked.",
        },
        confidence="low",
    )


def _mean_day(days: list[list[float]]) -> list[float]:
    n = len(days)
    return [sum(d[i] for d in days) / n for i in range(SLOTS)]


def build_year(
    readings: dict[date, list[float | None]],
    rate: float | None,
    heating: str = "gas",
) -> ParseResult:
    """Turn dated readings into exactly 365 days ending on the last day with data."""
    from .profile_estimator import monthly_factors   # local import: avoids a cycle

    if not readings:
        raise ValueError("No readings with valid timestamps were found.")

    last = max(readings)
    first_kept = last - timedelta(days=MAX_DAYS - 1)
    dropped_days = sum(1 for d in readings if d < first_kept)
    readings = {d: v for d, v in readings.items() if d >= first_kept}
    first = min(readings)
    readings = _with_clock_gaps_zeroed(readings)

    complete = {d: [float(x) for x in v] for d, v in readings.items() if all(x is not None for x in v)}
    if not complete:
        raise ValueError("No complete days of half-hourly readings were found.")

    by_month: dict[int, list[list[float]]] = {}
    for d, v in complete.items():
        by_month.setdefault(d.month, []).append(v)
    month_mean = {m: _mean_day(v) for m, v in by_month.items()}
    overall_mean = _mean_day(list(complete.values()))

    def typical_day(d: date) -> list[float]:
        return month_mean.get(d.month, overall_mean)

    # Fill gaps inside the uploaded date range.
    filled: dict[date, list[float]] = {}
    partial_days = missing_days = slots_filled = 0
    d = first
    while d <= last:
        day = readings.get(d)
        if day is None:
            fill = list(typical_day(d))
            for slot in _nonexistent_slots(d) if d.month == 3 else ():
                fill[slot] = 0.0
            filled[d] = fill
            missing_days += 1
            slots_filled += SLOTS
        elif d in complete:
            filled[d] = complete[d]
        else:
            ref = typical_day(d)
            filled[d] = [ref[i] if x is None else float(x) for i, x in enumerate(day)]
            partial_days += 1
            slots_filled += sum(1 for x in day if x is None)
        d += timedelta(days=1)

    # Scale the uploaded range to a full year using the seasonal shape.
    factors = monthly_factors(heating)
    in_range_kwh = sum(sum(v) for v in filled.values())
    in_range_weight = sum(factors[x.month - 1] for x in filled)
    base_daily = in_range_kwh / in_range_weight if in_range_weight else 0.0
    shape_total = sum(overall_mean) or 1.0
    shape = [v / shape_total for v in overall_mean]

    year_dates = [first_kept + timedelta(days=i) for i in range(MAX_DAYS)]
    days: list[list[float]] = []
    scaled_days = 0
    for x in year_dates:
        if x in filled:
            days.append(filled[x])
        else:
            level = base_daily * factors[x.month - 1]
            days.append([s * level for s in shape])
            scaled_days += 1

    days_found = len(readings)
    real_kwh = sum(sum(v for v in day if v is not None) for day in readings.values())
    annual = sum(sum(day) for day in days)
    confidence = "high" if days_found >= 330 else "medium" if days_found >= 90 else "low"

    return ParseResult(
        days=days,
        inferred_rate=rate,
        days_count=days_found,
        total_kwh=round(real_kwh, 3),
        daily_avg_kwh=round(annual / MAX_DAYS, 3),
        annual_kwh_estimate=round(annual, 1),
        dates=year_dates,
        coverage={
            "has_dates": True,
            "first_date": first.isoformat(),
            "last_date": last.isoformat(),
            "days_found": days_found,
            "complete_days": len(complete),
            "partial_days_filled": partial_days,
            "missing_days_filled": missing_days,
            "half_hours_filled": slots_filled,
            "days_scaled_from_estimate": scaled_days,
            "days_dropped_older_than_a_year": dropped_days,
        },
        confidence=confidence,
        readings=readings,
    )


def merge_parse_results(results: list[ParseResult], heating: str = "gas") -> ParseResult:
    """Merge several files. Dated files are combined by date; a later file wins where they overlap."""
    if not results:
        raise ValueError("No files to merge.")
    if len(results) == 1:
        return results[0]

    rates = [r.inferred_rate for r in results if r.inferred_rate is not None]
    rate = round(sum(rates) / len(rates), 4) if rates else None

    if all(r.dates is not None and r.readings for r in results):
        combined: dict[date, list[float | None]] = {}
        for r in results:
            for d, day in r.readings.items():
                cur = combined.setdefault(d, [None] * SLOTS)
                for i, v in enumerate(day):
                    if v is not None:
                        cur[i] = v
        return build_year(combined, rate, heating)

    all_days: list[list[float]] = []
    for r in results:
        if r.dates is None:
            all_days.extend(r.days)
        else:   # dated file merged with an undated one: use only its real days
            all_days.extend([[v or 0.0 for v in day] for _, day in sorted(r.readings.items())])
    flat = [v for day in all_days for v in day]
    return _parse_undated(flat, rate)
