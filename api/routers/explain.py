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
    annual_kwh:    float
    property_type: str  = "semi"
    bedrooms:      int  = 3
    postcode:      str  = ""
    unit_rate_p:   float = 28.16
    best_scenario: str  = "battery"
    scenarios:     dict[str, Any] = {}


def _build_prompt(req: ExplainRequest) -> str:
    prop_label = {
        "flat": "flat", "terraced": "terraced house",
        "semi": "semi-detached house", "detached": "detached house",
    }.get(req.property_type, "home")

    postcode_note = f" in {req.postcode.upper()}" if req.postcode.strip() else ""

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

    return f"""You are a friendly, expert home energy advisor for UK homeowners. A customer has received results from our battery and solar savings calculator. Write a concise, engaging explanation (4–6 sentences) of why the recommended option is the best choice for this specific household. Use concrete numbers from the results. Write in plain English — no bullet points, no headers, no jargon. Address the homeowner directly (use "you" and "your").

Customer profile:
- Property: {req.bedrooms}-bedroom {prop_label}{postcode_note}
- Annual electricity use: {round(req.annual_kwh):,} kWh/year
- Current electricity rate: {req.unit_rate_p}p/kWh
- Recommended option: {best_label}

Results for all three options:
Battery Only:
{fmt_scen('battery')}

Solar Only:
{fmt_scen('solar')}

Solar + Battery:
{fmt_scen('solar_battery')}

Write the explanation now. Cover: (1) why the recommended option suits this household's consumption and property type, (2) the key financial benefit (saving per year and payback period), (3) briefly how the other options compare, (4) if the carbon saving is over 200 kg/yr, mention it with a relatable equivalence. Keep it to 4–6 sentences. Do not start with "I" or "As an"."""


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
