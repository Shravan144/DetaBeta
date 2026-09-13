import assert from "node:assert/strict";
import test from "node:test";

import { reconcileWorkspaceSelection } from "./workspace-selection.ts";

test("clears a saved project that is not visible to the signed-in user", () => {
  assert.deepEqual(
    reconcileWorkspaceSelection({
      projects: [{ id: 3 }, { id: 4 }],
      datasets: [],
      savedProjectId: 1,
      savedDatasetId: 2,
      savedTab: "feature-lab",
    }),
    {
      projectId: null,
      datasetId: null,
      tab: "dashboard",
    },
  );
});

test("keeps a valid project but clears a dataset from another project", () => {
  assert.deepEqual(
    reconcileWorkspaceSelection({
      projects: [{ id: 3 }],
      datasets: [{ id: 4 }],
      savedProjectId: 3,
      savedDatasetId: 99,
      savedTab: "dataset",
    }),
    {
      projectId: 3,
      datasetId: null,
      tab: "overview",
    },
  );
});

test("keeps a fully valid saved workspace", () => {
  assert.deepEqual(
    reconcileWorkspaceSelection({
      projects: [{ id: 3 }],
      datasets: [{ id: 4 }],
      savedProjectId: 3,
      savedDatasetId: 4,
      savedTab: "diagnostics",
    }),
    {
      projectId: 3,
      datasetId: 4,
      tab: "diagnostics",
    },
  );
});
