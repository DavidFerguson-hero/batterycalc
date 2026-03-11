"""
CSV parser — accepts the same format as the existing HTML tool:
  - Column: 'Electricity consumption (kWh)'  (required)
  - Column: 'Electricity cost (£)'           (optional — infers rate)
  - Column: 'Timestamp' or similar           (optional — used for ordering)

Accepts multi-day files or multiple single-day files.
Returns:
  days       list[list[float]]  — 48 values per day
  rate       float | None       — inferred unit rate (£/kWh), or None
"""
from __future__ import annotations
import io
import math
import pandas as pd
from dataclasses import dataclass


@dataclass
class ParseResult:
    days: list[list[float]]
    inferred_rate: float | None
    days_count: int
    total_kwh: float
    daily_avg_kwh: float
    annual_kwh_estimate: float


_CONSUMPTION_ALIASES = [
    "electricity consumption (kwh)",
    "consumption (kwh)",
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


def _find_col(columns: list[str], aliases: list[str]) -> str | None:
    lower = {c.lower().strip(): c for c in columns}
    for alias in aliases:
        if alias in lower:
            return lower[alias]
    return None


def parse_csv_bytes(raw: bytes) -> ParseResult:
    """Parse a single CSV file's bytes into daily slot arrays."""
    df = pd.read_csv(io.BytesIO(raw))

    cons_col = _find_col(list(df.columns), _CONSUMPTION_ALIASES)
    if cons_col is None:
        raise ValueError(
            f"Could not find consumption column. Expected one of: {_CONSUMPTION_ALIASES}. "
            f"Found: {list(df.columns)}"
        )

    cost_col = _find_col(list(df.columns), _COST_ALIASES)

    values = pd.to_numeric(df[cons_col], errors="coerce").fillna(0.0).tolist()
    costs = (
        pd.to_numeric(df[cost_col], errors="coerce").fillna(0.0).tolist()
        if cost_col else None
    )

    # Group into 48-slot days
    days: list[list[float]] = []
    n = len(values)
    for start in range(0, n, 48):
        chunk = values[start : start + 48]
        if len(chunk) < 48:
            chunk += [0.0] * (48 - len(chunk))
        days.append(chunk)

    # Infer rate from cost/consumption ratio
    inferred_rate: float | None = None
    if costs:
        total_kwh = sum(values)
        total_cost = sum(costs)
        if total_kwh > 0:
            raw_rate = total_cost / total_kwh
            # Sanity check: plausible UK rate 5p–80p
            if 0.05 <= raw_rate <= 0.80:
                inferred_rate = round(raw_rate, 4)

    total_kwh = sum(values)
    n_days = len(days)
    daily_avg = total_kwh / n_days if n_days else 0.0

    return ParseResult(
        days=days,
        inferred_rate=inferred_rate,
        days_count=n_days,
        total_kwh=round(total_kwh, 3),
        daily_avg_kwh=round(daily_avg, 3),
        annual_kwh_estimate=round(daily_avg * 365, 1),
    )


def merge_parse_results(results: list[ParseResult]) -> ParseResult:
    """Merge multiple single-file parse results into one."""
    all_days: list[list[float]] = []
    all_rates: list[float] = []

    for r in results:
        all_days.extend(r.days)
        if r.inferred_rate is not None:
            all_rates.append(r.inferred_rate)

    inferred = round(sum(all_rates) / len(all_rates), 4) if all_rates else None
    total_kwh = sum(sum(d) for d in all_days)
    n_days = len(all_days)
    daily_avg = total_kwh / n_days if n_days else 0.0

    return ParseResult(
        days=all_days,
        inferred_rate=inferred,
        days_count=n_days,
        total_kwh=round(total_kwh, 3),
        daily_avg_kwh=round(daily_avg, 3),
        annual_kwh_estimate=round(daily_avg * 365, 1),
    )
