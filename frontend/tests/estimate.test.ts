// Unit tests for the quick-estimate answers and suggested annual use. Run: npm test
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  DEFAULT_ESTIMATE, isComplete, parseEstimate, peopleFactor, suggestKwh, typicalKwh, writeEstimate,
} from "../lib/estimate.ts";

test("empty query gives defaults (gas heating, nothing else)", () => {
  assert.deepEqual(parseEstimate(""), DEFAULT_ESTIMATE);
  assert.equal(isComplete(DEFAULT_ESTIMATE), false);
});

test("round trip, keeping other answers in the query", () => {
  const e = { annualKwh: 3800, propertyType: "semi", bedrooms: 3, heating: "electric", people: 4,
              evMiles: 9000, floorArea: 92, epcRating: "C" } as const;
  const q = writeEstimate(e, "ev=planning&route=estimate");
  assert.deepEqual(parseEstimate(q), e);
  const p = new URLSearchParams(q);
  assert.equal(p.get("ev"), "planning");
  assert.equal(p.get("route"), "estimate");
  assert.equal(isComplete(parseEstimate(q)), true);
});

test("gas heating and empty answers are left out of the link", () => {
  assert.equal(writeEstimate({ ...DEFAULT_ESTIMATE, annualKwh: 3000, propertyType: "flat" }), "kwh=3000&prop=flat");
});

test("never writes a postcode or address", () => {
  const q = writeEstimate({ ...DEFAULT_ESTIMATE, annualKwh: 3000, propertyType: "flat" }, "postcode=AB1+2CD");
  // Unknown keys already in the query are kept, but the estimate itself never adds location data.
  assert.ok(!writeEstimate({ ...DEFAULT_ESTIMATE, propertyType: "flat" }).includes("postcode"));
  assert.ok(q.includes("postcode"));
});

test("out-of-range or malformed values are ignored", () => {
  const e = parseEstimate("kwh=50&prop=castle&beds=9&people=0&miles=-5&area=3&epc=Z&heat=solar");
  assert.deepEqual(e, DEFAULT_ESTIMATE);
  assert.equal(parseEstimate("kwh=3500.7").annualKwh, null);
  assert.equal(parseEstimate("epc=c").epcRating, "C");
});

test("typical use comes from the BEIS table, nearest size when off the table", () => {
  assert.equal(typicalKwh("semi", 3), 3500);
  assert.equal(typicalKwh("flat", 5), 2900);
  assert.equal(typicalKwh("detached", 1), 4200);
});

test("people: typical household = no change; more people use more; clamped", () => {
  assert.equal(peopleFactor(null, 3), 1);
  assert.ok(Math.abs(peopleFactor(3, 4) - 1) < 1e-9);
  assert.ok(peopleFactor(5, 3) > 1 && peopleFactor(1, 3) < 1);
  assert.equal(peopleFactor(6, 1), 1.4);                          // 6 people in 1 bedroom: capped
  assert.ok(Math.abs(peopleFactor(1, 5) - 0.724) < 1e-9);          // 1 person in 5 bedrooms: 1 − 0.12 × 2.3
  assert.ok(peopleFactor(1, 5) >= 0.7);
});

test("suggested use: gas home is everyday use × people, rounded to 100", () => {
  assert.equal(suggestKwh("semi", 3, null), 3500);
  assert.equal(suggestKwh("semi", 3, 4) % 100, 0);
  assert.ok(suggestKwh("semi", 3, 4) > 3500);
});

test("suggested use: electric heating from the EPC is kept, only everyday use changes with people", () => {
  // EPC estimate 9,000 for a 2-bed flat with storage heaters: 2,400 everyday + 6,600 heating.
  assert.equal(suggestKwh("flat", 2, null, 9000), 9000);
  const withFour = suggestKwh("flat", 2, 4, 9000);
  assert.equal(withFour, Math.round((2400 * peopleFactor(4, 2) + 6600) / 100) * 100);
});

test("suggested use stays within 500–20,000", () => {
  assert.equal(suggestKwh("detached", 5, 6, 30000), 20000);
});
