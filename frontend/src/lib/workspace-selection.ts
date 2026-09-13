export type PersistedWorkspaceTab =
  | "landing"
  | "dashboard"
  | "overview"
  | "dataset"
  | "diagnostics"
  | "investigation"
  | "feature-lab"
  | "experiment"
  | "explain"
  | "report";

interface IdentifiedResource {
  id: number;
}

interface ReconcileWorkspaceSelectionInput {
  projects: IdentifiedResource[];
  datasets: IdentifiedResource[];
  savedProjectId: number | null;
  savedDatasetId: number | null;
  savedTab: PersistedWorkspaceTab;
}

export interface ReconciledWorkspaceSelection {
  projectId: number | null;
  datasetId: number | null;
  tab: PersistedWorkspaceTab;
}

export function workspaceStorageKey(
  userId: string,
  field: "projectId" | "datasetId" | "activeTab",
): string {
  return `detabeta:${encodeURIComponent(userId)}:${field}`;
}

export function parsePersistedId(value: string | null): number | null {
  if (value === null || value.trim() === "") return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
}

export function reconcileWorkspaceSelection({
  projects,
  datasets,
  savedProjectId,
  savedDatasetId,
  savedTab,
}: ReconcileWorkspaceSelectionInput): ReconciledWorkspaceSelection {
  if (savedProjectId === null || !projects.some((project) => project.id === savedProjectId)) {
    return { projectId: null, datasetId: null, tab: "dashboard" };
  }

  if (savedDatasetId !== null && !datasets.some((dataset) => dataset.id === savedDatasetId)) {
    return { projectId: savedProjectId, datasetId: null, tab: "overview" };
  }

  return {
    projectId: savedProjectId,
    datasetId: savedDatasetId,
    tab: savedTab === "landing" || savedTab === "dashboard" ? "overview" : savedTab,
  };
}
