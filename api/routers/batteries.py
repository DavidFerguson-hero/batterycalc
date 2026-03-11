"""
GET /api/batteries — return the standard battery size catalogue with indicative prices.
"""
from fastapi import APIRouter
from engine.tariffs import OPT_BATTERIES, DEFAULT_COSTS

router = APIRouter(tags=["batteries"])


@router.get("/batteries")
async def list_batteries():
    return {
        "standard_sizes": OPT_BATTERIES,
        "default_costs": DEFAULT_COSTS,
        "note": "Prices are indicative installed costs (Q1 2026). Always obtain quotes.",
    }
