"use client";

import React, { createContext, useContext, useState, useEffect } from "react";

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

export interface RightPanelState {
  isOpen: boolean;
  type: "column" | "discovery" | "transform" | "SHAP" | null;
  data: any;
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
  openRightPanel: (type: RightPanelState["type"], data: any) => void;
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
  ) => Promise<any>;
}

const WorkspaceContext = createContext<WorkspaceContextProps | undefined>(undefined);

export const WorkspaceProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [apiBase, setApiBaseState] = useState<string>("/api");
  const [projects, setProjects] = useState<Project[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [selectedDatasetId, setSelectedDatasetId] = useState<number | null>(null);
  const [selectedDataset, setSelectedDataset] = useState<Dataset | null>(null);
  const [activeTab, setActiveTab] = useState<TabName>("landing");
  
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
  const resultsCacheRef = React.useRef<Map<string, any>>(new Map());

  // Initialize API Base and load initial projects
  useEffect(() => {
    if (typeof window !== "undefined") {
      const saved = window.localStorage.getItem("detabetaApiBase");
      if (saved && saved !== "http://127.0.0.1:8000/api") {
        setApiBaseState(saved);
      } else {
        setApiBaseState("/api");
      }
    }
  }, []);

  useEffect(() => {
    if (apiBase) {
      loadProjects().catch((err) => {
        console.error("Failed to load initial projects:", err);
      });
    }
  }, [apiBase]);

  const setApiBase = (url: string) => {
    setApiBaseState(url);
    if (typeof window !== "undefined") {
      window.localStorage.setItem("detabetaApiBase", url);
    }
  };

  const showToast = (message: string, type: "success" | "error" = "success") => {
    setToast({ message, type });
    setTimeout(() => {
      setToast({ message: "", type: null });
    }, 3000);
  };

  const openRightPanel = (type: RightPanelState["type"], data: any) => {
    setRightPanel({ isOpen: true, type, data });
  };

  const closeRightPanel = () => {
    setRightPanel((prev) => ({ ...prev, isOpen: false }));
  };

  // Helper fetch function
  const apiFetch = async (path: string, options: RequestInit = {}) => {
    const headers = options.body instanceof FormData 
      ? {} 
      : { "Content-Type": "application/json", ...(options.headers || {}) };

    const url = `${apiBase.replace(/\/$/, "")}${path}`;
    
    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      const contentType = response.headers.get("content-type") || "";
      let data;
      if (contentType.includes("application/json")) {
        data = await response.json();
      } else {
        data = await response.text();
      }

      if (!response.ok) {
        const errorDetail = data?.detail || data?.message || response.statusText || "Request failed";
        throw new Error(typeof errorDetail === "string" ? errorDetail : JSON.stringify(errorDetail));
      }

      return data;
    } catch (error: any) {
      showToast(error.message || "Network error occurred", "error");
      throw error;
    }
  };

  // Like apiFetch, but also returns response headers so callers can read the
  // cache metadata (X-DetaBeta-Cached / X-DetaBeta-Session-Id) the analysis
  // endpoints attach.
  const apiFetchWithHeaders = async (path: string, options: RequestInit = {}) => {
    const headers = options.body instanceof FormData
      ? {}
      : { "Content-Type": "application/json", ...(options.headers || {}) };
    const url = `${apiBase.replace(/\/$/, "")}${path}`;
    try {
      const response = await fetch(url, { ...options, headers });
      const contentType = response.headers.get("content-type") || "";
      const data = contentType.includes("application/json")
        ? await response.json()
        : await response.text();
      if (!response.ok) {
        const errorDetail = data?.detail || data?.message || response.statusText || "Request failed";
        throw new Error(typeof errorDetail === "string" ? errorDetail : JSON.stringify(errorDetail));
      }
      return { data, headers: response.headers };
    } catch (error: any) {
      showToast(error.message || "Network error occurred", "error");
      throw error;
    }
  };

  const loadProjects = async () => {
    try {
      const data = await apiFetch("/projects");
      setProjects(data);
    } catch (e) {
      console.error(e);
    }
  };

  const loadDatasets = async (projectId: number) => {
    try {
      const data = await apiFetch(`/projects/${projectId}/datasets`);
      setDatasets(data);
    } catch (e) {
      console.error(e);
    }
  };

  const selectProject = async (projectId: number | null) => {
    setSelectedProjectId(projectId);
    setSelectedDatasetId(null);
    setSelectedDataset(null);
    setDatasets([]);
    resultsCacheRef.current.clear();
    setSessions([]);
    setSession({ id: null, status: "idle", cached: false });
    closeRightPanel();
    if (projectId) {
      await loadDatasets(projectId);
      showToast(`Switched to Project #${projectId}`);
      setActiveTab("overview");
    } else {
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
      const newProj = await apiFetch("/projects", {
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
      const newDs = await apiFetch(`/projects/${selectedProjectId}/datasets`, {
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
    } catch (e) {
      console.error(e);
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
    } catch (e) {
      console.error(e);
    }
  };

  const runAnalysis = async (
    engineKey: string,
    target?: string,
    opts?: { refresh?: boolean }
  ) => {
    if (!selectedDatasetId) throw new Error("No dataset selected");

    const refresh = opts?.refresh === true;
    const cacheKey = `${selectedDatasetId}:${target || ""}:${engineKey}`;

    // Serve from the client-side cache within a visit unless a refresh is asked.
    if (!refresh && resultsCacheRef.current.has(cacheKey)) {
      setSession((prev) => ({ ...prev, status: "completed", cached: true }));
      return resultsCacheRef.current.get(cacheKey);
    }

    setSession((prev) => ({ ...prev, status: "running", cached: false }));

    const params = new URLSearchParams();
    if (target) params.set("target", target);
    if (refresh) params.set("refresh", "true");
    const query = params.toString() ? `?${params.toString()}` : "";

    try {
      const { data, headers } = await apiFetchWithHeaders(
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
  };

  const loadSessions = async (target?: string) => {
    if (!selectedDatasetId) return;
    const query = target ? `?target=${encodeURIComponent(target)}` : "";
    try {
      const data = await apiFetch(`/datasets/${selectedDatasetId}/sessions${query}`);
      setSessions(data);
    } catch (e) {
      console.error(e);
    }
  };

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
    } catch (e) {
      console.error(e);
      throw e;
    }
  };

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
