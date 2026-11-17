// Analytics never sends the homeowner's answers (task 3.3). Run: npm test
import assert from "node:assert/strict";
import { test } from "node:test";

import { withoutQuery } from "../lib/analytics.ts";

test("page views keep only the path, never the answers in the query string", () => {
  const ev = withoutQuery({ type: "pageview" as const, url: "https://www.batterysizer.co.uk/check/results?kwh=3500&prop=semi&tariff=octopusGo#verdict" });
  assert.deepEqual(ev, { type: "pageview", url: "https://www.batterysizer.co.uk/check/results" });
});

test("custom events are cut back the same way", () => {
  const ev = withoutQuery({ type: "event" as const, url: "https://www.batterysizer.co.uk/check/usage/upload?route=upload&ev=have" });
  assert.equal(ev?.url, "https://www.batterysizer.co.uk/check/usage/upload");
});

test("an address that can't be read isn't sent at all", () => {
  assert.equal(withoutQuery({ type: "pageview" as const, url: "not a url" }), null);
});
