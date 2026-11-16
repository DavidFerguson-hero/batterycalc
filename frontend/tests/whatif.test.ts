// Unit tests for what-ifs and the day-in-the-life summary. Run: npm test
import assert from "node:assert/strict";
import { test } from "node:test";

import type { AssessRequest } from "../lib/api-v2-types.ts";
import { chargeWindow, slotTime, summariseDay } from "../lib/dayinlife.ts";
import { alreadyIncludedNote, applyWhatIf, initialWhatIf, sameWhatIf } from "../lib/whatif.ts";

const base: AssessRequest = {
  usage: { route: "estimate", annual_kwh: 3500, property_type: "semi", heating_type: "gas" },
  ev: { status: "none" },
  heat_pump: { status: "planning", floor_area_m2: 90, epc_rating: "D" },
  tariff: { current_tariff_key: "octopusGo" },
  battery: {},
};

test("the starting what-if matches the answer they already have", () => {
  const w = initialWhatIf({ battery_kwh: 10, installed_price: 6500 }, "none", "planning");
  assert.deepEqual(w, { sizeKwh: 10, priceGbp: 6500, ev: false, heatPump: true, solar: false });
  assert.ok(sameWhatIf(w, { ...w }));
  assert.ok(!sameWhatIf(w, { ...w, priceGbp: 6000 }));
});

test("a what-if fixes the battery size and price, and keeps their other answers", () => {
  const r = applyWhatIf(base, { sizeKwh: 13.5, priceGbp: 7999.6, ev: false, heatPump: true, solar: false });
  assert.deepEqual(r.battery, { size_kwh: 13.5, price_gbp: 8000 });
  assert.deepEqual(r.heat_pump, base.heat_pump);
  assert.deepEqual(r.tariff, base.tariff);
  assert.deepEqual(r.usage, base.usage);
});

test("adding a car plans one; removing a planned heat pump drops it", () => {
  const r = applyWhatIf(base, { sizeKwh: 10, priceGbp: 6500, ev: true, heatPump: false, solar: false });
  assert.deepEqual(r.ev, { status: "planning" });
  assert.deepEqual(r.heat_pump, { status: "none" });
});

test("a car or heat pump they already have can't be switched off", () => {
  const have = { ...base, ev: { status: "have" as const, annual_miles: 9000 } };
  const r = applyWhatIf(have, { sizeKwh: 10, priceGbp: 6500, ev: false, heatPump: true, solar: false });
  assert.deepEqual(r.ev, { status: "have", annual_miles: 9000 });
});

test("prices are kept inside what the API accepts", () => {
  assert.equal(applyWhatIf(base, { sizeKwh: 5, priceGbp: 10, ev: false, heatPump: false, solar: false }).battery?.price_gbp, 500);
  assert.equal(applyWhatIf(base, { sizeKwh: 5, priceGbp: 1e6, ev: false, heatPump: false, solar: false }).battery?.price_gbp, 50000);
});

// ── Solar what-ifs (H17) ──────────────────────────────────────────────────────

const noSolar = { sizeKwh: 10, priceGbp: 6500, ev: false, heatPump: true, solar: false };

test("solar they have or plan starts ticked", () => {
  assert.equal(initialWhatIf({ battery_kwh: 10, installed_price: 6500 }, "none", "none", "planning").solar, true);
  assert.equal(initialWhatIf({ battery_kwh: 10, installed_price: 6500 }, "none", "none", "have").solar, true);
  assert.equal(initialWhatIf({ battery_kwh: 10, installed_price: 6500 }, "none", "none").solar, false);
  assert.ok(!sameWhatIf(noSolar, { ...noSolar, solar: true }));
});

test("ticking solar plans panels; unticking drops planned ones", () => {
  assert.deepEqual(applyWhatIf(base, { ...noSolar, solar: true }).solar, { status: "planning" });
  const planned = { ...base, solar: { status: "planning" as const, kwp: 3 } };
  assert.deepEqual(applyWhatIf(planned, { ...noSolar, solar: true }).solar, { status: "planning", kwp: 3 });
  assert.deepEqual(applyWhatIf(planned, noSolar).solar, { status: "none" });
});

test("solar panels they already have can't be switched off", () => {
  const have = { ...base, solar: { status: "have" as const } };
  assert.deepEqual(applyWhatIf(have, noSolar).solar, { status: "have" });
});

test("the already-included note", () => {
  assert.equal(alreadyIncludedNote("none", "none", "planning"), null);
  assert.equal(alreadyIncludedNote("have", "none", "none"), "Your electric car is already included.");
  assert.equal(alreadyIncludedNote("none", "none", "have"), "Your solar panels are already included.");
  assert.equal(alreadyIncludedNote("have", "have", "have"),
    "Your electric car, heat pump and solar panels are already included.");
});

test("half-hour slot times", () => {
  assert.equal(slotTime(0), "00:00");
  assert.equal(slotTime(1), "00:30");
  assert.equal(slotTime(47), "23:30");
  assert.equal(slotTime(48), "00:00");
});

const zeros = () => Array(48).fill(0);

test("charging window, including one that runs past midnight", () => {
  const night = zeros(); for (let i = 1; i < 9; i++) night[i] = 1.5;          // 00:30–04:30
  assert.equal(chargeWindow(night), "00:30 to 04:30");
  const wrap = zeros(); for (const i of [46, 47, 0, 1, 2, 3]) wrap[i] = 1;     // 23:00–02:00
  assert.equal(chargeWindow(wrap), "23:00 to 02:00");
  const two = zeros(); two[4] = 1; for (let i = 26; i < 30; i++) two[i] = 1;  // longest run wins
  assert.equal(chargeWindow(two), "13:00 to 15:00");
  assert.equal(chargeWindow(zeros()), null);
});

test("day summary", () => {
  const d = { load: Array(48).fill(0.5), grid_to_battery: zeros(), from_battery: zeros(), grid_to_home: zeros(), battery_level: zeros() };
  for (let i = 2; i < 10; i++) d.grid_to_battery[i] = 1;
  for (let i = 32; i < 44; i++) d.from_battery[i] = 0.5;
  const s = summariseDay(d);
  assert.equal(s.use, 24);
  assert.equal(s.fromBattery, 6);
  assert.equal(s.share, 0.25);
  assert.equal(s.charged, 8);
  assert.equal(s.window, "01:00 to 05:00");
});
