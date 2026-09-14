import test from "node:test";
import assert from "node:assert/strict";
import { pickDefaultTarget } from "./target-selection.ts";

test("prefers an explicit outcome-like column when choosing a default target", () => {
  assert.equal(pickDefaultTarget(["age", "fare", "survived", "country"]), "survived");
});

test("returns null instead of silently choosing an arbitrary final column", () => {
  assert.equal(pickDefaultTarget(["age", "fare", "country"]), null);
});
