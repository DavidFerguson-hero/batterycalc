"""
POST /api/v2/summary — a short, plain-English summary of an assessment, written by
Claude (task 2.9). The front end sends back the AssessResponse it was given; only the
headline figures go into the prompt (never the half-hourly profiles), and nothing is
stored or logged.

Guard rails:
- The model may only quote £ figures that are in the facts it was given; a reply with any
  other £ amount is discarded (502), so a made-up number never reaches the page.
- Refusals, truncated replies and API errors return an error; the page simply hides the summary.
- A small per-address limit keeps a public endpoint from running up the API bill.
"""
from __future__ import annotations

import os
import re
import threading
import time
from collections import deque
from typing import Optional

import anthropic
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from models.assess import AssessResponse

router = APIRouter(tags=["summary"])

MODEL = "claude-haiku-5-5"
MAX_TOKENS = 2000
RATE_LIMIT = 30            # summaries per address
RATE_WINDOW_S = 3600       # per hour

SYSTEM_PROMPT = """You write a short summary of a home battery assessment for a UK homeowner.

Write one paragraph of 3 to 5 sentences in plain British English, addressed to the homeowner as "you". No headings, bullet points or markdown.

Cover, in this order:
1. The verdict and the main reason for it (how the payback compares with the warranty).
2. The battery and tariff that work best, and roughly what it costs.
3. The most useful thing to know or do next: switching tariff first if that is flagged, what price would make it pay back if that is given, or how sure the answer is if it's an estimate.

Rules:
- Use only the facts given. Quote any £ figure exactly as written in the facts and never work out new ones (no differences, totals or percentages of your own).
- Agree with the verdict given; don't soften or strengthen it.
- Spell out any acronym the first time you use it.
- Don't recommend specific installers or brands, and don't call it financial advice.
- Don't start with "I", "As", "Based on" or "Great"."""


# ── Facts for the prompt ──────────────────────────────────────────────────────

def _gbp(n: float) -> str:
    r = round(n)
    return f"−£{abs(r):,}" if r < 0 else f"£{r:,}"


def _years(y: Optional[float], life: int) -> str:
    return f"not within {life} years" if y is None else f"{round(y, 1):g} years"


VERDICT_WORDS = {
    "worth_it": "Worth it (pays back well within the warranty)",
    "borderline": "Borderline (pays back, but only towards the end of the warranty)",
    "not_yet": "Not yet (unlikely to pay back within the warranty at today's prices)",
}


def build_facts(a: AssessResponse) -> str:
    """The figures the model may use, as plain labelled lines."""
    h, r, tc, s = a.headline, a.recommendation, a.tariff_check, a.assumptions
    life, warranty = s.battery_life_years, s.warranty_years
    cur = tc.current or {}
    lines = [
        f"Verdict: {VERDICT_WORDS[a.verdict]}",
        f"Warranty: {warranty} years. Battery life modelled: {life} years.",
        f"{'Best-value battery' if r.chosen_by == 'best_value' else 'Battery the homeowner chose'}: "
        f"{r.battery_label} on the {r.tariff_name} tariff, about {_gbp(r.installed_price)} fitted "
        f"(typically {_gbp(h.installed_cost.low)} to {_gbp(h.installed_cost.high)}).",
        f"Saving in the first year, on top of the best tariff without a battery: {_gbp(h.year1_battery_saving)}.",
        f"Pays back in: {_years(h.payback_years.likely, life)} "
        f"(range {_years(h.payback_years.low, life)} to {_years(h.payback_years.high, life)}).",
        f"Money ahead after {life} years: {_gbp(h.lifetime_net_gain.likely)} "
        f"(range {_gbp(h.lifetime_net_gain.low)} to {_gbp(h.lifetime_net_gain.high)}).",
        f"Yearly bill now on {cur.get('name', 'their current tariff')}: {_gbp(cur.get('annual_cost_no_battery', 0))}. "
        f"On {tc.best_no_battery.name} without a battery: {_gbp(tc.best_no_battery.annual_cost)}. "
        f"With the battery on {tc.best_with_battery.name}: {_gbp(tc.best_with_battery.annual_cost)}.",
    ]
    if tc.switch_first:
        lines.append(
            f"Switch tariff first: switching alone saves {_gbp(tc.savings.get('switch_tariff_only', 0))} a year, "
            f"which is most of the total possible saving.")
    lv = a.what_would_make_it_pay_back
    if lv and lv.price.price_for_payback_within_warranty is not None:
        lines.append(f"A fitted price of {_gbp(lv.price.price_for_payback_within_warranty)} or less "
                     f"would pay back within the warranty.")
    u = a.usage
    sure = {"high": "based on about a year of their smart meter data",
            "medium": "based on a few months of their smart meter data",
            "low": "based on only a little of their smart meter data, so treat it as rough",
            "estimate": "an estimate from the home's details, not real meter data"}[u.confidence]
    lines.append(f"Electricity use modelled: {round(u.annual_kwh):,} kWh a year; this answer is {sure}.")
    loads = u.extra_loads or {}
    for key, label in (("ev", "electric car"), ("heat_pump", "heat pump")):
        status = (loads.get(key) or {}).get("status")
        if status in ("have", "planning"):
            lines.append(f"Includes {'their' if status == 'have' else 'a planned'} {label}.")
    if u.solar and u.solar.status in ("have", "planning"):
        lines.append(f"Includes {'their' if u.solar.status == 'have' else 'planned'} "
                     f"{u.solar.kwp:g} kWp solar panels (kWp = the panels' peak power).")
    return "\n".join(lines)


_GBP = re.compile(r"£\s?(\d[\d,]*(?:\.\d+)?)")


def pound_figures(text: str) -> set[int]:
    return {round(float(m.replace(",", ""))) for m in _GBP.findall(text)}


def only_known_figures(summary: str, facts: str) -> bool:
    """Every £ amount in the summary must appear in the facts (to the pound)."""
    return pound_figures(summary) <= pound_figures(facts)


# ── Rate limit ────────────────────────────────────────────────────────────────

_hits: dict[str, deque] = {}
_lock = threading.Lock()


def _client_address(request: Request) -> str:
    # Render sits behind a proxy; its address comes first in X-Forwarded-For.
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def _allow(addr: str, now: Optional[float] = None) -> bool:
    now = time.monotonic() if now is None else now
    with _lock:
        q = _hits.setdefault(addr, deque())
        while q and now - q[0] > RATE_WINDOW_S:
            q.popleft()
        if len(q) >= RATE_LIMIT:
            return False
        q.append(now)
        if len(_hits) > 10_000:          # keep memory bounded
            for k in [k for k, v in _hits.items() if not v][:5_000]:
                _hits.pop(k, None)
        return True


# ── The call ──────────────────────────────────────────────────────────────────

_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(timeout=25.0, max_retries=1)
    return _client


def write_summary(facts: str) -> str:
    """Ask Claude for the paragraph. Raises HTTPException when there's nothing safe to show."""
    try:
        response = _get_client().messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            output_config={"effort": "low"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Facts:\n{facts}\n\nWrite the summary."}],
        )
    except anthropic.RateLimitError:
        raise HTTPException(503, "The summary service is busy. Please try again later.")
    except (anthropic.APIStatusError, anthropic.APIConnectionError):
        raise HTTPException(502, "Couldn't write a summary just now.")
    if response.stop_reason != "end_turn":     # refusal, max_tokens, …
        raise HTTPException(502, "Couldn't write a summary just now.")
    text = " ".join(b.text for b in response.content if b.type == "text").strip()
    if not text:
        raise HTTPException(502, "Couldn't write a summary just now.")
    return text


class SummaryResponse(BaseModel):
    summary: str
    model: str


@router.post("/v2/summary", response_model=SummaryResponse)
def summary(body: AssessResponse, request: Request) -> SummaryResponse:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(503, "Summaries aren't switched on.")
    if not _allow(_client_address(request)):
        raise HTTPException(429, "Too many summaries from this address. Please try again later.")
    facts = build_facts(body)
    text = write_summary(facts)
    if not only_known_figures(text, facts):
        raise HTTPException(502, "Couldn't write a summary just now.")
    return SummaryResponse(summary=text, model=MODEL)
