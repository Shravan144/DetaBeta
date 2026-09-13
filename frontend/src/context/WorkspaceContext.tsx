"use client";
import React, { createContext, useCallback, useContext, useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { getBackendToken, clearBackendToken } from "@/lib/backend-token";
import {
  parsePersistedId,
  reconcileWorkspaceSelection,
  workspaceStorageKey,
} from "@/lib/workspace-selection";

export type TabName =
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

export interface Project {
  id: number;
  name: string;
  description: string;
  created_at: string;
  dataset_count: number;
}

export interface Dataset {
  id: number;
  project_id: number;
  name: string;
  storage_path: string;
  n_rows: number;
  n_columns: number;
  created_at: string;
}

export type AnalysisResult = Record<string, unknown>;

export interface RightPanelState {
  isOpen: boolean;
  type: "column" | "discovery" | "transform" | "SHAP" | null;
  data: unknown;
}

export interface ToastState {
  message: string;
  type: "success" | "error" | null;
}

export interface SessionState {
  // The real backend analysis-session id for the most recent run (or null).
  id: number | null;
  status: "idle" | "running" | "completed" | "failed";
  // Whether the most recent engine result was served from the cache.
  cached: boolean;
}

export interface SessionSummary {
  id: number;
  dataset_id: number;
  target: string | null;
  created_at: string;
  completed_engine_keys: string[];
}

interface WorkspaceContextProps {
  apiBase: string;
  setApiBase: (url: string) => void;
  projects: Project[];
  datasets: Dataset[];
  selectedProjectId: number | null;
  selectedDatasetId: number | null;
  selectedDataset: Dataset | null;
  activeTab: TabName;
  setActiveTab: (tab: TabName) => void;
  rightPanel: RightPanelState;
  openRightPanel: (type: RightPanelState["type"], data: unknown) => void;
  closeRightPanel: () => void;
  toast: ToastState;
  showToast: (message: string, type?: "success" | "error") => void;
  session: SessionState;
  setSession: React.Dispatch<React.SetStateAction<SessionState>>;
  sessions: SessionSummary[];
  loadSessions: (target?: string) => Promise<void>;
  rerunSession: (target?: string) => Promise<void>;
  loadProjects: () => Promise<void>;
  loadDatasets: (projectId: number) => Promise<void>;
  selectProject: (projectId: number | null) => Promise<void>;
  selectDataset: (datasetId: number | null) => Promise<void>;
  createProject: (name: string, description: string) => Promise<Project>;
  uploadDataset: (file: File) => Promise<Dataset>;
  deleteProject: (projectId: number) => Promise<void>;
  deleteDataset: (datasetId: number) => Promise<void>;
  runAnalysis: (
    engineKey: string,
    target?: string,
    opts?: { refresh?: boolean }
  ) => Promise<AnalysisResult>;
  applyTransform: (
    datasetId: number,
    payload: { transform: string; columns: string[]; evidence?: Record<string, unknown>; title?: string }
  ) => Promise<ApplyTransformResult>;
  apiFetch: <T,>(path: string, options?: RequestInit) => Promise<T>;
}

export interface ApplyTransformResult {
  dataset: Dataset;
  changes: string[];
  health_before: { score: number; grade: string };
  health_after: { score: number; grade: string };
}

const WorkspaceContext = createContext<WorkspaceContextProps | undefined>(undefined);

export const WorkspaceProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { data: authSession } = useSession();
  const workspaceUserId = authSession?.user?.id || authSession?.user?.email || "authenticated-user";
  const projectStorageKey = workspaceStorageKey(workspaceUserId, "projectId");
  const datasetStorageKey = workspaceStorageKey(workspaceUserId, "datasetId");
  const tabStorageKey = workspaceStorageKey(workspaceUserId, "activeTab");
  const [apiBase, setApiBaseState] = useState<string>(() => {
    if (typeof window === "undefined") return "/api";
    const saved = window.localStorage.getItem("detabetaApiBase");
    return saved && saved !== "http://127.0.0.1:8000/api" ? saved : "/api";
  });
  const [projects, setProjects] = useState<Project[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  // Start from a safe empty workspace. Persisted IDs are restored only after
  // the backend confirms that they belong to the current signed-in user.
  const [selectedProjectId, setSelectedProjectIdState] = useState<number | null>(null);
  const [selectedDatasetId, setSelectedDatasetIdState] = useState<number | null>(null);
  const [selectedDataset, setSelectedDataset] = useState<Dataset | null>(null);
  const [activeTab, setActiveTabState] = useState<TabName>("dashboard");

  const setActiveTab = (tab: TabName) => {
    setActiveTabState(tab);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(tabStorageKey, tab);
    }
  };

  const setSelectedProjectId = (id: number | null) => {
    setSelectedProjectIdState(id);
    if (typeof window !== "undefined") {
      if (id !== null) window.localStorage.setItem(projectStorageKey, String(id));
      else window.localStorage.removeItem(projectStorageKey);
    }
  };

  const setSelectedDatasetId = (id: number | null) => {
    setSelectedDatasetIdState(id);
    if (typeof window !== "undefined") {
      if (id !== null) window.localStorage.setItem(datasetStorageKey, String(id));
      else window.localStorage.removeItem(datasetStorageKey);
    }
  };
  
  const [rightPanel, setRightPanel] = useState<RightPanelState>({
    isOpen: false,
    type: null,
    data: null,
  });

  const [toast, setToast] = useState<ToastState>({
    message: "",
    type: null,
  });

  const [session, setSession] = useState<SessionState>({
    id: null,
    status: "idle",
    cached: false,
  });

  // History of analysis sessions for the selected dataset.
  const [sessions, setSessions] = useState<SessionSummary[]>([]);

  // In-memory cache of engine results for the current visit, keyed by
  // `${datasetId}:${target}:${engineKey}`. This skips redundant network calls
  // when switching between tabs; the backend also caches, so this is purely a
  // client-side speed-up. Cleared whenever the selected dataset changes.
  const resultsCacheRef = React.useRef<Map<string, AnalysisResult>>(new Map());

  const setApiBase = (url: string) => {
    setApiBaseState(url);
    if (typeof window !== "undefined") {
      window.localStorage.setItem("detabetaApiBase", url);
    }
  };

  const showToast = useCallback((message: string, type: "success" | "error" = "success") => {
    setToast({ message, type });
    setTimeout(() => {
      setToast({ message: "", type: null });
    }, 3000);
  }, []);

  const openRightPanel = (type: RightPanelState["type"], data: unknown) => {
    setRightPanel({ isOpen: true, type, data });
  };

  const closeRightPanel = () => {
    setRightPanel((prev) => ({ ...prev, isOpen: false }));
  };

  // Helper fetch function
  const apiFetch = useCallback(async <T,>(path: string, options: RequestInit = {}): Promise<T> => {
    let token: string;
    try {
      token = await getBackendToken();
    } catch {
      showToast("Authentication failed. Please sign in again.", "error");
      throw new Error("Authentication failed");
    }

    const authHeader = { Authorization: `Bearer ${token}` };
    const headers = options.body instanceof FormData 
      ? { ...authHeader, ...(options.headers || {}) }
      : { "Content-Type": "application/json", ...authHeader, ...(options.headers || {}) };

    const url = `${apiBase.replace(/\/$/, "")}${path}`;
    
    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      // Clear backend token on auth failure so next request fetches a fresh one.
      if (response.status === 401) {
        clearBackendToken();
      }

      const contentType = response.headers.get("content-type") || "";
      let data: unknown;
      if (contentType.includes("application/json")) {
        data = await response.json();
      } else {
        data = await response.text();
      }

      if (!response.ok) {
        const errorData = typeof data === "object" && data !== null ? data as Record<string, unknown> : {};
        const errorDetail = errorData.detail || errorData.message || response.statusText || "Request failed";
        throw new Error(typeof errorDetail === "string" ? errorDetail : JSON.stringify(errorDetail));
      }

      return data as T;
    } catch (error: unknown) {
      showToast(error instanceof Error ? error.message : "Network error occurred", "error");
      throw error;
    }
  }, [apiBase, showToast]);

  // Like apiFetch, but also returns response headers so callers can read the
  // cache metadata (X-DetaBeta-Cached / X-DetaBeta-Session-Id) the analysis
  // endpoints attach.
  const apiFetchWithHeaders = useCallback(async <T,>(path: string, options: RequestInit = {}) => {
    let token: string;
    try {
      token = await getBackendToken();
    } catch {
      showToast("Authentication failed. Please sign in again.", "error");
      throw new Error("Authentication failed");
    }

    const authHeader = { Authorization: `Bearer ${token}` };
    const headers = options.body instanceof FormData
      ? { ...authHeader, ...(options.headers || {}) }
      : { "Content-Type": "application/json", ...authHeader, ...(options.headers || {}) };
    const url = `${apiBase.replace(/\/$/, "")}${path}`;
    try {
      const response = await fetch(url, { ...options, headers });

      if (response.status === 401) {
        clearBackendToken();
      }

      const contentType = response.headers.get("content-type") || "";
      const data: unknown = contentType.includes("application/json")
        ? await response.json()
        : await response.text();
      if (!response.ok) {
        const errorData = typeof data === "object" && data !== null ? data as Record<string, unknown> : {};
        const errorDetail = errorData.detail || errorData.message || response.statusText || "Request failed";
        throw new Error(typeof errorDetail === "string" ? errorDetail : JSON.stringify(errorDetail));
      }
      return { data: data as T, headers: response.headers };
    } catch (error: unknown) {
      showToast(error instanceof Error ? error.message : "Network error occurred", "error");
      throw error;
    }
  }, [apiBase, showToast]);

  const loadProjects = async () => {
    const data = await apiFetch<Project[]>("/projects");
    setProjects(data);
  };

  const loadDatasets = async (projectId: number) => {
    const data = await apiFetch<Dataset[]>(`/projects/${projectId}/datasets`);
    setDatasets(data);
  };

  const selectProject = async (projectId: number | null) => {
    setSelectedDatasetId(null);
    setSelectedDataset(null);
    setDatasets([]);
    resultsCacheRef.current.clear();
    setSessions([]);
    setSession({ id: null, status: "idle", cached: false });
    closeRightPanel();
    if (projectId) {
      if (!projects.some((project) => project.id === projectId)) {
        setSelectedProjectId(null);
        setActiveTab("dashboard");
        showToast("That project is no longer available. The project list was refreshed.", "error");
        await loadProjects().catch(() => undefined);
        return;
      }

      try {
        const data = await apiFetch<Dataset[]>(`/projects/${projectId}/datasets`);
        setDatasets(data);
        setSelectedProjectId(projectId);
        showToast(`Switched to Project #${projectId}`);
        setActiveTab("overview");
      } catch {
        setSelectedProjectId(null);
        setActiveTab("dashboard");
        await loadProjects().catch(() => undefined);
      }
    } else {
      setSelectedProjectId(null);
      setActiveTab("dashboard");
    }
  };

  const selectDataset = async (datasetId: number | null) => {
    setSelectedDatasetId(datasetId);
    closeRightPanel();
    // A new dataset means a fresh analysis context: drop the client-side cache
    // and any loaded session history from the previous dataset.
    resultsCacheRef.current.clear();
    setSessions([]);
    setSession({ id: null, status: "idle", cached: false });
    if (datasetId) {
      const ds = datasets.find((d) => d.id === datasetId) || null;
      setSelectedDataset(ds);
      showToast(`Selected Dataset: ${ds?.name}`);
    } else {
      setSelectedDataset(null);
    }
  };

  const createProject = async (name: string, description: string) => {
    try {
      const newProj = await apiFetch<Project>("/projects", {
        method: "POST",
        body: JSON.stringify({ name, description }),
      });
      await loadProjects();
      showToast(`Created project "${name}"`);
      return newProj;
    } catch (e) {
      throw e;
    }
  };

  const uploadDataset = async (file: File) => {
    if (!selectedProjectId) throw new Error("No project selected");
    const formData = new FormData();
    formData.append("file", file);
    
    try {
      const newDs = await apiFetch<Dataset>(`/projects/${selectedProjectId}/datasets`, {
        method: "POST",
        body: formData,
      });
      await loadProjects();
      await loadDatasets(selectedProjectId);
      // Select the new dataset automatically
      await selectDataset(newDs.id);
      showToast(`Uploaded dataset ${file.name}`);
      return newDs;
    } catch (e) {
      throw e;
    }
  };

  const deleteProject = async (projectId: number) => {
    try {
      await apiFetch(`/projects/${projectId}`, { method: "DELETE" });
      if (selectedProjectId === projectId) {
        setSelectedProjectId(null);
        setSelectedDatasetId(null);
        setSelectedDataset(null);
        setActiveTab("dashboard");
      }
      await loadProjects();
      showToast("Project deleted");
    } catch {
      // apiFetch already presents the failure to the user.
    }
  };

  const deleteDataset = async (datasetId: number) => {
    try {
      await apiFetch(`/datasets/${datasetId}`, { method: "DELETE" });
      if (selectedDatasetId === datasetId) {
        setSelectedDatasetId(null);
        setSelectedDataset(null);
      }
      if (selectedProjectId) {
        await loadDatasets(selectedProjectId);
      }
      showToast("Dataset deleted");
    } catch {
      // apiFetch already presents the failure to the user.
    }
  };

  const runAnalysis = useCallback(async (
    engineKey: string,
    target?: string,
    opts?: { refresh?: boolean }
  ) => {
    if (!selectedDatasetId) throw new Error("No dataset selected");

    const refresh = opts?.refresh === true;
    const cacheKey = `${selectedDatasetId}:${target || ""}:${engineKey}`;

    // Serve from the client-side cache within a visit unless a refresh is asked.
    const cachedResult = !refresh ? resultsCacheRef.current.get(cacheKey) : undefined;
    if (cachedResult !== undefined) {
      setSession((prev) => ({ ...prev, status: "completed", cached: true }));
      return cachedResult;
    }

    setSession((prev) => ({ ...prev, status: "running", cached: false }));

    const params = new URLSearchParams();
    if (target) params.set("target", target);
    if (refresh) params.set("refresh", "true");
    const query = params.toString() ? `?${params.toString()}` : "";

    try {
      const { data, headers } = await apiFetchWithHeaders<AnalysisResult>(
        `/datasets/${selectedDatasetId}/analysis/${engineKey}${query}`
      );
      const cached = headers.get("X-DetaBeta-Cached") === "true";
      const sessionIdHeader = headers.get("X-DetaBeta-Session-Id");
      const sessionId = sessionIdHeader ? Number(sessionIdHeader) : null;

      resultsCacheRef.current.set(cacheKey, data);
      setSession({ id: sessionId, status: "completed", cached });
      return data;
    } catch (e) {
      setSession((prev) => ({ ...prev, status: "failed", cached: false }));
      throw e;
    }
  }, [apiFetchWithHeaders, selectedDatasetId]);

  const applyTransform = async (
    datasetId: number,
    payload: { transform: string; columns: string[]; evidence?: Record<string, unknown>; title?: string }
  ): Promise<ApplyTransformResult> => {
    const result = await apiFetch<ApplyTransformResult>(`/datasets/${datasetId}/apply-transform`, {
      method: "POST",
      body: JSON.stringify({
        transform: payload.transform,
        columns: payload.columns,
        evidence: payload.evidence ?? {},
        title: payload.title ?? null,
      }),
    });
    // The new version is a fresh dataset: refresh the project's dataset list
    // and the project cards (dataset_count) so the UI reflects it immediately.
    if (selectedProjectId) {
      await loadDatasets(selectedProjectId);
      await loadProjects();
    }
    setSelectedDatasetId(result.dataset.id);
    setSelectedDataset(result.dataset);
    resultsCacheRef.current.clear();
    setSessions([]);
    setSession({ id: null, status: "idle", cached: false });
    closeRightPanel();
    return result;
  };

  const loadSessions = useCallback(async (target?: string) => {
    if (!selectedDatasetId) return;
    const query = target ? `?target=${encodeURIComponent(target)}` : "";
    try {
      const data = await apiFetch<SessionSummary[]>(`/datasets/${selectedDatasetId}/sessions${query}`);
      setSessions(data);
    } catch {
      setSessions([]);
    }
  }, [apiFetch, selectedDatasetId]);

  const rerunSession = async (target?: string) => {
    if (!selectedDatasetId) throw new Error("No dataset selected");
    const query = target ? `?target=${encodeURIComponent(target)}` : "";
    try {
      await apiFetch(`/datasets/${selectedDatasetId}/sessions/rerun${query}`, {
        method: "POST",
      });
      // A fresh session version starts empty: clear the client cache so the
      // next analysis calls recompute against the new session.
      resultsCacheRef.current.clear();
      setSession({ id: null, status: "idle", cached: false });
      await loadSessions(target);
      showToast("Started a new analysis session");
    } catch (error) {
      throw error;
    }
  };

  useEffect(() => {
    let cancelled = false;

    async function loadInitialProjects() {
      try {
        // Pre-Supabase builds used global keys. They can point at a project
        // owned by a different account, so never import them into user-scoped state.
        window.localStorage.removeItem("detabetaSelectedProjectId");
        window.localStorage.removeItem("detabetaSelectedDatasetId");
        window.localStorage.removeItem("detabetaActiveTab");

        const savedProjectId = parsePersistedId(window.localStorage.getItem(projectStorageKey));
        const savedDatasetId = parsePersistedId(window.localStorage.getItem(datasetStorageKey));
        const savedTab = (window.localStorage.getItem(tabStorageKey) as TabName | null) || "dashboard";
        const data = await apiFetch<Project[]>("/projects");
        if (cancelled) return;
        setProjects(data);

        let dsList: Dataset[] = [];
        if (savedProjectId && data.some((project) => project.id === savedProjectId)) {
          dsList = await apiFetch<Dataset[]>(`/projects/${savedProjectId}/datasets`);
        }

        if (cancelled) return;
        const reconciled = reconcileWorkspaceSelection({
          projects: data,
          datasets: dsList,
          savedProjectId,
          savedDatasetId,
          savedTab,
        });

        setDatasets(reconciled.projectId ? dsList : []);
        setSelectedProjectId(reconciled.projectId);
        setSelectedDatasetId(reconciled.datasetId);
        setSelectedDataset(
          reconciled.datasetId ? dsList.find((dataset) => dataset.id === reconciled.datasetId) || null : null,
        );
        setActiveTab(reconciled.tab);
        resultsCacheRef.current.clear();
        setSessions([]);
        setSession({ id: null, status: "idle", cached: false });
        closeRightPanel();
      } catch {
        if (cancelled) return;
        setProjects([]);
        setDatasets([]);
        setSelectedProjectId(null);
        setSelectedDatasetId(null);
        setSelectedDataset(null);
        setActiveTab("dashboard");
      }
    }

    void loadInitialProjects();
    return () => { cancelled = true; };
    // apiFetch changes with apiBase. The storage keys change with the signed-in user.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase, workspaceUserId]);

  return (
    <WorkspaceContext.Provider
      value={{
        apiBase,
        setApiBase,
        projects,
        datasets,
        selectedProjectId,
        selectedDatasetId,
        selectedDataset,
        activeTab,
        setActiveTab,
        rightPanel,
        openRightPanel,
        closeRightPanel,
        toast,
        showToast,
        session,
        setSession,
        sessions,
        loadSessions,
        rerunSession,
        loadProjects,
        loadDatasets,
        selectProject,
        selectDataset,
        createProject,
        uploadDataset,
        deleteProject,
        deleteDataset,
        runAnalysis,
        applyTransform,
        apiFetch,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
};

export const useWorkspace = () => {
  const context = useContext(WorkspaceContext);
  if (context === undefined) {
    throw new Error("useWorkspace must be used within a WorkspaceProvider");
  }
  return context;
};
