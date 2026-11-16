"""
POST /api/v2/assess — one request with all the inputs, one response with everything the
homeowner results page needs (task 1.9). Contract: models/assess.py, docs/api-v2.md.

Send JSON for the estimate route, or multipart/form-data for the upload route:
an "inputs" part holding the same JSON, plus one or more CSV "files".
Stateless: nothing is cached, and uploaded data is processed in memory only.
"""
from __future__ import annotations

import json
from dataclasses import replace

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from engine.costs import battery_price, context_costs, fair_price, load_costs, price_range_for
from engine.csv_parser import ParseResult, merge_parse_results, parse_csv_bytes
from engine.extra_loads import EVSettings, HeatPumpSettings, apply_extra_loads
from engine.lifetime import BORDERLINE_SHARE, WORTH_IT_SHARE, lifetime_finance
from engine.optimiser import build_opt_matrix
from engine.profile_estimator import make_parse_result
from engine.simulator import IMPLIED_RATE, calc_day_flows, run_simulation
from engine.size_comparison import compare_sizes, options_from_matrix
from engine.tariff_check import tariff_check
from engine.tariffs import TARIFFS, TARIFFS_CHECKED
from models.assess import AssessRequest, AssessResponse, UsageCheckResponse
from routers.analyse import _pay_back_levers

router = APIRouter(tags=["v2"])

DEFAULT_RATE_P = IMPLIED_RATE * 100


def _bad(msg: str, code: int = 422):
    raise HTTPException(status_code=code, detail=msg)


async def _read_request(request: Request) -> tuple[AssessRequest, list[bytes]]:
    ctype = request.headers.get("content-type", "")
    files: list[bytes] = []
    try:
        if ctype.startswith("multipart/form-data"):
            form = await request.form()
            raw = form.get("inputs")
            if raw is None:
                _bad('Multipart requests need an "inputs" part holding the JSON inputs.')
            req = AssessRequest.model_validate_json(raw if isinstance(raw, str) else await raw.read())
            for f in form.getlist("files"):
                files.append(await f.read())
        else:
            req = AssessRequest.model_validate(await request.json())
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=json.loads(e.json(include_url=False)))
    except json.JSONDecodeError:
        _bad("The request body isn't valid JSON.")
    return req, files


def _usage(req: AssessRequest, files: list[bytes]) -> ParseResult:
    u = req.usage
    if u.route == "estimate":
        if u.annual_kwh is None:
            _bad("usage.annual_kwh is required for the estimate route.")
        if files:
            _bad('Files were sent but usage.route is "estimate".')
        rate_p = req.tariff.unit_rate_p or DEFAULT_RATE_P
        return make_parse_result(u.annual_kwh, u.property_type, rate_p, u.heating_type)
    if not files:
        _bad('The upload route needs at least one CSV in the "files" part.')
    try:
        return merge_parse_results([parse_csv_bytes(f, u.heating_type) for f in files], u.heating_type)
    except ValueError as e:
        _bad(str(e))


def _with_loads(parse: ParseResult, req: AssessRequest) -> ParseResult:
    if req.ev.status == "none" and req.heat_pump.status == "none":
        return parse
    try:
        res = apply_extra_loads(
            parse.days, parse.dates,
            EVSettings(**req.ev.model_dump()), HeatPumpSettings(**req.heat_pump.model_dump()),
            route=req.usage.route, property_type=req.usage.property_type,
        )
    except ValueError as e:
        _bad(str(e))
    return replace(parse, days=res.days, extra_loads={
        "ev": req.ev.model_dump(), "heat_pump": req.heat_pump.model_dump(), **res.summary()})


def _average(days: list[list[float]]) -> list[float]:
    return [sum(d[i] for d in days) / len(days) for i in range(48)]


def _day(label, load, tariff, cap, rate_kw, eff) -> dict:
    f = calc_day_flows(load, tariff, cap, rate_kw, eff, None)
    return {
        "label": label,
        "load": [round(v, 4) for v in load],
        "grid_to_battery": f["grid_to_batt"],
        "from_battery": f["from_battery"],
        "grid_to_home": f["grid_to_load"],
        "battery_level": f["soc_profile"],
    }


def _day_in_life(parse: ParseResult, tariff, cap, rate_kw, eff) -> dict:
    out = {"average": _day("Average day", _average(parse.days), tariff, cap, rate_kw, eff),
           "summer": None, "winter": None}
    if parse.dates:
        for key, months, label in (("summer", {6, 7, 8}, "Summer day (Jun–Aug average)"),
                                   ("winter", {12, 1, 2}, "Winter day (Dec–Feb average)")):
            sel = [d for d, x in zip(parse.days, parse.dates) if x.month in months]
            if sel:
                out[key] = _day(label, _average(sel), tariff, cap, rate_kw, eff)
    return out


@router.post(
    "/v2/assess",
    response_model=AssessResponse,
    openapi_extra={"requestBody": {"required": True, "content": {
        "application/json": {"schema": AssessRequest.model_json_schema()},
        "multipart/form-data": {"schema": {"type": "object", "required": ["inputs"], "properties": {
            "inputs": {"type": "string", "description": "AssessRequest as JSON"},
            "files": {"type": "array", "items": {"type": "string", "format": "binary"}},
        }}},
    }}},
)
async def assess(request: Request) -> AssessResponse:
    req, files = await _read_request(request)
    b, t = req.battery, req.tariff
    if t.current_tariff_key and t.current_tariff_key not in TARIFFS:
        _bad(f"Unknown current tariff: {t.current_tariff_key}", 400)
    if b.tariff_key and b.tariff_key not in TARIFFS:
        _bad(f"Unknown tariff: {b.tariff_key}", 400)

    parse = _with_loads(_usage(req, files), req)
    days = parse.days
    unit_rate = (t.unit_rate_p / 100) if t.unit_rate_p else (parse.inferred_rate or IMPLIED_RATE)
    eff = b.efficiency_pct / 100
    export = t.export_rate_p / 100

    def check(cap):
        return tariff_check(days, unit_rate, t.standing_charge_p, cap, b.max_charge_rate_kw, eff,
                            export_rate=export, current_tariff_key=t.current_tariff_key)

    # Size comparison across the standard sizes (best value = highest likely lifetime net gain).
    first_cap = b.size_kwh or 10.0
    tc = check(first_cap)
    matrix = build_opt_matrix(
        days=days, current_rate=unit_rate, max_rate_kw=b.max_charge_rate_kw, efficiency=eff,
        selected_cap_kwh=first_cap,
        selected_cost_gbp=b.price_gbp or battery_price(first_cap)["typical"],
        current_sc_pd=t.standing_charge_p,
    )
    sizes = compare_sizes(
        options_from_matrix(matrix, {k: v.name for k, v in TARIFFS.items()}, tc["current"]),
        tc["best_no_battery"]["annual_cost"],
    )

    # The battery to assess: the one asked about, or the best-value size and its tariff.
    if b.size_kwh:
        cap, chosen_by = b.size_kwh, "you"
    else:
        cap, chosen_by = sizes["best_value"]["kwh"], "best_value"
    if cap != first_cap:
        tc = check(cap)
    price = b.price_gbp or round(battery_price(cap)["typical"], -1)
    if b.tariff_key:
        tkey = b.tariff_key
    elif chosen_by == "best_value":
        tkey = sizes["best_value"]["tariff_key"]
    else:
        tkey = tc["best_with_battery"]["key"]
    tariff = TARIFFS.get(tkey) or TARIFFS["currentFlat"]   # "current" (a flat rate) can't use a battery

    sim = run_simulation(tariff, cap, b.max_charge_rate_kw, eff, days, unit_rate,
                         t.standing_charge_p, export_rate=export)
    battery_saving = tc["best_no_battery"]["annual_cost"] - sim.ann_cost_with_battery
    lt = lifetime_finance(price, battery_saving, *price_range_for(cap, price))
    life = lt.assumptions.battery_life_years

    levers = None
    if lt.verdict == "not_yet":
        levers = _pay_back_levers(parse, tc, tkey, battery_saving, price, lt.verdict, unit_rate,
                                  t.standing_charge_p, cap, b.max_charge_rate_kw, eff, export,
                                  t.current_tariff_key)
        for k in ("switch_tariff", "add_ev"):
            if levers.get(k) and "tariff_key" not in levers[k]:
                levers[k]["tariff_key"] = tkey
                levers[k]["tariff_name"] = tariff.name

    def avg_saving(case):
        c = lt.cases[case]
        return (c.lifetime_net_gain + c.installed_cost) / life

    ld = lt.to_dict()
    a = ld["assumptions"]
    label = next((r["label"] for r in sizes["all_sizes"] if r["kwh"] == cap), f"{cap:g} kWh")

    return AssessResponse(
        usage={
            "route": req.usage.route,
            "annual_kwh": round(sum(map(sum, days)) * 365 / len(days), 1),
            "days_modelled": len(days),
            "days_found": parse.days_count if req.usage.route == "upload" else None,
            "confidence": parse.confidence or "low",
            "coverage": parse.coverage,
            "extra_loads": parse.extra_loads,
            "unit_rate_p": round(unit_rate * 100, 2),
        },
        recommendation={
            "battery_kwh": cap, "battery_label": label, "tariff_key": tkey,
            "tariff_name": tariff.name if tkey in TARIFFS else tc["current"]["name"],
            "installed_price": price, "chosen_by": chosen_by,
        },
        verdict=lt.verdict,
        headline={
            "installed_cost": {"low": ld["installed_cost"]["low"], "likely": ld["installed_cost"]["typical"],
                               "high": ld["installed_cost"]["high"]},
            "year1_battery_saving": round(battery_saving, 2),
            "average_yearly_saving": {"low": round(avg_saving("pessimistic"), 2),
                                      "likely": round(avg_saving("likely"), 2),
                                      "high": round(avg_saving("optimistic"), 2)},
            "payback_years": ld["payback_years"],
            "lifetime_net_gain": ld["lifetime_net_gain"],
        },
        break_even={"years": list(range(life + 1)), **ld["cash_by_year"]},
        saving_breakdown=sim.saving_breakdown(),
        tariff_check=tc,
        size_comparison=sizes,
        what_would_make_it_pay_back=levers,
        day_in_life=_day_in_life(parse, tariff, cap, b.max_charge_rate_kw, eff),
        fair_price=fair_price(cap, price),
        context_costs=context_costs(),
        assumptions={
            **{k: a[k] for k in ("battery_life_years", "warranty_years", "capacity_loss_pct_per_year",
                                 "price_growth_pct", "inverter_replacement_year",
                                 "inverter_replacement_cost")},
            "verdict_thresholds": {"worth_it_share_of_warranty": WORTH_IT_SHARE,
                                   "borderline_share_of_warranty": BORDERLINE_SHARE},
            "costs_as_of": load_costs()["as_of"],
            "tariffs_checked": TARIFFS_CHECKED,
        },
    )


MAX_FILES = 20
MAX_FILE_BYTES = 10 * 1024 * 1024   # a year of half-hourly data is well under 1 MB


@router.post(
    "/v2/usage/check",
    response_model=UsageCheckResponse,
    openapi_extra={"requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
        "type": "object", "required": ["files"],
        "properties": {"files": {"type": "array", "items": {"type": "string", "format": "binary"}}},
    }}}}},
)
async def usage_check(request: Request) -> UsageCheckResponse:
    """
    Read uploaded CSV files and say what was found (dates, days, gaps, confidence),
    without running the assessment. In memory only; nothing is stored.
    """
    if not request.headers.get("content-type", "").startswith("multipart/form-data"):
        _bad('Send the CSV files as multipart/form-data in a "files" part.')
    form = await request.form()
    uploads = form.getlist("files")
    if not uploads:
        _bad('Add at least one CSV in the "files" part.')
    if len(uploads) > MAX_FILES:
        _bad(f"Please upload {MAX_FILES} files or fewer.")

    files, parsed = [], []
    for f in uploads:
        name = getattr(f, "filename", None) or "file"
        raw = await f.read()
        if len(raw) > MAX_FILE_BYTES:
            files.append({"name": name, "ok": False, "error": "This file is too big. A year of half-hourly readings is usually under 1 MB."})
            continue
        try:
            p = parse_csv_bytes(raw)
        except ValueError as e:
            files.append({"name": name, "ok": False, "error": str(e)})
            continue
        except Exception:
            files.append({"name": name, "ok": False, "error": "We couldn't read this file. Please check it's a CSV export of your usage."})
            continue
        cov = p.coverage or {}
        files.append({"name": name, "ok": True, "days_found": p.days_count,
                      "first_date": cov.get("first_date"), "last_date": cov.get("last_date")})
        parsed.append(p)

    combined = None
    if parsed:
        m = merge_parse_results(parsed)
        c = m.coverage or {}
        combined = {
            "has_dates": bool(c.get("has_dates")),
            "first_date": c.get("first_date"),
            "last_date": c.get("last_date"),
            "days_found": m.days_count,
            "complete_days": c.get("complete_days"),
            "partial_days_filled": c.get("partial_days_filled"),
            "missing_days_filled": c.get("missing_days_filled"),
            "half_hours_filled": c.get("half_hours_filled"),
            "days_scaled_from_estimate": c.get("days_scaled_from_estimate"),
            "days_dropped_older_than_a_year": c.get("days_dropped_older_than_a_year"),
            "confidence": m.confidence or "low",
            "annual_kwh_estimate": m.annual_kwh_estimate,
            "inferred_unit_rate_p": round(m.inferred_rate * 100, 2) if m.inferred_rate else None,
        }
    return UsageCheckResponse(files=files, combined=combined)
