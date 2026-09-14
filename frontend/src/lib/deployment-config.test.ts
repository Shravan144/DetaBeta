import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

test("the repository does not force the unavailable experimental Services preset", () => {
  const configPath = resolve("..", "vercel.json");
  if (!existsSync(configPath)) return;

  const config = JSON.parse(readFileSync(configPath, "utf8")) as Record<string, unknown>;
  assert.equal("experimentalServices" in config, false);
});
