"""
GET /api/batteries — the standard battery sizes and indicative installed prices (from api/data/costs.json).
"""
from fastapi import APIRouter

from engine.costs import load_costs, standard_batteries, slider_costs

router = APIRouter(tags=["batteries"])


@router.get("/batteries")
async def list_batteries():
    # default_costs keyed as strings for JSON compatibility (used by the classic calculator)
    return {
        "standard_sizes": standard_batteries(),
        "default_costs": {str(k): v for k, v in slider_costs().items()},
        "as_of": load_costs()["as_of"],
        "note": "Typical installed prices, VAT included at the current 0%. Always get quotes.",
    }
