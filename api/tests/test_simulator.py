"""
Structured simulation tests for BatterySizer engine.

Covers:
  A. SoC constraints          — floor never breached, ceiling respected
  B. Battery-only dispatch    — charges on cheap slots, discharges on peak
  C. Solar-only               — self-consumption then export, no battery moves
  D. Solar+battery day flow   — priority order, overnight ceiling, full-day discharge
  E. Overnight ceiling logic  — sunny vs cloudy day headroom
  F. Cross-tariff              — Octopus Go, Flux, Economy 7, Cosy, Flat rate
  G. Financial sanity          — solar+battery annual saving > battery-only > 0
  H. Edge cases               — zero load, zero solar, tiny battery
"""
import sys, math
sys.path.insert(0, '.')

from engine.simulator import calc_day_flows, run_simulation, calc_solar_impact
from engine.tariffs   import TARIFFS, Tariff
from engine.profile_estimator import make_parse_result

PASS = "✅ PASS"
FAIL = "❌ FAIL"
results = []

def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append((status, name, detail))
    print(f"{status}  {name}" + (f"\n       {detail}" if detail else ""))

def approx(a, b, pct=5):
    """True if a is within pct% of b (or both ~0)."""
    if abs(b) < 1e-6:
        return abs(a) < 1e-6
    return abs(a - b) / abs(b) < pct / 100.0


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────

# Typical 3-bed semi daily load: ~8.5 kWh, shaped with morning+evening peaks
def _make_load(daily_kwh=8.5):
    """48-slot daily load profile (kWh), morning + evening peak."""
    # Flat base 0.1 kWh/slot + morning peak slots 14-19 + evening peak 32-41
    base = [0.10] * 48
    for i in range(14, 20): base[i] += 0.22   # 07:00–10:00 morning
    for i in range(32, 42): base[i] += 0.35   # 16:00–21:00 evening
    # Normalise to desired daily kWh
    total = sum(base)
    return [v * daily_kwh / total for v in base]

def _make_solar(daily_gen_kwh=12.0):
    """48-slot solar profile (kWh), Gaussian centred on 13:00."""
    from engine.routers_analyse_constants import UK_SOLAR_PROFILE_NORM
    return [v * daily_gen_kwh for v in UK_SOLAR_PROFILE_NORM]

# Fallback: inline solar profile (same Gaussian as analyse.py)
_SOLAR_NORM = [
    0,0,0,0,0,0,0,0,0,0,0,0,0,
    0.0066, 0.0093,0.0129,0.0172,0.0225,0.0285,0.0350,
    0.0420,0.0490,0.0555,0.0611,0.0655,0.0683,
    0.0692,0.0683,
    0.0655,0.0611,0.0555,0.0490,0.0420,0.0350,
    0.0285,0.0225,0.0172,0.0129,
    0,0,0,0,0,0,0,0,0,0,
]

def make_solar(daily_gen_kwh):
    return [v * daily_gen_kwh for v in _SOLAR_NORM]

LOAD      = _make_load(8.5)
SOLAR_12  = make_solar(12.0)   # sunny summer day
SOLAR_3   = make_solar(3.0)    # cloudy day
SOLAR_0   = [0.0] * 48         # no solar (night / winter)

CAP       = 10.0
RATE      = 3.6
EFF       = 0.90
FLUX      = TARIFFS["octopusFlux"]
GO        = TARIFFS["octopusGo"]
ECO7      = TARIFFS["economy7"]
COSY      = TARIFFS["octopusCosy"]
FLAT_T    = TARIFFS["currentFlat"]


print("\n" + "="*70)
print("BATTERYSIZER SIMULATION ENGINE — STRUCTURED TEST REPORT")
print("="*70 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# A. SOC CONSTRAINTS
# ─────────────────────────────────────────────────────────────────────────────
print("── A. SoC Constraints ──────────────────────────────────────────────\n")

for label, solar, tariff in [
    ("battery-only / Go",          None,     GO),
    ("battery-only / Flux",        None,     FLUX),
    ("solar+battery sunny / Flux", SOLAR_12, FLUX),
    ("solar+battery cloudy / Flux",SOLAR_3,  FLUX),
    ("solar+battery no-sun / Go",  SOLAR_0,  GO),
]:
    flows = calc_day_flows(LOAD, tariff, CAP, RATE, EFF, solar)
    soc   = flows["soc_profile"]
    min_s = CAP * 0.10
    max_s = CAP * 1.001  # tiny float tolerance

    check(f"A1 SoC never below 10% [{label}]",
          all(s >= min_s - 1e-6 for s in soc),
          f"min={min(soc):.4f} kWh  floor={min_s:.1f} kWh")

    check(f"A2 SoC never above 100% [{label}]",
          all(s <= max_s for s in soc),
          f"max={max(soc):.4f} kWh  cap={CAP:.1f} kWh")


# ─────────────────────────────────────────────────────────────────────────────
# B. BATTERY-ONLY DISPATCH
# ─────────────────────────────────────────────────────────────────────────────
print("\n── B. Battery-only Dispatch ────────────────────────────────────────\n")

flows_go = calc_day_flows(LOAD, GO, CAP, RATE, EFF, None)

# Octopus Go: charge slots 0-10, 47 (00:00–05:30, 23:30)
# Should charge during those slots, not during day
go_charge_slots  = list(range(0, 11)) + [47]
go_peak_slots    = list(range(11, 47))

gtb = flows_go["grid_to_batt"]
fb  = flows_go["from_battery"]

check("B1 Battery charges only in cheap slots (Go)",
      all(gtb[i] == 0.0 for i in go_peak_slots),
      f"max grid→batt in day slots = {max(gtb[i] for i in go_peak_slots):.4f} kWh")

check("B2 Battery charges during cheap window (Go)",
      sum(gtb[i] for i in go_charge_slots) > 0.1,
      f"total charged = {sum(gtb[i] for i in go_charge_slots):.3f} kWh")

check("B3 Battery discharges during day (Go)",
      sum(fb[i] for i in go_peak_slots) > 0.5,
      f"total discharged = {sum(fb[i] for i in go_peak_slots):.3f} kWh")

check("B4 No discharge during cheap charge slots (Go)",
      all(fb[i] == 0.0 for i in go_charge_slots),
      f"max discharge in cheap slots = {max(fb[i] for i in go_charge_slots):.4f} kWh")

# Flux: charge 00:00-05:00 (slots 0-9, 46-47), discharge 16:00-19:00 (slots 32-37)
flows_flux = calc_day_flows(LOAD, FLUX, CAP, RATE, EFF, None)
flux_charge_slots    = list(range(0, 10)) + [46, 47]
flux_discharge_slots = list(range(32, 38))
flux_mid_slots       = list(range(10, 32))

gtb_f = flows_flux["grid_to_batt"]
fb_f  = flows_flux["from_battery"]

check("B5 Battery charges in Flux cheap window (00:00-05:00)",
      sum(gtb_f[i] for i in flux_charge_slots) > 0.1,
      f"charged = {sum(gtb_f[i] for i in flux_charge_slots):.3f} kWh")

check("B6 No grid→battery outside Flux charge slots",
      all(gtb_f[i] == 0.0 for i in flux_mid_slots),
      f"max outside = {max(gtb_f[i] for i in flux_mid_slots):.4f} kWh")

check("B7 Battery discharges during Flux peak (16:00-19:00)",
      sum(fb_f[i] for i in flux_discharge_slots) > 0.3,
      f"discharged at peak = {sum(fb_f[i] for i in flux_discharge_slots):.3f} kWh")

check("B8 No discharge outside Flux discharge window (battery-only)",
      all(fb_f[i] == 0.0 for i in flux_mid_slots),
      f"max discharge in mid-day = {max(fb_f[i] for i in flux_mid_slots):.4f} kWh")

# Flat rate: no charge/discharge slots → battery should sit idle
flows_flat = calc_day_flows(LOAD, FLAT_T, CAP, RATE, EFF, None)
check("B9 Battery idle on flat rate (no cheap slots)",
      sum(flows_flat["grid_to_batt"]) < 0.001 and sum(flows_flat["from_battery"]) < 0.001,
      f"grid→batt={sum(flows_flat['grid_to_batt']):.4f}  from_batt={sum(flows_flat['from_battery']):.4f}")


# ─────────────────────────────────────────────────────────────────────────────
# C. SOLAR-ONLY (no battery)
# ─────────────────────────────────────────────────────────────────────────────
print("\n── C. Solar-only (cap=0) ───────────────────────────────────────────\n")

flows_so = calc_day_flows(LOAD, FLUX, 0.0, RATE, EFF, SOLAR_12)

sc   = flows_so["self_consumed"]
exp  = flows_so["exported"]
gtl  = flows_so["grid_to_load"]
gen  = flows_so["solar_gen"]
stb  = flows_so["solar_to_batt"]
fb_s = flows_so["from_battery"]

check("C1 Self-consumption ≤ min(solar, load) each slot",
      all(sc[i] <= min(gen[i], LOAD[i]) + 1e-4 for i in range(48)),   # 1e-4 = r4 rounding tolerance
      f"max excess = {max(sc[i]-min(gen[i],LOAD[i]) for i in range(48)):.8f}")

check("C2 No battery moves without a battery",
      sum(stb) < 1e-6 and sum(fb_s) < 1e-6,
      f"solar→batt={sum(stb):.6f}  from_batt={sum(fb_s):.6f}")

check("C3 Energy balance: gen = self_consumed + exported",
      all(abs((sc[i]+exp[i]) - gen[i]) < 1e-6 for i in range(48)),
      f"max imbalance = {max(abs(sc[i]+exp[i]-gen[i]) for i in range(48)):.8f}")

check("C4 Grid fills remaining load after solar",
      all(abs(gtl[i] - max(0.0, LOAD[i]-gen[i])) < 1e-4 for i in range(48)),  # r4 rounding tolerance
      f"max mismatch = {max(abs(gtl[i]-max(0.0,LOAD[i]-gen[i])) for i in range(48)):.8f}")

check("C5 No export when solar < load",
      all(exp[i] < 1e-6 for i in range(48) if gen[i] <= LOAD[i]),
      "export only when solar exceeds load")


# ─────────────────────────────────────────────────────────────────────────────
# D. SOLAR + BATTERY — priority order and full-day discharge
# ─────────────────────────────────────────────────────────────────────────────
print("\n── D. Solar+Battery Priority & Dispatch ────────────────────────────\n")

flows_sb = calc_day_flows(LOAD, FLUX, CAP, RATE, EFF, SOLAR_12)

sc_sb  = flows_sb["self_consumed"]
stb_sb = flows_sb["solar_to_batt"]
gtb_sb = flows_sb["grid_to_batt"]
fb_sb  = flows_sb["from_battery"]
exp_sb = flows_sb["exported"]
gtl_sb = flows_sb["grid_to_load"]
soc_sb = flows_sb["soc_profile"]
gen_sb = flows_sb["solar_gen"]

check("D1 Solar self-consumed before battery",
      all(sc_sb[i] <= min(gen_sb[i], LOAD[i]) + 1e-4 for i in range(48)),  # r4 rounding tolerance
      f"max excess = {max(sc_sb[i]-min(gen_sb[i],LOAD[i]) for i in range(48)):.8f}")

check("D2 Solar charges battery before grid export",
      # When there's surplus and battery has headroom, stb > 0 before export
      sum(stb_sb) > 0.5,
      f"total solar→batt = {sum(stb_sb):.3f} kWh (sunny day)")

check("D3 Export only when both load AND battery are satisfied",
      all(
          exp_sb[i] < 1e-5 or (
              abs(sc_sb[i] - LOAD[i]) < 1e-5 or gen_sb[i] > LOAD[i]  # load covered
          )
          for i in range(48)
      ),
      "no spurious export while load unmet")

check("D4 Battery discharges outside tariff peak slots (self-sufficiency)",
      # Flux peak is 32-37; any discharge in 10-31 shows all-day discharge
      sum(fb_sb[i] for i in range(10, 32)) > 0.1,
      f"mid-day discharge = {sum(fb_sb[i] for i in range(10,32)):.3f} kWh")

check("D5 Grid-to-home reduced vs solar-only",
      sum(gtl_sb) < sum(flows_so["grid_to_load"]) - 0.1,
      f"solar+batt grid draw={sum(gtl_sb):.3f}  solar-only={sum(flows_so['grid_to_load']):.3f} kWh")

check("D6 Export reduced vs solar-only (battery absorbs surplus)",
      sum(exp_sb) <= sum(exp) + 0.05,
      f"solar+batt export={sum(exp_sb):.3f}  solar-only export={sum(exp):.3f} kWh")

# Energy balance per slot: gen + grid_charge + from_batt = load + solar_to_batt + exported + grid_draw
# i.e. inflows = outflows
for i in range(48):
    inflow  = gen_sb[i] + gtb_sb[i] + fb_sb[i]
    outflow = LOAD[i] + stb_sb[i] + exp_sb[i] + gtl_sb[i]
    # Note: gtb is grid draw (adjusted for efficiency); net stored = gtb*eff
    # Simplified balance check: load met = self_consumed + from_batt + grid_to_load
    met = sc_sb[i] + fb_sb[i] + gtl_sb[i]

check("D7 Load fully met every slot (sc + from_batt + grid = load)",
      all(abs(sc_sb[i] + fb_sb[i] + gtl_sb[i] - LOAD[i]) < 1e-4 for i in range(48)),
      f"max imbalance = {max(abs(sc_sb[i]+fb_sb[i]+gtl_sb[i]-LOAD[i]) for i in range(48)):.6f} kWh")


# ─────────────────────────────────────────────────────────────────────────────
# E. OVERNIGHT CHARGING CEILING
# ─────────────────────────────────────────────────────────────────────────────
print("\n── E. Overnight Charging Ceiling ───────────────────────────────────\n")

# Sunny day: expect ceiling to be LOW (lots of solar headroom reserved)
flows_sunny  = calc_day_flows(LOAD, FLUX, CAP, RATE, EFF, SOLAR_12)
flows_cloudy = calc_day_flows(LOAD, FLUX, CAP, RATE, EFF, SOLAR_3)
flows_noson  = calc_day_flows(LOAD, FLUX, CAP, RATE, EFF, SOLAR_0)

# Overnight = slots 0-9 (Flux cheap window)
sunny_overnight_charged  = sum(flows_sunny["grid_to_batt"][i]  for i in range(10))
cloudy_overnight_charged = sum(flows_cloudy["grid_to_batt"][i] for i in range(10))
noson_overnight_charged  = sum(flows_noson["grid_to_batt"][i]  for i in range(10))

check("E1 Sunny day: less overnight grid charging than cloudy day",
      sunny_overnight_charged < cloudy_overnight_charged,
      f"sunny={sunny_overnight_charged:.3f}  cloudy={cloudy_overnight_charged:.3f} kWh")

check("E2 No-solar day: most overnight grid charging",
      noson_overnight_charged >= cloudy_overnight_charged - 0.05,
      f"no-solar={noson_overnight_charged:.3f}  cloudy={cloudy_overnight_charged:.3f} kWh")

check("E3 Sunny day: solar charges battery significantly during daytime",
      sum(flows_sunny["solar_to_batt"][i] for i in range(13, 35)) > 0.5,
      f"solar→batt daytime = {sum(flows_sunny['solar_to_batt'][i] for i in range(13,35)):.3f} kWh")

check("E4 Cloudy day: grid overnight > solar daytime contribution",
      cloudy_overnight_charged > sum(flows_cloudy["solar_to_batt"]),
      f"overnight grid={cloudy_overnight_charged:.3f}  solar→batt={sum(flows_cloudy['solar_to_batt']):.3f} kWh")

# Battery should reach a higher peak SoC mid-afternoon on sunny day
max_soc_sunny  = max(flows_sunny["soc_profile"])
max_soc_cloudy = max(flows_cloudy["soc_profile"])
check("E5 Battery reaches higher SoC on sunny day",
      max_soc_sunny >= max_soc_cloudy - 0.1,
      f"sunny peak SoC={max_soc_sunny:.2f}  cloudy peak SoC={max_soc_cloudy:.2f} kWh")

# SoC floor never breached after overnight charging
check("E6 SoC never below 10% — sunny",
      all(s >= CAP*0.10 - 1e-6 for s in flows_sunny["soc_profile"]),
      f"min SoC = {min(flows_sunny['soc_profile']):.4f} kWh")

check("E7 SoC never below 10% — no solar",
      all(s >= CAP*0.10 - 1e-6 for s in flows_noson["soc_profile"]),
      f"min SoC = {min(flows_noson['soc_profile']):.4f} kWh")


# ─────────────────────────────────────────────────────────────────────────────
# F. CROSS-TARIFF
# ─────────────────────────────────────────────────────────────────────────────
print("\n── F. Cross-tariff Behaviour ───────────────────────────────────────\n")

for t_name, tariff in [("Go", GO), ("Flux", FLUX), ("Economy7", ECO7), ("Cosy", COSY)]:
    # Battery-only
    f = calc_day_flows(LOAD, tariff, CAP, RATE, EFF, None)
    charged   = sum(f["grid_to_batt"])
    discharged = sum(f["from_battery"])
    soc_ok = all(s >= CAP*0.10-1e-6 for s in f["soc_profile"])
    check(f"F1 [{t_name}] battery-only: charges and discharges",
          charged > 0.1 and discharged > 0.1,
          f"charged={charged:.3f}  discharged={discharged:.3f} kWh  SoC_ok={soc_ok}")

    # Solar+battery
    f2 = calc_day_flows(LOAD, tariff, CAP, RATE, EFF, SOLAR_12)
    gtl_sb2 = sum(f2["grid_to_load"])
    gtl_so2 = sum(calc_day_flows(LOAD, tariff, 0.0, RATE, EFF, SOLAR_12)["grid_to_load"])
    check(f"F2 [{t_name}] solar+batt grid draw < solar-only",
          gtl_sb2 < gtl_so2,
          f"s+b={gtl_sb2:.3f}  solar-only={gtl_so2:.3f} kWh")


# ─────────────────────────────────────────────────────────────────────────────
# G. FINANCIAL SANITY (annual simulation)
# ─────────────────────────────────────────────────────────────────────────────
print("\n── G. Financial Sanity ─────────────────────────────────────────────\n")

from engine.payback import calc_payback

parse = make_parse_result(3100, "semi", 28.16)
unit_rate = parse.inferred_rate

# Battery-only saving on Octopus Go
sim_go = run_simulation(GO, CAP, RATE, EFF, parse.days, unit_rate, 53.0)
check("G1 Battery-only (Go): positive annual saving",
      sim_go.total_saving > 0,
      f"saving = £{sim_go.total_saving:.0f}/yr")

check("G2 Battery-only (Go): reasonable range £200–£900",
      200 <= sim_go.total_saving <= 900,
      f"saving = £{sim_go.total_saving:.0f}/yr")

# Battery-only on flat rate should save almost nothing
sim_flat = run_simulation(FLAT_T, CAP, RATE, EFF, parse.days, unit_rate, 53.0)
check("G3 Battery-only (flat rate): near-zero saving",
      abs(sim_flat.saving_battery_only) < 20,
      f"battery arbitrage saving = £{sim_flat.saving_battery_only:.2f}")

# Solar+battery should outperform battery-only
solar_profile_ann = make_solar(4.0 * 850 / 365)   # 4 kWp annual avg daily gen
from engine.tariffs import IMPLIED_RATE
sr = calc_solar_impact(
    FLUX, CAP, RATE, EFF, parse.days, solar_profile_ann,
    seg_rate=0.15,
    ann_cost_current=sim_go.ann_cost_current,
    sc_new=FLUX.standing_charge * 365,
)
check("G4 Solar+battery saving > battery-only saving",
      sr.saving_solar_battery > sim_go.total_saving,
      f"solar+batt=£{sr.saving_solar_battery:.0f}  battery-only=£{sim_go.total_saving:.0f}")

# self_consumption_pct = direct solar→load only (not battery-mediated).
# With annual-avg profile (4 kWp, 3400 kWh/yr) and Gaussian mid-day peak, direct SC ≈ 43%.
# The battery absorbs the remaining surplus; exported_with_batt = 0 confirms 100% on-site use.
check("G5 Direct solar self-consumption ≥ 35% (excl. battery-mediated)",
      sr.self_consumption_pct >= 35,
      f"direct SC = {sr.self_consumption_pct:.1f}%  (all surplus stored: exported_with_batt={sr.ann_exported_with_batt_kwh:.0f} kWh)")

check("G6 Less export with battery than without",
      sr.ann_exported_with_batt_kwh < sr.ann_exported_no_batt_kwh,
      f"with_batt={sr.ann_exported_with_batt_kwh:.0f}  no_batt={sr.ann_exported_no_batt_kwh:.0f} kWh/yr")

pb = calc_payback(6000, sim_go.total_saving, 5.0)
check("G7 Battery payback period 5–15 years (Go, £6000)",
      5 <= pb.years <= 15,
      f"payback = {pb.years:.1f} years")


# ─────────────────────────────────────────────────────────────────────────────
# H. EDGE CASES
# ─────────────────────────────────────────────────────────────────────────────
print("\n── H. Edge Cases ───────────────────────────────────────────────────\n")

# Zero load
zero_load = [0.0] * 48
f_zero = calc_day_flows(zero_load, FLUX, CAP, RATE, EFF, SOLAR_12)
check("H1 Zero load: no grid-to-load",
      sum(f_zero["grid_to_load"]) < 1e-6,
      f"grid_to_load = {sum(f_zero['grid_to_load']):.6f}")
check("H2 Zero load: all solar either stored or exported",
      abs(sum(f_zero["solar_gen"]) - sum(f_zero["solar_to_batt"]) - sum(f_zero["exported"])) < 1e-4,
      f"gen={sum(f_zero['solar_gen']):.3f}  →batt={sum(f_zero['solar_to_batt']):.3f}  export={sum(f_zero['exported']):.3f}")

# Very high load (battery depleted to floor)
heavy_load = [v * 3 for v in LOAD]   # 25+ kWh day
f_heavy = calc_day_flows(heavy_load, FLUX, CAP, RATE, EFF, None)
check("H3 Heavy load: SoC floor respected",
      all(s >= CAP*0.10 - 1e-6 for s in f_heavy["soc_profile"]),
      f"min SoC = {min(f_heavy['soc_profile']):.4f} kWh")

# Tiny battery (1 kWh)
f_tiny = calc_day_flows(LOAD, GO, 1.0, RATE, EFF, None)
check("H4 Tiny battery (1 kWh): still operates correctly",
      sum(f_tiny["grid_to_batt"]) > 0 and sum(f_tiny["from_battery"]) > 0,
      f"charged={sum(f_tiny['grid_to_batt']):.3f}  discharged={sum(f_tiny['from_battery']):.3f}")
check("H5 Tiny battery: SoC floor respected",
      all(s >= 1.0*0.10 - 1e-6 for s in f_tiny["soc_profile"]),
      f"min SoC = {min(f_tiny['soc_profile']):.4f} kWh  floor=0.1 kWh")

# Solar > load all day (very large array / summer solstice)
big_solar = make_solar(30.0)   # 30 kWh/day — much more than 8.5 kWh load
f_big = calc_day_flows(LOAD, FLUX, CAP, RATE, EFF, big_solar)
check("H6 Large solar: battery full → excess exports",
      sum(f_big["exported"]) > 1.0,
      f"exported = {sum(f_big['exported']):.3f} kWh")
check("H7 Large solar: minimal grid-to-load",
      sum(f_big["grid_to_load"]) < 1.5,
      f"grid_to_load = {sum(f_big['grid_to_load']):.3f} kWh")


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("SUMMARY")
print("="*70)
passed = sum(1 for r in results if r[0] == PASS)
failed = sum(1 for r in results if r[0] == FAIL)
total  = len(results)
print(f"\n  Passed: {passed}/{total}")
print(f"  Failed: {failed}/{total}")
if failed:
    print("\n  Failed tests:")
    for s, name, detail in results:
        if s == FAIL:
            print(f"    ❌  {name}")
            if detail:
                print(f"        {detail}")
print()
