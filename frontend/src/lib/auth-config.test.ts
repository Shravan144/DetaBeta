import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const authSource = readFileSync("src/auth.ts", "utf8");
const authGateSource = readFileSync("src/components/AuthGate.tsx", "utf8");

test("authentication has no built-in production secrets or demo password", () => {
  assert.doesNotMatch(authSource, /detabeta-local-nextauth-secret/);
  assert.doesNotMatch(authSource, /DEMO_USER_PASSWORD\s*\|\|\s*["']demo["']/);
});

test("demo credentials require an explicit strong password", () => {
  assert.match(authSource, /DEMO_USER_PASSWORD/);
  assert.match(authSource, /length\s*>=\s*12/);
});

test("the sign-in screen only renders providers enabled by the server", () => {
  assert.match(authGateSource, /getProviders/);
  assert.match(authGateSource, /providers\?\.credentials/);
  assert.match(authGateSource, /providers\?\.google/);
  assert.match(authGateSource, /providers\?\.github/);
});
