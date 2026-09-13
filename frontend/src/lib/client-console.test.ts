import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const clientRoots = ["src/app", "src/components", "src/context"];

function sourceFiles(path: string): string[] {
  return readdirSync(path).flatMap((entry) => {
    const child = join(path, entry);
    return statSync(child).isDirectory()
      ? sourceFiles(child)
      : /\.(ts|tsx)$/.test(child)
        ? [child]
        : [];
  });
}

test("handled client failures do not trigger the Next.js console-error overlay", () => {
  const offenders = clientRoots
    .flatMap(sourceFiles)
    .filter((file) => readFileSync(file, "utf8").includes("console.error"));

  assert.deepEqual(offenders, []);
});
