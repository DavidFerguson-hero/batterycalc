// Unit tests for sharing and the printable summary. Run: npm test
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { milestones, printableUrl, shareNote } from "../lib/summary.ts";

test("milestone years pick the matching values and skip years the chart doesn't have", () => {
  const years = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
  const values = years.map((y) => y * 100 - 600);
  assert.deepEqual(milestones(years, values, [0, 5, 10, 15]), [
    { year: 0, value: -600 },
    { year: 5, value: -100 },
    { year: 10, value: 400 },
  ]);
});

test("the share note warns that uploaded files aren't in the link", () => {
  assert.match(shareNote("upload"), /not your usage file/);
  assert.match(shareNote("upload"), /add the file again/);
  assert.doesNotMatch(shareNote("estimate"), /file/);
});

test("printed links drop the protocol", () => {
  assert.equal(printableUrl("https://batterysizer.co.uk/check/results?route=estimate"), "batterysizer.co.uk/check/results?route=estimate");
  assert.equal(printableUrl("http://localhost:3000/x"), "localhost:3000/x");
});

test("printing hides the page only when the results summary is there", () => {
  const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
  // Every page-hiding rule must be scoped to a body that contains the summary,
  // or printing any other page would come out blank.
  const hiding = css.match(/[^{}]*\{\s*display:\s*none\s*!important;?\s*\}/g) ?? [];
  assert.ok(hiding.length > 0);
  for (const rule of hiding) assert.match(rule, /body:has\(> \.print-root\)/);
});
