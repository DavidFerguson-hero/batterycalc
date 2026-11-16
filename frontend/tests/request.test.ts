// Unit tests for the current-tariff answers and the API request builder. Run: npm test
import assert from "node:assert/strict";
import { test } from "node:test";

import { buildAssessRequest } from "../lib/request.ts";
import { DEFAULT_TARIFF, isTimeOfUse, parseTariff, writeTariff } from "../lib/tariff.ts";

// ── Tariff answers ────────────────────────────────────────────────────────────

test("no tariff answer means not sure", () => {
  assert.deepEqual(parseTariff(""), DEFAULT_TARIFF);
});

test("flat tariff keeps its rates; a time-of-use tariff ignores them", () => {
  assert.deepEqual(parseTariff("tariff=flat&rate=24.5&sc=60"), { choice: "flat", unitRateP: 24.5, standingP: 60, exportP: null });
  assert.deepEqual(parseTariff("tariff=octopusGo&rate=24.5&sc=60"), { choice: "octopusGo", unitRateP: null, standingP: null, exportP: null });
});

test("bad values are ignored", () => {
  const t = parseTariff("tariff=flat&rate=2&sc=abc&exp=500");
  assert.deepEqual(t, { choice: "flat", unitRateP: null, standingP: null, exportP: null });
  assert.equal(parseTariff("tariff=<script>").choice, "unsure");
  assert.equal(parseTariff("tariff=flat&rate=24.555").unitRateP, null);   // at most 2 decimal places
});

test("write: unsure leaves nothing; switching away from flat drops its rates; other answers kept", () => {
  assert.equal(writeTariff(DEFAULT_TARIFF, "kwh=3000"), "kwh=3000");
  const q = writeTariff({ choice: "octopusCosy", unitRateP: 24, standingP: 60, exportP: 15 }, "rate=24&sc=60&kwh=3000");
  assert.equal(q, "exp=15&kwh=3000&tariff=octopusCosy");
});

test("round trip", () => {
  const t = { choice: "flat", unitRateP: 26.11, standingP: 49.5, exportP: 4.1 };
  assert.deepEqual(parseTariff(writeTariff(t)), t);
});

test("which choices are time-of-use", () => {
  assert.equal(isTimeOfUse("flat"), false);
  assert.equal(isTimeOfUse("unsure"), false);
  assert.equal(isTimeOfUse("octopusGo"), true);
});

// ── Request builder ───────────────────────────────────────────────────────────

test("says what's missing", () => {
  assert.deepEqual(buildAssessRequest("").missing, ["route"]);
  assert.deepEqual(buildAssessRequest("route=estimate").missing, ["property_type", "usage_kwh"]);
  assert.deepEqual(buildAssessRequest("route=upload").missing, ["files"]);
  assert.equal(buildAssessRequest("route=upload").request, null);
});

test("estimate route with EV, heat pump and a flat tariff", () => {
  const q = "route=estimate&prop=semi&beds=3&kwh=3800&heat=electric&ev=planning&miles=9000"
          + "&hp=have&area=92&epc=C&tariff=flat&rate=24.5&sc=60&exp=15";
  const { request, missing } = buildAssessRequest(q);
  assert.deepEqual(missing, []);
  assert.deepEqual(request, {
    usage: { route: "estimate", annual_kwh: 3800, property_type: "semi", heating_type: "electric" },
    ev: { status: "planning", annual_miles: 9000 },
    heat_pump: { status: "have", floor_area_m2: 92, epc_rating: "C" },
    tariff: { unit_rate_p: 24.5, standing_charge_p: 60, export_rate_p: 15 },
    battery: {},
  });
});

test("a time-of-use tariff is sent as current_tariff_key; not sure sends no rates", () => {
  const tou = buildAssessRequest("route=estimate&prop=flat&kwh=2500&tariff=octopusGo").request!;
  assert.deepEqual(tou.tariff, { current_tariff_key: "octopusGo" });
  const unsure = buildAssessRequest("route=estimate&prop=flat&kwh=2500").request!;
  assert.deepEqual(unsure.tariff, {});
});

test("time-of-use chosen but no tariff picked yet is missing, not guessed", () => {
  const { request, missing } = buildAssessRequest("route=estimate&prop=flat&kwh=2500&tariff=tou");
  assert.equal(request, null);
  assert.deepEqual(missing, ["tariff"]);
  assert.equal(isTimeOfUse("tou"), false);
});

test("upload route needs files loaded, then sends no annual kWh", () => {
  const { request } = buildAssessRequest("route=upload&ev=have", true);
  assert.deepEqual(request!.usage, { route: "upload", property_type: "semi", heating_type: "gas" });
  assert.deepEqual(request!.ev, { status: "have" });   // typical miles assumed by the API
});
