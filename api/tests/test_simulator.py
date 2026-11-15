"""
Structured simulation tests for the BatterySizer engine (60 checks).

Covers:
  A. SoC constraints          — floor never breached, ceiling respected
  B. Battery-only dispatch    — charges on cheap slots, discharges on peak
  C. Solar-only               — self-consumption then export, no battery moves
  D. Solar+battery day flow   — priority order, overnight ceiling, full-day discharge
  E. Overnight ceiling logic  — sunny vs cloudy day headroom
  F. Cross-tariff             — Octopus Go, Flux, Economy 7, Cosy
  G. Financial sanity         — solar+battery annual saving > battery-only > 0
  H. Edge cases               — zero load, heavy load, tiny battery, large solar

Run from api/:  pytest
"""
import pytest

from engine.simulator import calc_day_flows, run_simulation, calc_solar_impact
from engine.tariffs import TARIFFS
from engine.profile_estimator import make_parse_result
from engine.payback import calc_payback


# ─────────────────────────────────────────────────────────────────────────────
# Shared inputs
# ─────────────────────────────────────────────────────────────────────────────

def _make_load(daily_kwh=8.5):
    """48-slot daily load profile (kWh) for a typical 3-bed semi, morning + evening peak."""
    base = [0.10] * 48
    for i in range(14, 20):
        base[i] += 0.22   # 07:00–10:00 morning
    for i in range(32, 42):
        base[i] += 0.35   # 16:00–21:00 evening
    total = sum(base)
    return [v * daily_kwh / total for v in base]


# Normalised solar shape (same Gaussian as analyse.py), peak around 13:00
_SOLAR_NORM = [
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0.0066, 0.0093, 0.0129, 0.0172, 0.0225, 0.0285, 0.0350,
    0.0420, 0.0490, 0.0555, 0.0611, 0.0655, 0.0683,
    0.0692, 0.0683,
    0.0655, 0.0611, 0.0555, 0.0490, 0.0420, 0.0350,
    0.0285, 0.0225, 0.0172, 0.0129,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
]


def make_solar(daily_gen_kwh):
    return [v * daily_gen_kwh for v in _SOLAR_NORM]


LOAD     = _make_load(8.5)
SOLAR_12 = make_solar(12.0)   # sunny summer day
SOLAR_3  = make_solar(3.0)    # cloudy day
SOLAR_0  = [0.0] * 48         # no solar

CAP    = 10.0
RATE   = 3.6
EFF    = 0.90
FLUX   = TARIFFS["octopusFlux"]
GO     = TARIFFS["octopusGo"]
ECO7   = TARIFFS["economy7"]
COSY   = TARIFFS["octopusCosy"]
FLAT_T = TARIFFS["currentFlat"]


def flows(load=LOAD, tariff=FLUX, cap=CAP, solar=None):
    return calc_day_flows(load, tariff, cap, RATE, EFF, solar)


# ─────────────────────────────────────────────────────────────────────────────
# A. SOC CONSTRAINTS  (5 scenarios × 2 checks = 10)
# ─────────────────────────────────────────────────────────────────────────────

SOC_SCENARIOS = [
    pytest.param(None,     GO,   id="battery-only/Go"),
    pytest.param(None,     FLUX, id="battery-only/Flux"),
    pytest.param(SOLAR_12, FLUX, id="solar+battery-sunny/Flux"),
    pytest.param(SOLAR_3,  FLUX, id="solar+battery-cloudy/Flux"),
    pytest.param(SOLAR_0,  GO,   id="solar+battery-no-sun/Go"),
]


@pytest.mark.parametrize("solar,tariff", SOC_SCENARIOS)
def test_a1_soc_never_below_10pct(solar, tariff):
    soc = flows(tariff=tariff, solar=solar)["soc_profile"]
    floor = CAP * 0.10
    assert all(s >= floor - 1e-6 for s in soc), f"min={min(soc):.4f} kWh floor={floor:.1f} kWh"


@pytest.mark.parametrize("solar,tariff", SOC_SCENARIOS)
def test_a2_soc_never_above_100pct(solar, tariff):
    soc = flows(tariff=tariff, solar=solar)["soc_profile"]
    ceiling = CAP * 1.001  # tiny float tolerance
    assert all(s <= ceiling for s in soc), f"max={max(soc):.4f} kWh cap={CAP:.1f} kWh"


# ─────────────────────────────────────────────────────────────────────────────
# B. BATTERY-ONLY DISPATCH  (9)
# ─────────────────────────────────────────────────────────────────────────────

# Octopus Go: cheap slots 0–10 and 47 (00:00–05:30, 23:30)
GO_CHARGE_SLOTS = list(range(0, 11)) + [47]
GO_PEAK_SLOTS   = list(range(11, 47))

# Flux: charge 00:00–05:00 (slots 0–9, 46–47), peak 16:00–19:00 (slots 32–37)
FLUX_CHARGE_SLOTS    = list(range(0, 10)) + [46, 47]
FLUX_DISCHARGE_SLOTS = list(range(32, 38))
FLUX_MID_SLOTS       = list(range(10, 32))


@pytest.fixture(scope="module")
def flows_go():
    return flows(tariff=GO)


@pytest.fixture(scope="module")
def flows_flux():
    return flows(tariff=FLUX)


def test_b1_go_charges_only_in_cheap_slots(flows_go):
    gtb = flows_go["grid_to_batt"]
    assert all(gtb[i] == 0.0 for i in GO_PEAK_SLOTS), \
        f"max grid→batt in day slots = {max(gtb[i] for i in GO_PEAK_SLOTS):.4f} kWh"


def test_b2_go_charges_during_cheap_window(flows_go):
    charged = sum(flows_go["grid_to_batt"][i] for i in GO_CHARGE_SLOTS)
    assert charged > 0.1, f"total charged = {charged:.3f} kWh"


def test_b3_go_discharges_during_day(flows_go):
    discharged = sum(flows_go["from_battery"][i] for i in GO_PEAK_SLOTS)
    assert discharged > 0.5, f"total discharged = {discharged:.3f} kWh"


def test_b4_go_no_discharge_in_cheap_slots(flows_go):
    fb = flows_go["from_battery"]
    assert all(fb[i] == 0.0 for i in GO_CHARGE_SLOTS), \
        f"max discharge in cheap slots = {max(fb[i] for i in GO_CHARGE_SLOTS):.4f} kWh"


def test_b5_flux_charges_in_cheap_window(flows_flux):
    charged = sum(flows_flux["grid_to_batt"][i] for i in FLUX_CHARGE_SLOTS)
    assert charged > 0.1, f"charged = {charged:.3f} kWh"


def test_b6_flux_no_grid_charge_outside_window(flows_flux):
    gtb = flows_flux["grid_to_batt"]
    assert all(gtb[i] == 0.0 for i in FLUX_MID_SLOTS), \
        f"max outside = {max(gtb[i] for i in FLUX_MID_SLOTS):.4f} kWh"


def test_b7_flux_discharges_at_peak(flows_flux):
    discharged = sum(flows_flux["from_battery"][i] for i in FLUX_DISCHARGE_SLOTS)
    assert discharged > 0.3, f"discharged at peak = {discharged:.3f} kWh"


def test_b8_flux_no_discharge_midday_battery_only(flows_flux):
    fb = flows_flux["from_battery"]
    assert all(fb[i] == 0.0 for i in FLUX_MID_SLOTS), \
        f"max discharge in mid-day = {max(fb[i] for i in FLUX_MID_SLOTS):.4f} kWh"


def test_b9_battery_idle_on_flat_rate():
    f = flows(tariff=FLAT_T)
    gtb, fb = sum(f["grid_to_batt"]), sum(f["from_battery"])
    assert gtb < 0.001 and fb < 0.001, f"grid→batt={gtb:.4f} from_batt={fb:.4f}"


# ─────────────────────────────────────────────────────────────────────────────
# C. SOLAR-ONLY, NO BATTERY  (5)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def flows_solar_only():
    return flows(tariff=FLUX, cap=0.0, solar=SOLAR_12)


def test_c1_self_consumption_capped(flows_solar_only):
    f = flows_solar_only
    sc, gen = f["self_consumed"], f["solar_gen"]
    # 1e-4 = rounding tolerance (engine rounds to 4 dp)
    assert all(sc[i] <= min(gen[i], LOAD[i]) + 1e-4 for i in range(48)), \
        f"max excess = {max(sc[i] - min(gen[i], LOAD[i]) for i in range(48)):.8f}"


def test_c2_no_battery_moves_without_battery(flows_solar_only):
    stb, fb = sum(flows_solar_only["solar_to_batt"]), sum(flows_solar_only["from_battery"])
    assert stb < 1e-6 and fb < 1e-6, f"solar→batt={stb:.6f} from_batt={fb:.6f}"


def test_c3_energy_balance_gen_equals_sc_plus_export(flows_solar_only):
    f = flows_solar_only
    sc, exp, gen = f["self_consumed"], f["exported"], f["solar_gen"]
    assert all(abs(sc[i] + exp[i] - gen[i]) < 1e-6 for i in range(48)), \
        f"max imbalance = {max(abs(sc[i] + exp[i] - gen[i]) for i in range(48)):.8f}"


def test_c4_grid_fills_remaining_load(flows_solar_only):
    f = flows_solar_only
    gtl, gen = f["grid_to_load"], f["solar_gen"]
    assert all(abs(gtl[i] - max(0.0, LOAD[i] - gen[i])) < 1e-4 for i in range(48)), \
        f"max mismatch = {max(abs(gtl[i] - max(0.0, LOAD[i] - gen[i])) for i in range(48)):.8f}"


def test_c5_no_export_when_solar_below_load(flows_solar_only):
    f = flows_solar_only
    exp, gen = f["exported"], f["solar_gen"]
    assert all(exp[i] < 1e-6 for i in range(48) if gen[i] <= LOAD[i])


# ─────────────────────────────────────────────────────────────────────────────
# D. SOLAR + BATTERY: PRIORITY ORDER AND DISPATCH  (7)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def flows_sb():
    return flows(tariff=FLUX, solar=SOLAR_12)


def test_d1_solar_self_consumed_first(flows_sb):
    sc, gen = flows_sb["self_consumed"], flows_sb["solar_gen"]
    assert all(sc[i] <= min(gen[i], LOAD[i]) + 1e-4 for i in range(48)), \
        f"max excess = {max(sc[i] - min(gen[i], LOAD[i]) for i in range(48)):.8f}"


def test_d2_solar_charges_battery_before_export(flows_sb):
    stb = sum(flows_sb["solar_to_batt"])
    assert stb > 0.5, f"total solar→batt = {stb:.3f} kWh (sunny day)"


def test_d3_export_only_when_load_satisfied(flows_sb):
    sc, exp, gen = flows_sb["self_consumed"], flows_sb["exported"], flows_sb["solar_gen"]
    assert all(
        exp[i] < 1e-5 or abs(sc[i] - LOAD[i]) < 1e-5 or gen[i] > LOAD[i]
        for i in range(48)
    ), "spurious export while load unmet"


def test_d4_battery_discharges_outside_peak(flows_sb):
    # Flux peak is slots 32–37; any discharge in 10–31 shows all-day self-sufficiency
    midday = sum(flows_sb["from_battery"][i] for i in range(10, 32))
    assert midday > 0.1, f"mid-day discharge = {midday:.3f} kWh"


def test_d5_grid_draw_lower_than_solar_only(flows_sb, flows_solar_only):
    sb, so = sum(flows_sb["grid_to_load"]), sum(flows_solar_only["grid_to_load"])
    assert sb < so - 0.1, f"solar+batt grid draw={sb:.3f} solar-only={so:.3f} kWh"


def test_d6_export_not_higher_than_solar_only(flows_sb, flows_solar_only):
    sb, so = sum(flows_sb["exported"]), sum(flows_solar_only["exported"])
    assert sb <= so + 0.05, f"solar+batt export={sb:.3f} solar-only export={so:.3f} kWh"


def test_d7_load_fully_met_every_slot(flows_sb):
    sc, fb, gtl = flows_sb["self_consumed"], flows_sb["from_battery"], flows_sb["grid_to_load"]
    imbalance = [abs(sc[i] + fb[i] + gtl[i] - LOAD[i]) for i in range(48)]
    assert all(x < 1e-4 for x in imbalance), f"max imbalance = {max(imbalance):.6f} kWh"


# ─────────────────────────────────────────────────────────────────────────────
# E. OVERNIGHT CHARGING CEILING  (7)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def flux_days():
    return {
        "sunny":  flows(tariff=FLUX, solar=SOLAR_12),
        "cloudy": flows(tariff=FLUX, solar=SOLAR_3),
        "no_sun": flows(tariff=FLUX, solar=SOLAR_0),
    }


def _overnight(f):
    """Grid charging in the Flux cheap window (slots 0–9)."""
    return sum(f["grid_to_batt"][i] for i in range(10))


def test_e1_sunny_less_overnight_charge_than_cloudy(flux_days):
    sunny, cloudy = _overnight(flux_days["sunny"]), _overnight(flux_days["cloudy"])
    assert sunny < cloudy, f"sunny={sunny:.3f} cloudy={cloudy:.3f} kWh"


def test_e2_no_sun_most_overnight_charge(flux_days):
    no_sun, cloudy = _overnight(flux_days["no_sun"]), _overnight(flux_days["cloudy"])
    assert no_sun >= cloudy - 0.05, f"no-solar={no_sun:.3f} cloudy={cloudy:.3f} kWh"


def test_e3_sunny_solar_charges_battery_daytime(flux_days):
    daytime = sum(flux_days["sunny"]["solar_to_batt"][i] for i in range(13, 35))
    assert daytime > 0.5, f"solar→batt daytime = {daytime:.3f} kWh"


def test_e4_cloudy_grid_overnight_exceeds_solar(flux_days):
    f = flux_days["cloudy"]
    grid, solar = _overnight(f), sum(f["solar_to_batt"])
    assert grid > solar, f"overnight grid={grid:.3f} solar→batt={solar:.3f} kWh"


def test_e5_sunny_reaches_higher_soc(flux_days):
    sunny = max(flux_days["sunny"]["soc_profile"])
    cloudy = max(flux_days["cloudy"]["soc_profile"])
    assert sunny >= cloudy - 0.1, f"sunny peak SoC={sunny:.2f} cloudy peak SoC={cloudy:.2f} kWh"


def test_e6_soc_floor_sunny(flux_days):
    soc = flux_days["sunny"]["soc_profile"]
    assert all(s >= CAP * 0.10 - 1e-6 for s in soc), f"min SoC = {min(soc):.4f} kWh"


def test_e7_soc_floor_no_sun(flux_days):
    soc = flux_days["no_sun"]["soc_profile"]
    assert all(s >= CAP * 0.10 - 1e-6 for s in soc), f"min SoC = {min(soc):.4f} kWh"


# ─────────────────────────────────────────────────────────────────────────────
# F. CROSS-TARIFF  (4 tariffs × 2 checks = 8)
# ─────────────────────────────────────────────────────────────────────────────

CROSS_TARIFFS = [
    pytest.param(GO,   id="Go"),
    pytest.param(FLUX, id="Flux"),
    pytest.param(ECO7, id="Economy7"),
    pytest.param(COSY, id="Cosy"),
]


@pytest.mark.parametrize("tariff", CROSS_TARIFFS)
def test_f1_battery_only_charges_and_discharges(tariff):
    f = flows(tariff=tariff)
    charged, discharged = sum(f["grid_to_batt"]), sum(f["from_battery"])
    assert charged > 0.1 and discharged > 0.1, \
        f"charged={charged:.3f} discharged={discharged:.3f} kWh"


@pytest.mark.parametrize("tariff", CROSS_TARIFFS)
def test_f2_solar_battery_grid_draw_below_solar_only(tariff):
    sb = sum(flows(tariff=tariff, solar=SOLAR_12)["grid_to_load"])
    so = sum(flows(tariff=tariff, cap=0.0, solar=SOLAR_12)["grid_to_load"])
    assert sb < so, f"s+b={sb:.3f} solar-only={so:.3f} kWh"


# ─────────────────────────────────────────────────────────────────────────────
# G. FINANCIAL SANITY, ANNUAL SIMULATION  (7)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def annual():
    parse = make_parse_result(3100, "semi", 28.16)
    unit_rate = parse.inferred_rate
    sim_go = run_simulation(GO, CAP, RATE, EFF, parse.days, unit_rate, 53.0)
    sim_flat = run_simulation(FLAT_T, CAP, RATE, EFF, parse.days, unit_rate, 53.0)
    solar_profile_ann = make_solar(4.0 * 850 / 365)   # 4 kWp, annual average daily generation
    sr = calc_solar_impact(
        FLUX, CAP, RATE, EFF, parse.days, solar_profile_ann,
        seg_rate=0.15,
        ann_cost_current=sim_go.ann_cost_current,
        sc_new=FLUX.standing_charge * 365,
    )
    return {"sim_go": sim_go, "sim_flat": sim_flat, "solar": sr}


def test_g1_battery_only_go_positive_saving(annual):
    s = annual["sim_go"].total_saving
    assert s > 0, f"saving = £{s:.0f}/yr"


def test_g2_battery_only_go_saving_in_range(annual):
    s = annual["sim_go"].total_saving
    assert 200 <= s <= 900, f"saving = £{s:.0f}/yr"


def test_g3_battery_only_flat_rate_near_zero(annual):
    s = annual["sim_flat"].saving_battery_only
    assert abs(s) < 20, f"battery arbitrage saving = £{s:.2f}"


def test_g4_solar_battery_beats_battery_only(annual):
    sb, bo = annual["solar"].saving_solar_battery, annual["sim_go"].total_saving
    assert sb > bo, f"solar+batt=£{sb:.0f} battery-only=£{bo:.0f}"


def test_g5_direct_self_consumption_at_least_35pct(annual):
    # self_consumption_pct counts direct solar→load only, not battery-mediated use.
    # With a 4 kWp annual-average profile, direct self-consumption is about 43%.
    sr = annual["solar"]
    assert sr.self_consumption_pct >= 35, \
        f"direct SC = {sr.self_consumption_pct:.1f}% (exported_with_batt={sr.ann_exported_with_batt_kwh:.0f} kWh)"


def test_g6_less_export_with_battery(annual):
    sr = annual["solar"]
    assert sr.ann_exported_with_batt_kwh < sr.ann_exported_no_batt_kwh, \
        f"with_batt={sr.ann_exported_with_batt_kwh:.0f} no_batt={sr.ann_exported_no_batt_kwh:.0f} kWh/yr"


def test_g7_payback_5_to_15_years(annual):
    pb = calc_payback(6000, annual["sim_go"].total_saving, 5.0)
    assert 5 <= pb.years <= 15, f"payback = {pb.years:.1f} years"


# ─────────────────────────────────────────────────────────────────────────────
# H. EDGE CASES  (7)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def flows_zero_load():
    return flows(load=[0.0] * 48, tariff=FLUX, solar=SOLAR_12)


def test_h1_zero_load_no_grid_to_load(flows_zero_load):
    g = sum(flows_zero_load["grid_to_load"])
    assert g < 1e-6, f"grid_to_load = {g:.6f}"


def test_h2_zero_load_solar_stored_or_exported(flows_zero_load):
    f = flows_zero_load
    gen, stb, exp = sum(f["solar_gen"]), sum(f["solar_to_batt"]), sum(f["exported"])
    assert abs(gen - stb - exp) < 1e-4, f"gen={gen:.3f} →batt={stb:.3f} export={exp:.3f}"


def test_h3_heavy_load_soc_floor():
    soc = flows(load=[v * 3 for v in LOAD], tariff=FLUX)["soc_profile"]   # ~25 kWh day
    assert all(s >= CAP * 0.10 - 1e-6 for s in soc), f"min SoC = {min(soc):.4f} kWh"


@pytest.fixture(scope="module")
def flows_tiny():
    return flows(tariff=GO, cap=1.0)


def test_h4_tiny_battery_operates(flows_tiny):
    charged, discharged = sum(flows_tiny["grid_to_batt"]), sum(flows_tiny["from_battery"])
    assert charged > 0 and discharged > 0, f"charged={charged:.3f} discharged={discharged:.3f}"


def test_h5_tiny_battery_soc_floor(flows_tiny):
    soc = flows_tiny["soc_profile"]
    assert all(s >= 1.0 * 0.10 - 1e-6 for s in soc), f"min SoC = {min(soc):.4f} kWh floor=0.1 kWh"


@pytest.fixture(scope="module")
def flows_big_solar():
    return flows(tariff=FLUX, solar=make_solar(30.0))   # far more than the 8.5 kWh load


def test_h6_large_solar_exports_excess(flows_big_solar):
    exp = sum(flows_big_solar["exported"])
    assert exp > 1.0, f"exported = {exp:.3f} kWh"


def test_h7_large_solar_minimal_grid(flows_big_solar):
    g = sum(flows_big_solar["grid_to_load"])
    assert g < 1.5, f"grid_to_load = {g:.3f} kWh"
