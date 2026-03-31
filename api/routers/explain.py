"""
POST /api/explain — stream a natural-language explanation of the recommendation
using the Anthropic Claude API (claude-haiku-4-5 for speed).
"""
from __future__ import annotations

import json
import os
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(tags=["explain"])


class ExplainRequest(BaseModel):
    annual_kwh:          float
    property_type:       str  = "semi"
    bedrooms:            int  = 3
    postcode:            str  = ""
    unit_rate_p:         float = 28.16
    best_scenario:       str  = "battery"
    scenarios:           dict[str, Any] = {}
    context_has_solar:   bool = False
    context_has_battery: bool = False


def _build_prompt(req: ExplainRequest) -> str:
    prop_label = {
        "flat": "flat", "terraced": "terraced house",
        "semi": "semi-detached house", "detached": "detached house",
    }.get(req.property_type, "home")

    postcode_note = f" in {req.postcode.upper()}" if req.postcode.strip() else ""

    # Describe what the homeowner already has
    hs, hb = req.context_has_solar, req.context_has_battery
    if hs and hb:
        existing = "solar panels and a home battery already installed"
        framing  = (
            "The customer wants to know how their current setup compares to alternatives "
            "and whether switching tariff or changing equipment would improve returns. "
            "The recommended option is their best next move — whether that means keeping "
            "what they have on a better tariff, or making a change."
        )
    elif hs:
        existing = "solar panels already installed (no battery yet)"
        framing  = (
            "The customer wants to know whether adding a battery is worth it. "
            "The recommended option should be framed as the best upgrade step for "
            "their existing solar investment."
        )
    elif hb:
        existing = "a home battery already installed (no solar yet)"
        framing  = (
            "The customer wants to know whether adding solar panels would complement "
            "their battery. The recommended option should be framed as the best next "
            "upgrade to maximise the value of their existing battery."
        )
    else:
        existing = "no solar or battery currently installed"
        framing  = (
            "The customer is starting fresh and wants to know the best system to install. "
            "The recommended option should be framed as their best first investment."
        )

    def fmt_scen(key: str) -> str:
        sc = req.scenarios.get(key, {})
        if not sc or not sc.get("label"):
            return "  (not modelled)"
        lines = [
            f"  Option: {sc.get('label')}",
            f"  Technology: {sc.get('tech', '')}",
            f"  Annual saving: £{round(sc.get('annual_saving') or 0):,}",
            f"  Installed cost: £{round(sc.get('installed_cost') or 0):,}",
            f"  Payback: {sc.get('payback_years', 'N/A')} years",
            f"  10-year ROI: £{round(sc.get('roi_10yr') or 0):,}",
        ]
        carbon = sc.get("carbon") or {}
        if carbon.get("kg_saved_annual", 0) > 0:
            lines.append(
                f"  Carbon saved: {carbon['kg_saved_annual']} kg CO\u2082/yr "
                f"({carbon['pct_reduction']}% reduction)"
            )
        return "\n".join(lines)

    best_label = req.scenarios.get(req.best_scenario, {}).get("label", req.best_scenario)

    return f"""You are a friendly, expert home energy advisor for UK homeowners. A customer has used our energy savings calculator and received personalised results. Write a concise, engaging explanation (4–6 sentences) of why the recommended option is the best choice for this specific household. Use concrete numbers. Write in plain English — no bullet points, no headers, no jargon. Address the homeowner directly ("you" / "your").

Customer profile:
- Property: {req.bedrooms}-bedroom {prop_label}{postcode_note}
- Annual electricity use: {round(req.annual_kwh):,} kWh/year
- Current electricity rate: {req.unit_rate_p}p/kWh
- Existing setup: {existing}
- Recommended option: {best_label}

Context: {framing}

Results for all three options being compared:
{scenarios_section(req, fmt_scen)}

Instructions: Cover (1) the customer's existing situation and why the recommended option is the right next step for them specifically, (2) the key financial benefit (saving per year and payback), (3) briefly contrast with the other options shown, (4) if carbon saving exceeds 200 kg/yr, include a relatable equivalence. 4–6 sentences. Do not start with "I" or "As an"."""


def scenarios_section(req: ExplainRequest, fmt_scen) -> str:
    hs, hb = req.context_has_solar, req.context_has_battery
    if hs and hb:
        labels = [
            ("Your current setup (solar + battery)", "solar_battery"),
            ("Battery only (no solar)", "battery"),
            ("Solar only (no battery)", "solar"),
        ]
    elif hs:
        labels = [
            ("Your solar today (baseline)", "solar"),
            ("Add a battery", "solar_battery"),
            ("Battery only, no solar", "battery"),
        ]
    elif hb:
        labels = [
            ("Your battery today (baseline)", "battery"),
            ("Add solar panels", "solar"),
            ("Solar + your battery", "solar_battery"),
        ]
    else:
        labels = [
            ("Battery only", "battery"),
            ("Solar only", "solar"),
            ("Solar + battery", "solar_battery"),
        ]
    return "\n\n".join(f"{title}:\n{fmt_scen(key)}" for title, key in labels)


async def _stream_explanation(req: ExplainRequest):
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        yield f"data: {json.dumps('[AI explanation unavailable — API key not configured]')}\n\n"
        yield "data: [DONE]\n\n"
        return

    client = anthropic.Anthropic(api_key=api_key)
    prompt = _build_prompt(req)

    try:
        with client.messages.stream(
            model="claude-haiku-4-5-20251001",
            max_tokens=350,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for chunk in stream.text_stream:
                yield f"data: {json.dumps(chunk)}\n\n"
    except Exception as exc:
        yield f"data: {json.dumps('')}\n\n"
    finally:
        yield "data: [DONE]\n\n"


@router.post("/explain")
async def explain(req: ExplainRequest):
    return StreamingResponse(
        _stream_explanation(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
