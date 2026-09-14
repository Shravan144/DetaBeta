import test from "node:test";
import assert from "node:assert/strict";
import { MAX_UPLOAD_BYTES, validateCsvUpload } from "./upload-validation.ts";

function file(name: string, size: number): File {
  return { name, size } as File;
}

test("accepts a CSV at the configured upload boundary", () => {
  assert.equal(validateCsvUpload(file("data.csv", MAX_UPLOAD_BYTES)), null);
});

test("rejects a file larger than 25 MiB before upload", () => {
  assert.match(validateCsvUpload(file("data.csv", MAX_UPLOAD_BYTES + 1)) || "", /25 MB/);
});

test("rejects a non-CSV file", () => {
  assert.match(validateCsvUpload(file("data.xlsx", 1)) || "", /CSV/i);
});
