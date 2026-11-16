// Unit tests for results-page formatting and wording. Run: npm test
import assert from "node:assert/strict";
import { test } from "node:test";

import { BREAKDOWN_LABELS, CONFIDENCE, VERDICT, gbp, gbpRange, kwh, paybackNote, plainUpgradeLabel, ukDate, years, yearsRange } from "../lib/format.ts";

test("pounds", () => {
  assert.equal(gbp(6500), "£6,500");
  assert.equal(gbp(706.7), "£707");
  assert.equal(gbp(-224), "−£224");      // a proper minus sign, before the £
  assert.equal(gbp(0), "£0");
});

test("pound ranges, in order, collapsing when equal", () => {
  assert.equal(gbpRange(4500, 8900), "£4,500 to £8,900");
  assert.equal(gbpRange(8900, 4500), "£4,500 to £8,900");
  assert.equal(gbpRange(737.2, 737.4), "£737");
  assert.equal(gbpRange(-224, 7348), "−£224 to £7,348");
});

test("years, including never", () => {
  assert.equal(years(10.43), "10.4 years");
  assert.equal(years(1), "1 year");
  assert.equal(years(null), "not within 15 years");
  assert.equal(years(undefined, 12), "not within 12 years");
});

test("year ranges", () => {
  assert.equal(yearsRange(5.9, 14.62), "5.9 to 14.6 years");
  assert.equal(yearsRange(5.9, null), "5.9 years, or not within 15 years");
  assert.equal(yearsRange(null, null), "not within 15 years");
  assert.equal(yearsRange(7, 7.01), "7 years");
});

test("kWh", () => {
  assert.equal(kwh(4851.3), "4,851 kWh");
});

test("every verdict has words and an icon, not just a colour", () => {
  for (const v of Object.values(VERDICT)) {
    assert.ok(v.title.length > 0 && v.icon.length > 0);
    assert.match(v.summary(10), /10-year warranty/);
  }
  assert.deepEqual(Object.keys(VERDICT).sort(), ["borderline", "not_yet", "worth_it"]);
});

test("every confidence level the API returns is explained", () => {
  for (const c of ["high", "medium", "low", "estimate"]) assert.ok(CONFIDENCE[c]?.label && CONFIDENCE[c]?.text);
});

test("saving breakdown labels are plain English (no 'other')", () => {
  assert.ok(!Object.values(BREAKDOWN_LABELS).some((l) => /^other$/i.test(l)));
  assert.match(BREAKDOWN_LABELS.other, /Selling stored energy/);
});

test("dates in words", () => {
  assert.equal(ukDate("2026-11-15"), "15 November 2026");
  assert.equal(ukDate("2026-01-03T10:00:00Z"), "3 January 2026");
  assert.equal(ukDate("soon"), "soon");
});

test("upgrade labels explain their acronyms", () => {
  assert.equal(plainUpgradeLabel("Solar panels (4 kWp)"), "Solar panels (4 kWp, about 10 panels)");
  assert.equal(plainUpgradeLabel("Home EV charger (7 kW)"), "Home electric car charger (7 kW)");
  assert.equal(plainUpgradeLabel("Air source heat pump"), "Air source heat pump");
});

test("payback note never says 'could be not within'", () => {
  assert.equal(paybackNote(5.9, 14.62), "Could be 5.9 to 14.6 years");
  assert.doesNotMatch(paybackNote(null, null), /could be/i);
});
