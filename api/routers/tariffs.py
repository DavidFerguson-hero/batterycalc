"""
GET /api/tariffs — return the current tariff catalogue.
"""
from fastapi import APIRouter
from engine.tariffs import TARIFFS

router = APIRouter(tags=["tariffs"])


@router.get("/tariffs")
async def list_tariffs():
    return [
        {
            "key": t.key,
            "name": t.name,
            "supplier": t.supplier,
            "description": t.description,
            "color": t.color,
            "standing_charge_pence": round(t.standing_charge * 100, 2),
            "is_flat_rate": t.is_flat_rate,
            "is_dynamic": t.is_dynamic,
            "slot_rates_pence": [round(r * 100, 3) for r in t.slot_rates],
            "export_rate_pence": round(t.export_rate * 100, 2),
        }
        for t in TARIFFS.values()
    ]
