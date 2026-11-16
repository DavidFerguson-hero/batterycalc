"""
Accuracy check (task 3.1): how close is the estimate route to the answer from real meter data?

For each home, the same request goes through /api/v2/assess twice:
  - upload route: the home's real half-hourly readings
  - estimate route: only the home's yearly total (so this tests our assumed daily and
    seasonal pattern of use, not the guess of yearly use from the home's details)
Everything else (tariff, unit rate, standing charge) is the same, and both answers are compared:
the battery each route recommends, year-1 saving and payback, plus the year-1 saving
of a 10 kWh battery on both, which compares like with like.

Data is read in memory from wherever it lives (never from or into this repo) and only
anonymised summary figures are printed. Run from api/:

  # Low Carbon London 2013 (4TU.ResearchData, CC BY 4.0): one column per home, kWh per half hour
  python scripts/accuracy_check.py --lcl /path/to/LCL_2013.csv --homes 30

  # Your own smart meter exports (any format the upload route accepts), one file per home
  python scripts/accuracy_check.py --csv /path/to/home1.csv /path/to/home2.csv

Add --markdown to print the table in Markdown.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient  # noqa: E402

from engine.csv_parser import parse_csv_bytes  # noqa: E402
from main import app  # noqa: E402

CLIENT = TestClient(app)
TARIFF = {"unit_rate_p": 28.16, "standing_charge_p": 53.0}   # same flat starting tariff for every home
COMPARE_KWH = 10.0


@dataclass
class Home:
    label: str
    csv: bytes             # half-hourly readings as a CSV the upload route accepts
    annual_kwh: float


@dataclass
class Result:
    label: str
    annual_kwh: float
    real: dict
    est: dict

    @staticmethod
    def _at(a: dict, kwh: float) -> dict:
        return next(s for s in a["size_comparison"]["all_sizes"] if s["kwh"] == kwh)

    @property
    def same_size_saving(self) -> tuple[float, float]:
        return self._at(self.real, COMPARE_KWH)["year1_battery_saving"], self._at(self.est, COMPARE_KWH)["year1_battery_saving"]


# ── Loading homes ─────────────────────────────────────────────────────────────

def lcl_homes(path: Path, n: int, seed: int = 2013) -> list[Home]:
    """
    n homes from the LCL 2013 file with near-complete readings, spread evenly across yearly use.
    Timestamps in the file are GMT and mark the END of each half hour.
    """
    df = pd.read_csv(path, dtype={"DateTime": str}, float_precision="high")
    times = pd.to_datetime(df.pop("DateTime").str.slice(0, 19), format="%Y-%m-%d %H:%M:%S") - pd.to_timedelta(30, unit="min")
    data = df.to_numpy(dtype=np.float32)
    present = np.isfinite(data).mean(axis=0)
    totals = np.nansum(data, axis=0)
    ok = np.where((present >= 0.99) & (totals >= 1000) & (totals <= 15000))[0]
    ok = ok[np.argsort(totals[ok])]
    # Even spread from the 5th to the 95th centile of use, so the sample isn't all average homes.
    picks = ok[np.linspace(len(ok) * 0.05, len(ok) * 0.95 - 1, n).astype(int)]
    rng = np.random.default_rng(seed)
    rng.shuffle(picks)
    stamps = times.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    homes = []
    for i, col in enumerate(picks, 1):
        vals = data[:, col]
        keep = np.isfinite(vals)
        csv = pd.DataFrame({"Start": stamps[keep], "Consumption (kWh)": np.round(vals[keep], 3)}).to_csv(index=False)
        homes.append(Home(f"L{i:02d}", csv.encode(), float(totals[col])))
    return homes


def csv_homes(paths: list[Path]) -> list[Home]:
    homes = []
    for i, p in enumerate(paths, 1):
        raw = p.read_bytes()
        parsed = parse_csv_bytes(raw)
        homes.append(Home(f"H{i:02d}", raw, parsed.annual_kwh_estimate))
    return homes


# ── Running both routes ───────────────────────────────────────────────────────

def assess_both(h: Home) -> Result:
    real = CLIENT.post("/api/v2/assess", data={"inputs": json.dumps({"usage": {"route": "upload"}, "tariff": TARIFF})},
                       files=[("files", ("usage.csv", h.csv, "text/csv"))])
    real.raise_for_status()
    kwh = min(20000, max(500, round(real.json()["usage"]["annual_kwh"])))
    est = CLIENT.post("/api/v2/assess", json={"usage": {"route": "estimate", "annual_kwh": kwh}, "tariff": TARIFF})
    est.raise_for_status()
    return Result(h.label, kwh, real.json(), est.json())


# ── Report ────────────────────────────────────────────────────────────────────

def _yrs(y):
    return "never" if y is None else f"{y:.1f}"


def _cap(y, life=15):
    return life + 5 if y is None else y      # "never pays back" counted as 20 years for the averages


def report(results: list[Result], markdown: bool) -> str:
    head = ["Home", "kWh/yr", "Size real/est", "Tariff same?", "Yr-1 saving real/est", "Payback real/est (yrs)",
            "Verdict real/est", f"{COMPARE_KWH:g} kWh saving real/est", "Gap"]
    rows, gaps, pay_gaps, same_verdict, same_size = [], [], [], 0, 0
    for r in results:
        a, b = r.real["recommendation"], r.est["recommendation"]
        ha, hb = r.real["headline"], r.est["headline"]
        s_real, s_est = r.same_size_saving
        gap = (s_est - s_real) / s_real if s_real else 0.0
        gaps.append(gap)
        pay_gaps.append(_cap(hb["payback_years"]["likely"]) - _cap(ha["payback_years"]["likely"]))
        same_verdict += r.real["verdict"] == r.est["verdict"]
        same_size += a["battery_kwh"] == b["battery_kwh"]
        rows.append([
            r.label, f"{r.annual_kwh:,.0f}", f"{a['battery_kwh']:g} / {b['battery_kwh']:g}",
            "yes" if a["tariff_key"] == b["tariff_key"] else f"{a['tariff_name']} / {b['tariff_name']}",
            f"£{ha['year1_battery_saving']:,.0f} / £{hb['year1_battery_saving']:,.0f}",
            f"{_yrs(ha['payback_years']['likely'])} / {_yrs(hb['payback_years']['likely'])}",
            f"{r.real['verdict']} / {r.est['verdict']}",
            f"£{s_real:,.0f} / £{s_est:,.0f}", f"{gap:+.0%}",
        ])
    n = len(results)
    abs_gaps = [abs(g) for g in gaps]
    abs_pay = [abs(p) for p in pay_gaps]
    summary = [
        f"Homes: {n}",
        f"Same verdict: {same_verdict} of {n}. Same recommended size: {same_size} of {n}.",
        f"{COMPARE_KWH:g} kWh year-1 saving, estimate vs real: median gap {statistics.median(gaps):+.0%}, "
        f"median size of gap {statistics.median(abs_gaps):.0%}, within ±10% for "
        f"{sum(g <= 0.10 for g in abs_gaps)} of {n}, within ±20% for {sum(g <= 0.20 for g in abs_gaps)} of {n}, "
        f"largest {max(abs_gaps):.0%}.",
        f"Payback (each route's own recommendation; 'never' counted as 20 years): median gap "
        f"{statistics.median(pay_gaps):+.1f} years, median size of gap {statistics.median(abs_pay):.1f} years, "
        f"within 2 years for {sum(p <= 2 for p in abs_pay)} of {n}.",
    ]
    if markdown:
        lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
        lines += ["| " + " | ".join(r) + " |" for r in rows]
    else:
        widths = [max(len(x) for x in col) for col in zip(head, *rows)]
        fmt = "  ".join(f"{{:<{w}}}" for w in widths)
        lines = [fmt.format(*head)] + [fmt.format(*r) for r in rows]
    return "\n".join(lines + [""] + summary)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--lcl", type=Path, help="LCL_2013.csv (wide: DateTime then one column per home)")
    src.add_argument("--csv", type=Path, nargs="+", help="smart meter export(s), one per home")
    ap.add_argument("--homes", type=int, default=30, help="how many LCL homes to sample (default 30)")
    ap.add_argument("--markdown", action="store_true")
    args = ap.parse_args()

    homes = lcl_homes(args.lcl, args.homes) if args.lcl else csv_homes(args.csv)
    results = []
    for h in homes:
        results.append(assess_both(h))
        print(f"  {h.label} done", file=sys.stderr)
    print(report(results, args.markdown))


if __name__ == "__main__":
    main()
