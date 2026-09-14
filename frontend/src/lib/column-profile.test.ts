import test from "node:test";
import assert from "node:assert/strict";
import { findColumnProfile } from "./column-profile.ts";

test("returns the exact profile for a diagnostic column", () => {
  const profile = { name: "cabin", missing_pct: 70 };
  assert.equal(findColumnProfile([profile], "cabin"), profile);
});

test("returns undefined for a column absent from the profile", () => {
  assert.equal(findColumnProfile([{ name: "age" }], "cabin"), undefined);
});
