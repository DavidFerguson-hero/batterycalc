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
            "The customer already has a complete solar + battery system. "
            "Focus on what their system achieves today — the annual saving, "
            "carbon reduction, and how well their existing investment is performing. "
            "If the tariff could be optimised, mention it. Do not recommend buying "
            "more equipment — they already have a great setup."
        )
    elif hs:
        existing = "solar panels already installed (no battery yet)"
        framing  = (
            "The customer already has solar panels. The two options shown are their "
            "solar baseline (what they already have) and the upgrade (adding a battery). "
            "The financials for 'Add a battery' show only the INCREMENTAL cost and saving "
            "on top of their existing solar — not the total system cost. "
            "Frame the recommendation as the right next step for their solar investment, "
            "emphasising that the battery cost and payback are on top of what they already earn."
        )
    elif hb:
        existing = "a home battery already installed (no solar yet)"
        framing  = (
            "The customer already has a home battery. The two options shown are their "
            "battery baseline (what they already have) and the upgrade (adding solar panels). "
            "The financials for 'Add solar panels' show only the INCREMENTAL cost and saving "
            "on top of their existing battery savings — not the total system cost. "
            "Frame the recommendation as the right next step to complement their battery, "
            "emphasising that solar would work alongside what they already have."
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

Instructions: {"Cover (1) how their existing setup is already performing and what it earns them, (2) whether there are any tariff improvements that could increase returns — be specific about the tariff and the extra saving, (3) the carbon impact. 3–5 sentences. Do not recommend buying more equipment." if (req.context_has_solar and req.context_has_battery) else "Cover (1) what their existing setup already earns them, (2) why adding the recommended upgrade makes financial sense — use the incremental cost and incremental saving (not total system cost), (3) the payback period for the upgrade investment, (4) if carbon saving exceeds 200 kg/yr mention a relatable equivalence. 4–6 sentences. Do not start with 'I' or 'As an'." if (req.context_has_solar or req.context_has_battery) else "Cover (1) why the recommended option suits this household's consumption and property type, (2) the key financial benefit (saving per year and payback period), (3) briefly contrast with the other options shown, (4) if carbon saving exceeds 200 kg/yr include a relatable equivalence. 4–6 sentences. Do not start with 'I' or 'As an'."}"""


def scenarios_section(req: ExplainRequest, fmt_scen) -> str:
    hs, hb = req.context_has_solar, req.context_has_battery
    if hs and hb:
        labels = [
            ("Your current setup (solar + battery)", "solar_battery"),
        ]
    elif hs:
        labels = [
            ("Your solar today (current baseline)", "solar"),
            ("Add a battery (incremental cost & saving only)", "solar_battery"),
        ]
    elif hb:
        labels = [
            ("Your battery today (current baseline)", "battery"),
            ("Add solar panels (incremental cost & saving only)", "solar_battery"),
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
