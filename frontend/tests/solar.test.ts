// Unit tests for the results page's solar lines (H17). Run: npm test
import assert from "node:assert/strict";
import { test } from "node:test";

import { solarAssumption, solarContextNote } from "../lib/solar.ts";

const modelled = {
  status: "have" as const, kwp: 4, orientation: "south" as const, annual_generation_kwh: 3400,
  modelled: true, used_at_home_kwh: 1298, spare_kwh: 2102,
};

test("no solar, no lines", () => {
  assert.equal(solarContextNote(null), "");
  assert.equal(solarAssumption(undefined), null);
});

test("modelled solar is described with its size and generation", () => {
  assert.equal(solarContextNote(modelled), "Your answer above includes your solar panels.");
  assert.equal(solarAssumption(modelled),
    "4 kWp (kilowatts peak) facing south, making about 3,400 kWh a year, of which about 2,102 kWh is spare without a battery. Spare solar charges the battery first.");
});

test("planned panels say their own cost isn't counted", () => {
  assert.match(solarContextNote({ ...modelled, status: "planning" }), /planning\. The panels' own cost isn't included/);
});

test("panels already in uploaded readings are left as they are", () => {
  const s = { ...modelled, modelled: false, used_at_home_kwh: null, spare_kwh: null };
  assert.match(solarContextNote(s), /meter readings already include/);
  assert.equal(solarAssumption(s), "Already in your meter readings, so we use them as they are");
});
