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
  id: string | null;
  status: "idle" | "running" | "completed" | "failed";
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
  loadProjects: () => Promise<void>;
  loadDatasets: (projectId: number) => Promise<void>;
  selectProject: (projectId: number | null) => Promise<void>;
  selectDataset: (datasetId: number | null) => Promise<void>;
  createProject: (name: string, description: string) => Promise<Project>;
  uploadDataset: (file: File) => Promise<Dataset>;
  deleteProject: (projectId: number) => Promise<void>;
  deleteDataset: (datasetId: number) => Promise<void>;
  runAnalysis: (engineKey: string, target?: string) => Promise<any>;
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
  });

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

  const runAnalysis = async (engineKey: string, target?: string) => {
    if (!selectedDatasetId) throw new Error("No dataset selected");
    
    setSession({ id: `session-${Date.now()}`, status: "running" });
    const query = target ? `?target=${encodeURIComponent(target)}` : "";
    
    try {
      const res = await apiFetch(`/datasets/${selectedDatasetId}/analysis/${engineKey}${query}`);
      setSession((prev) => ({ ...prev, status: "completed" }));
      return res;
    } catch (e) {
      setSession((prev) => ({ ...prev, status: "failed" }));
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
