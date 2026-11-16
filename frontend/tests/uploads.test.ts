// Unit tests for the in-memory store of chosen usage files. Run: npm test
import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";

import type { UsageCheckResponse } from "../lib/api-v2-types.ts";
import { addFiles, clearUploads, getUploads, removeFile, setCheck } from "../lib/uploads.ts";

const file = (name: string, body = "x", lastModified = 1) => new File([body], name, { lastModified });
const fakeCheck: UsageCheckResponse = { schema_version: "2.0", files: [], combined: null };

beforeEach(() => clearUploads());

test("adds files and skips exact duplicates", () => {
  const a = file("a.csv");
  addFiles([a, file("b.csv")]);
  addFiles([file("a.csv")]);                 // same name, size and time: a duplicate
  addFiles([file("a.csv", "x", 2)]);         // same name but re-exported later: kept
  assert.deepEqual(getUploads().files.map((f) => `${f.name}@${f.lastModified}`), ["a.csv@1", "b.csv@1", "a.csv@2"]);
});

test("adding or removing a file clears the old check", () => {
  const a = file("a.csv");
  addFiles([a]);
  setCheck([a], fakeCheck);
  assert.equal(getUploads().check, fakeCheck);
  addFiles([file("b.csv")]);
  assert.equal(getUploads().check, null);
  setCheck(getUploads().files, fakeCheck);
  removeFile(0);
  assert.equal(getUploads().check, null);
  assert.deepEqual(getUploads().files.map((f) => f.name), ["b.csv"]);
});

test("a check for files that have since changed is ignored", () => {
  const a = file("a.csv");
  addFiles([a]);
  const stale = getUploads().files;
  addFiles([file("b.csv")]);
  setCheck(stale, fakeCheck);
  assert.equal(getUploads().check, null);
});

test("clear forgets everything", () => {
  addFiles([file("a.csv")]);
  clearUploads();
  assert.deepEqual(getUploads(), { files: [], check: null });
});
