"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useWorkspace } from "@/context/WorkspaceContext";
import { MAX_UPLOAD_BYTES, validateCsvUpload } from "@/lib/upload-validation";
import {
  Upload,
  FileSpreadsheet,
  CheckCircle,
  ArrowRight,
  Loader2,
  History,
  RefreshCw,
  Zap,
} from "lucide-react";

type DatasetProfile = {
  n_rows?: number;
  n_cols?: number;
  n_duplicate_rows?: number;
  observations?: string[];
};

type Discovery = {
  strength: string;
  title: string;
  [key: string]: unknown;
};

type OverviewAnalysis = {
  profile: DatasetProfile;
  healthScore: number;
  discoveries: Discovery[];
};

export const OverviewView: React.FC = () => {
  const {
    selectedDatasetId,
    selectedDataset,
    datasets,
    uploadDataset,
    runAnalysis,
    openRightPanel,
    session,
    sessions,
    loadSessions,
    rerunSession,
  } = useWorkspace();

  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [rerunning, setRerunning] = useState(false);

  // Analysis states
  const [profile, setProfile] = useState<DatasetProfile | null>(null);
  const [discoveries, setDiscoveries] = useState<Discovery[]>([]);
  const [healthScore, setHealthScore] = useState<number | null>(null);

  const fetchOverviewAnalysis = useCallback(async (): Promise<OverviewAnalysis> => {
    const profileData = await runAnalysis("understand");
    const healthData = await runAnalysis("health");
    const investigationData = await runAnalysis("investigate");
    await loadSessions();
    return {
      profile: profileData as DatasetProfile,
      healthScore: (healthData as { score?: number }).score ?? 100,
      discoveries: (investigationData as { findings?: Discovery[] }).findings ?? [],
    };
  }, [loadSessions, runAnalysis]);

  // Load the reports for the active dataset and refresh when it changes.
  useEffect(() => {
    if (!selectedDatasetId) return;
    let cancelled = false;
    void fetchOverviewAnalysis()
      .then((analysis) => {
        if (cancelled) return;
        setProfile(analysis.profile);
        setHealthScore(analysis.healthScore);
        setDiscoveries(analysis.discoveries);
      })
      .catch(() => {
        if (!cancelled) {
          setProfile(null);
          setHealthScore(null);
          setDiscoveries([]);
        }
      });
    return () => { cancelled = true; };
  }, [fetchOverviewAnalysis, selectedDatasetId]);

  const loadingAnalysis = Boolean(selectedDatasetId && profile === null);

  const handleRerun = async () => {
    setRerunning(true);
    try {
      // Start a fresh session version, then recompute the overview engines.
      await rerunSession();
      const analysis = await fetchOverviewAnalysis();
      setProfile(analysis.profile);
      setHealthScore(analysis.healthScore);
      setDiscoveries(analysis.discoveries);
    } catch {
      // The workspace toast contains the backend failure message.
    } finally {
      setRerunning(false);
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragging(true);
    } else if (e.type === "dragleave") {
      setDragging(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const dropped = e.dataTransfer.files[0];
      const validationError = validateCsvUpload(dropped);
      if (!validationError) {
        setFile(dropped);
      } else {
        alert(validationError);
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const nextFile = e.target.files[0];
      const validationError = validateCsvUpload(nextFile);
      if (validationError) {
        alert(validationError);
        e.target.value = "";
        return;
      }
      setFile(nextFile);
    }
  };

  const handleUploadSubmit = async () => {
    if (!file) return;
    setLoading(true);
    try {
      await uploadDataset(file);
      setFile(null);
    } catch {
      // The workspace toast contains the upload failure message.
    } finally {
      setLoading(false);
    }
  };

  // Render Upload Zone if project has no dataset
  if (!selectedDatasetId && datasets.length === 0) {
    const formattedSize = file ? (file.size / (1024 * 1024)).toFixed(2) + " MB" : "";
    return (
      <div className="flex-1 flex flex-col justify-center items-center py-10 max-w-2xl mx-auto space-y-6">
        <div className="text-center space-y-1">
          <h2 className="text-xl font-bold text-zinc-100">Upload dataset to begin</h2>
          <p className="text-xs text-zinc-500 max-w-sm">
            Import a CSV format dataset. This starts the automated diagnostics, understanding, and pattern engines.
          </p>
        </div>

        {/* Drag Drop Box */}
        <div
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
          className={`w-full p-10 bg-zinc-900/30 hover:bg-zinc-900/50 border border-dashed rounded-lg transition duration-300 flex flex-col justify-center items-center gap-4 cursor-pointer min-h-[220px] ${
            dragging ? "border-emerald-500 bg-emerald-950/10" : "border-zinc-800"
          }`}
        >
          <input
            type="file"
            id="file-upload"
            className="hidden"
            accept=".csv"
            onChange={handleFileChange}
          />
          <label htmlFor="file-upload" className="flex flex-col items-center gap-3 cursor-pointer">
            <div className="w-10 h-10 rounded-full bg-zinc-900 border border-zinc-850 flex items-center justify-center text-zinc-400 group-hover:scale-105 transition duration-300">
              <Upload className="w-4.5 h-4.5" />
            </div>
            <div className="text-center">
              <span className="text-xs font-semibold text-zinc-300">
                {file ? file.name : "Drop dataset here, or Browse Files"}
              </span>
              <span className="text-[10px] text-zinc-500 block mt-1">CSV files up to {Math.round(MAX_UPLOAD_BYTES / (1024 * 1024))} MB</span>
            </div>
          </label>
        </div>

        {/* Selected file confirmation */}
        {file && (
          <div className="w-full p-4 bg-zinc-900 border border-zinc-800 rounded-lg flex justify-between items-center text-xs">
            <div className="flex items-center gap-2">
              <FileSpreadsheet className="w-4 h-4 text-emerald-500" />
              <div>
                <span className="font-semibold text-zinc-200 block">{file.name}</span>
                <span className="text-[10px] text-zinc-500 font-mono">{formattedSize} · CSV format verified</span>
              </div>
            </div>
            <button
              onClick={handleUploadSubmit}
              disabled={loading}
              className="flex items-center gap-1.5 px-4 py-2 bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-zinc-950 rounded font-semibold transition cursor-pointer"
            >
              {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>Create Project & Inspect Dataset</span>
            </button>
          </div>
        )}
      </div>
    );
  }

  // Fallback if loading analysis results
  if (loadingAnalysis) {
    return (
      <div className="flex-1 flex flex-col justify-center items-center min-h-[300px]">
        <Loader2 className="w-8 h-8 text-emerald-400 animate-spin" />
        <span className="text-xs text-zinc-500 mt-3 font-mono">Running DetaBeta core understanding engine...</span>
      </div>
    );
  }

  const datasetName = selectedDataset?.name || "No name";
  const rowCount = profile?.n_rows || selectedDataset?.n_rows || 0;
  const colCount = profile?.n_cols || selectedDataset?.n_columns || 0;
  const duplicateCount = profile?.n_duplicate_rows || 0;

  // Stepper statuses
  const stepper = [
    { title: "Dataset Understanding", key: "understand", isCompleted: !!profile },
    { title: "Data Diagnostics", key: "diagnostics", isCompleted: healthScore !== null },
    { title: "Statistical Analysis", key: "statistics", isCompleted: discoveries.length > 0 },
    { title: "Pattern Discovery", key: "investigate", isCompleted: discoveries.length > 0 },
    { title: "Feature Recommendations", key: "feature-lab", isCompleted: !!profile },
  ];

  return (
    <div className="space-y-8 py-4">
      {/* Top Concise Summary Cards */}
      <div className="border-b border-zinc-850 pb-5">
        <div className="text-[10px] uppercase font-bold tracking-wider text-emerald-400 mb-1">
          Experiment Container
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-zinc-100 uppercase font-mono break-all">
          {datasetName.replace(".csv", "")} DATASET
        </h1>
        
        {/* Core Stats Metric Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
          <div className="p-4 bg-zinc-900 border border-zinc-800 rounded">
            <span className="text-[10px] text-zinc-500 font-medium">Rows</span>
            <div className="text-xl font-bold text-zinc-100 mt-1 font-mono">{rowCount.toLocaleString()}</div>
          </div>
          <div className="p-4 bg-zinc-900 border border-zinc-800 rounded">
            <span className="text-[10px] text-zinc-500 font-medium">Columns</span>
            <div className="text-xl font-bold text-zinc-100 mt-1 font-mono">{colCount}</div>
          </div>
          <div className="p-4 bg-zinc-900 border border-zinc-800 rounded">
            <span className="text-[10px] text-zinc-500 font-medium">Duplicate Rows</span>
            <div className="text-xl font-bold text-zinc-100 mt-1 font-mono">{duplicateCount}</div>
          </div>
          <div className="p-4 bg-zinc-900 border border-zinc-800 rounded">
            <span className="text-[10px] text-zinc-500 font-medium">Diagnostics Health</span>
            <div className="text-xl font-bold text-emerald-400 mt-1 font-mono">
              {healthScore !== null ? `${healthScore}/100` : "..."}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: What DetaBeta Understands */}
        <div className="lg:col-span-2 space-y-6">
          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">
              What DetaBeta Understands
            </h2>
            <div className="p-5 bg-zinc-900/50 border border-zinc-800/80 rounded-lg space-y-4">
              <p className="text-xs text-zinc-300 leading-relaxed font-serif">
                {profile?.observations?.[0] || "DetaBeta has completed parsing and classifies the columns of this dataset. Use explorer to check metadata details."}
              </p>
              
              {profile?.observations && profile.observations.length > 1 && (
                <div className="space-y-1.5 pt-3 border-t border-zinc-850">
                  {profile.observations.slice(1, 4).map((obs: string, idx: number) => (
                    <div key={idx} className="flex gap-2 items-start text-xs text-zinc-400 leading-relaxed">
                      <span className="text-emerald-500 font-bold">•</span>
                      <span>{obs}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Stepper Analysis checklist */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">
              Analysis pipeline progress
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {stepper.map((step, idx) => (
                <div
                  key={step.key}
                  className="flex items-center justify-between p-3.5 bg-zinc-900 border border-zinc-800 rounded-lg text-xs"
                >
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-zinc-950 border border-zinc-800 text-[10px] text-zinc-500 flex items-center justify-center font-bold font-mono">
                      0{idx + 1}
                    </span>
                    <span className="text-zinc-300 font-medium">{step.title}</span>
                  </div>
                  {step.isCompleted ? (
                    <CheckCircle className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <Loader2 className="w-4 h-4 text-zinc-600 animate-spin" />
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Stepper Launcher Quick actions */}
        <div className="space-y-6">
          {/* Start Here - top discoveries */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">
              Start Here (Key Discoveries)
            </h3>
            <div className="space-y-3">
              {discoveries && discoveries.length > 0 ? (
                discoveries.slice(0, 3).map((f, idx) => (
                  <div
                    key={idx}
                    onClick={() => openRightPanel("discovery", f)}
                    className="group bg-[#18181b]/40 hover:bg-[#18181b]/80 border border-zinc-850 hover:border-zinc-700/80 rounded-lg p-4 cursor-pointer transition duration-300 flex flex-col justify-between min-h-[90px]"
                  >
                    <div>
                      <div className="flex justify-between items-center gap-2 text-[8px] uppercase tracking-wider text-emerald-400 font-bold mb-1">
                        <span>Discovery #0{idx + 1}</span>
                        <span className="font-mono">{f.strength} strength</span>
                      </div>
                      <h4 className="text-xs font-semibold text-zinc-200 group-hover:text-emerald-400 transition leading-snug line-clamp-2">
                        {f.title}
                      </h4>
                    </div>
                    <div className="flex items-center justify-end text-[9px] text-zinc-500 group-hover:text-emerald-400 font-mono mt-3 gap-0.5">
                      <span>Investigate</span>
                      <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-xs text-zinc-500 text-center py-8 bg-zinc-900/30 border border-dashed border-zinc-800 rounded-lg">
                  No discoveries calculated yet.
                </div>
              )}
            </div>
          </div>

          {/* Session history */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-1.5">
                <History className="w-3.5 h-3.5 text-zinc-500" />
                Session History
              </h3>
              <button
                onClick={handleRerun}
                disabled={rerunning}
                className="flex items-center gap-1.5 px-2.5 py-1.5 text-[10px] font-semibold bg-zinc-900 hover:bg-zinc-800 disabled:opacity-50 border border-zinc-800 text-zinc-300 rounded transition cursor-pointer"
              >
                <RefreshCw className={`w-3 h-3 ${rerunning ? "animate-spin" : ""}`} />
                <span>Re-run analysis</span>
              </button>
            </div>

            {session.cached && (
              <div className="flex items-center gap-1.5 text-[10px] text-emerald-400 font-mono">
                <Zap className="w-3 h-3" />
                <span>Served from cache · instant</span>
              </div>
            )}

            <div className="space-y-2">
              {sessions.length > 0 ? (
                sessions.map((s, idx) => {
                  const isActive = s.id === session.id;
                  const created = new Date(s.created_at).toLocaleString();
                  return (
                    <div
                      key={s.id}
                      className={`p-3 rounded-lg border text-xs transition ${
                        isActive
                          ? "bg-emerald-950/20 border-emerald-800/60"
                          : "bg-zinc-900/40 border-zinc-850"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-semibold text-zinc-200">
                          {idx === 0 ? "Latest" : `v${sessions.length - idx}`}
                          {s.target ? ` · target: ${s.target}` : " · base"}
                        </span>
                        {isActive && (
                          <span className="text-[9px] uppercase tracking-wider text-emerald-400 font-bold">
                            Active
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] text-zinc-500 font-mono mt-1">{created}</div>
                      {s.completed_engine_keys.length > 0 && (
                        <div className="text-[10px] text-zinc-500 mt-1.5">
                          {s.completed_engine_keys.length} engine
                          {s.completed_engine_keys.length === 1 ? "" : "s"} cached
                        </div>
                      )}
                    </div>
                  );
                })
              ) : (
                <div className="text-xs text-zinc-500 text-center py-6 bg-zinc-900/30 border border-dashed border-zinc-800 rounded-lg">
                  No sessions yet.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
