// Unit tests for the journey's URL state. Run: npm test (Node's built-in runner, no extra dependencies).
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  DEFAULT_JOURNEY, hasNothing, homeToRequest, parseJourney, stepHref, writeJourney,
} from "../lib/journey.ts";

test("an empty query gives the defaults", () => {
  assert.deepEqual(parseJourney(""), DEFAULT_JOURNEY);
  assert.equal(hasNothing(parseJourney("").home), true);
});

test("reads the short keys", () => {
  const j = parseJourney("solar=have&hp=planning&ev=have&batt=have");
  assert.deepEqual(j.home, { solar: "have", heat_pump: "planning", ev: "have", battery: "have" });
});

test("invalid values fall back to none", () => {
  const j = parseJourney("solar=lots&ev=PLANNING&hp=");
  assert.deepEqual(j.home, DEFAULT_JOURNEY.home);
});

test("defaults are left out so links stay short", () => {
  assert.equal(writeJourney(DEFAULT_JOURNEY), "");
  const q = writeJourney({ home: { ...DEFAULT_JOURNEY.home, ev: "planning" } });
  assert.equal(q, "ev=planning");
});

test("round trip", () => {
  const home = { solar: "planning", heat_pump: "have", ev: "none", battery: "have" } as const;
  assert.deepEqual(parseJourney(writeJourney({ home })).home, home);
});

test("other steps' answers in the query are kept", () => {
  const q = writeJourney({ home: { ...DEFAULT_JOURNEY.home, ev: "have" } }, "kwh=3500&route=estimate&ev=planning");
  const p = new URLSearchParams(q);
  assert.equal(p.get("ev"), "have");
  assert.equal(p.get("kwh"), "3500");
  assert.equal(p.get("route"), "estimate");
});

test("setting an item back to none removes it", () => {
  assert.equal(writeJourney(DEFAULT_JOURNEY, "ev=have&kwh=3000"), "kwh=3000");
});

test("output order is stable for identical answers", () => {
  const a = writeJourney(parseJourney("hp=have&ev=have"));
  const b = writeJourney(parseJourney("ev=have&hp=have"));
  assert.equal(a, b);
});

test("step links carry the answers", () => {
  assert.equal(stepHref("/check/usage", "ev=have"), "/check/usage?ev=have");
  assert.equal(stepHref("/check/usage", ""), "/check/usage");
});

test("maps EV and heat pump onto the API request", () => {
  const home = parseJourney("ev=planning&hp=have&solar=have").home;
  assert.deepEqual(homeToRequest(home), { ev: { status: "planning" }, heat_pump: { status: "have" } });
});
