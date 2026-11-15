"""Task 1.4 — where the battery's saving comes from. Done when the parts sum to the total within £1."""
import pytest
from fastapi.testclient import TestClient

from engine.extra_loads import EVSettings, HeatPumpSettings, apply_extra_loads
from engine.profile_estimator import generate_days, model_year_dates
from engine.simulator import calc_solar_impact, run_simulation
from engine.tariffs import OPT_TARIFF_KEYS, TARIFFS
from main import app

DAYS = generate_days(3500, "semi")

# Same normalised solar shape as the simulator tests, scaled to a 4 kWp annual-average day.
_SOLAR_NORM = [0] * 13 + [
    0.0066, 0.0093, 0.0129, 0.0172, 0.0225, 0.0285, 0.0350, 0.0420, 0.0490, 0.0555, 0.0611,
    0.0655, 0.0683, 0.0692, 0.0683, 0.0655, 0.0611, 0.0555, 0.0490, 0.0420, 0.0350, 0.0285,
    0.0225, 0.0172, 0.0129,
] + [0] * 10
SOLAR = [v * 4.0 * 850 / 365 for v in _SOLAR_NORM]


def parts_sum(b):
    return b["time_shifting"] + b["solar_storage"] + b["other"]


# ── Battery without solar ─────────────────────────────────────────────────────

@pytest.mark.parametrize("tariff_key", OPT_TARIFF_KEYS)
@pytest.mark.parametrize("cap", [5.0, 13.5])
def test_battery_only_parts_sum_to_total(tariff_key, cap):
    sim = run_simulation(TARIFFS[tariff_key], cap, 3.6, 0.9, DAYS, 0.2816, 53.0)
    b = sim.saving_breakdown()
    assert abs(parts_sum(b) - sim.saving_battery_only) < 1.0
    assert b["solar_storage"] == 0.0


def test_battery_only_is_mostly_time_shifting():
    sim = run_simulation(TARIFFS["octopusGo"], 10, 3.6, 0.9, DAYS, 0.2816, 53.0)
    b = sim.saving_breakdown()
    assert b["time_shifting"] == pytest.approx(sim.saving_battery_only, abs=0.01)
    assert b["other"] == 0.0


def test_selling_stored_energy_shows_as_other():
    sim = run_simulation(TARIFFS["octopusGo"], 20, 3.6, 0.9, DAYS, 0.2816, 53.0, export_rate=0.15)
    b = sim.saving_breakdown()
    assert b["other"] == pytest.approx(sim.ann_export_revenue, abs=0.01) and b["other"] > 0
    assert abs(parts_sum(b) - sim.saving_battery_only) < 1.0


def test_with_ev_and_heat_pump_parts_still_sum():
    days = apply_extra_loads(
        DAYS, model_year_dates(),
        EVSettings(status="planning"), HeatPumpSettings(status="planning"),
        route="estimate",
    ).days
    sim = run_simulation(TARIFFS["edfFreePhaseDynamic"], 15, 3.6, 0.9, days, 0.2816, 53.0)
    assert abs(parts_sum(sim.saving_breakdown()) - sim.saving_battery_only) < 1.0


# ── Battery with solar ────────────────────────────────────────────────────────

def solar_result(tariff_key="octopusFlux", cap=10.0, seg=0.15):
    t = TARIFFS[tariff_key]
    base = run_simulation(t, cap, 3.6, 0.9, DAYS, 0.2816, 53.0)
    return calc_solar_impact(
        t, cap, 3.6, 0.9, DAYS, SOLAR, seg_rate=seg,
        ann_cost_current=base.ann_cost_current, sc_new=t.standing_charge * 365,
    )


@pytest.mark.parametrize("tariff_key", ["octopusFlux", "octopusGo", "octopusCosy", "currentFlat"])
@pytest.mark.parametrize("cap", [5.0, 10.0])
def test_solar_battery_parts_sum_to_battery_saving(tariff_key, cap):
    sr = solar_result(tariff_key, cap)
    b = sr.saving_breakdown()
    assert b["total"] == pytest.approx(sr.saving_solar_battery - sr.saving_solar_only, abs=0.02)
    assert abs(parts_sum(b) - b["total"]) < 1.0


def test_flat_rate_battery_saving_is_all_solar():
    """On a flat rate there are no cheap slots, so the battery only stores solar."""
    b = solar_result("currentFlat").saving_breakdown()
    assert b["time_shifting"] == pytest.approx(0, abs=1.0)
    assert b["solar_storage"] > 50


def test_solar_storage_is_net_of_lost_export_income():
    # The higher the export rate, the less storing solar is worth.
    low = solar_result("currentFlat", seg=0.05).saving_breakdown()["solar_storage"]
    high = solar_result("currentFlat", seg=0.20).saving_breakdown()["solar_storage"]
    assert high < low


def test_starting_charge_is_tiny():
    b = solar_result().saving_breakdown()
    assert 0 <= b["other"] < 2


# ── API ───────────────────────────────────────────────────────────────────────

def test_estimate_returns_breakdown():
    r = TestClient(app).post("/api/estimate", json={"annual_kwh": 3500, "property_type": "semi"})
    assert r.status_code == 200, r.text
    f = r.json()["financials"]
    b = f["saving_breakdown"]
    assert b["total"] == pytest.approx(f["saving_battery_only"], abs=0.01)
    assert abs(parts_sum(b) - b["total"]) < 1.0


def test_solar_endpoint_returns_battery_breakdown(monkeypatch):
    import routers.solar as solar_router

    async def fake_postcode(pc):
        return 52.2, 0.12

    async def fake_profiles(**kw):
        return {"monthly_profiles": None, "annual_kwh": 3400}

    monkeypatch.setattr(solar_router, "resolve_postcode", fake_postcode)
    monkeypatch.setattr(solar_router, "fetch_solar_profiles", fake_profiles)
    monkeypatch.setattr(solar_router, "weighted_avg_profile", lambda _m: SOLAR)

    c = TestClient(app)
    sid = c.post("/api/estimate", json={"annual_kwh": 3500, "property_type": "semi"}).json()["session_id"]
    r = c.post("/api/solar", json={"session_id": sid, "postcode": "CB1 1AA", "tariff_key": "octopusFlux"})
    assert r.status_code == 200, r.text
    s = r.json()["solar"]
    b = s["battery_saving_breakdown"]
    assert b["total"] == pytest.approx(s["incremental_battery_saving"], abs=0.02)
    assert abs(parts_sum(b) - b["total"]) < 1.0
