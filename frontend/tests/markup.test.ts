// Static checks on component markup. Run: npm test
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";

const ROOTS = ["components", "app"];

function tsxFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    return statSync(p).isDirectory() ? tsxFiles(p) : p.endsWith(".tsx") ? [p] : [];
  });
}

// Elements that are, or render their children inside, a <label>.
const LABEL_LIKE = ["label", "RadioCard"];

test("no <Term> (a button) inside a <label>", () => {
  // A button inside a label is invalid HTML and blanks the form field's accessible name.
  // This happened twice while building the journey, so it's checked here.
  const offenders: string[] = [];
  for (const file of ROOTS.flatMap(tsxFiles)) {
    const src = readFileSync(file, "utf8");
    for (const tag of LABEL_LIKE) {
      for (const m of src.matchAll(new RegExp(`<${tag}\\b[^>]*>([\\s\\S]*?)<\\/${tag}>`, "g"))) {
        if (/<Term\b/.test(m[1])) offenders.push(`${file}: ${m[0].slice(0, 80).replace(/\s+/g, " ")}…`);
      }
    }
  }
  assert.deepEqual(offenders, []);
});

test("no <Term> inside a <Link> or <a>", () => {
  const offenders: string[] = [];
  for (const file of ROOTS.flatMap(tsxFiles)) {
    const src = readFileSync(file, "utf8");
    for (const m of src.matchAll(/<(Link|a)\b[^>]*>([\s\S]*?)<\/\1>/g)) {
      if (/<Term\b/.test(m[2])) offenders.push(`${file}: ${m[0].slice(0, 80).replace(/\s+/g, " ")}…`);
    }
  }
  assert.deepEqual(offenders, []);
});
