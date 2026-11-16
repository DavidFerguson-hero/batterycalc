// Generates lib/api-v2-types.ts from docs/api-v2.schema.json (the API's published contract).
// Usage: npm run gen:api-types        (write the file)
//        npm run check:api-types      (fail if the file is out of date — used in CI)
import { readFileSync, writeFileSync } from "node:fs";
import { compile } from "json-schema-to-typescript";

const SCHEMA = new URL("../../docs/api-v2.schema.json", import.meta.url);
const OUT = new URL("../lib/api-v2-types.ts", import.meta.url);

const schema = JSON.parse(readFileSync(SCHEMA, "utf8"));
const opts = { bannerComment: "", additionalProperties: false, strictIndexSignatures: true };

// Pydantic gives every field a "title", which the generator turns into a named alias per field
// (TariffKey, AnnualKwh, ...) that clash between request and response. Keep titles only on the
// models themselves ($defs entries and the root), so fields come out as plain inline types.
function stripFieldTitles(node, keep = false) {
  if (Array.isArray(node)) return node.map((n) => stripFieldTitles(n));
  if (node && typeof node === "object") {
    const out = {};
    for (const [k, v] of Object.entries(node)) {
      if (k === "title" && !keep) continue;
      if (k === "$defs") {
        out[k] = Object.fromEntries(Object.entries(v).map(([name, d]) => [name, stripFieldTitles(d, true)]));
      } else {
        out[k] = stripFieldTitles(v);
      }
    }
    return out;
  }
  return node;
}

const parts = [
  "/* Generated from docs/api-v2.schema.json by scripts/gen-api-types.mjs. Do not edit by hand. */",
  "/* eslint-disable */",
  await compile(stripFieldTitles(schema.request, true), "AssessRequest", opts),
  await compile(stripFieldTitles(schema.response, true), "AssessResponse", opts),
];
const text = parts.join("\n\n");

if (process.argv.includes("--check")) {
  const current = (() => { try { return readFileSync(OUT, "utf8"); } catch { return ""; } })();
  if (current !== text) {
    console.error("lib/api-v2-types.ts is out of date. Run: npm run gen:api-types");
    process.exit(1);
  }
  console.log("lib/api-v2-types.ts is up to date.");
} else {
  writeFileSync(OUT, text);
  console.log("wrote lib/api-v2-types.ts");
}
