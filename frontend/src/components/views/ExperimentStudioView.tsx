"use client";

import React, { useState, useEffect } from "react";
import { useWorkspace } from "@/context/WorkspaceContext";
import { Loader2, Sparkles, Cpu, Award, ListFilter, AlertTriangle } from "lucide-react";

export const ExperimentStudioView: React.FC = () => {
  const { selectedDatasetId, runAnalysis, apiBase } = useWorkspace();
  
  const [columns, setColumns] = useState<string[]>([]);
  const [target, setTarget] = useState("");
  const [loadingMetadata, setLoadingMetadata] = useState(false);
  const [loadingRecommend, setLoadingRecommend] = useState(false);
  const [loadingExperiment, setLoadingExperiment] = useState(false);
  
  const [recommendReport, setRecommendReport] = useState<any>(null);
  const [experimentReport, setExperimentReport] = useState<any>(null);

  // Load dataset preview to get column list
  useEffect(() => {
    if (selectedDatasetId) {
      loadColumns();
    }
  }, [selectedDatasetId]);

  const loadColumns = async () => {
    setLoadingMetadata(true);
    try {
      const res = await fetch(`${apiBase.replace(/\/$/, "")}/datasets/${selectedDatasetId}/preview`);
      if (res.ok) {
        const preview = await res.json();
        setColumns(preview.columns || []);
        // Set default target if columns contain survived or churn
        const defaultTgt = (preview.columns || []).find((c: string) => 
          c.toLowerCase() === "survived" || c.toLowerCase() === "churn"
        );
        if (defaultTgt) {
          setTarget(defaultTgt);
        }
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingMetadata(false);
    }
  };

  // Fetch algorithm recommendations when target changes
  useEffect(() => {
    if (selectedDatasetId && target) {
      loadRecommendations();
    } else {
      setRecommendReport(null);
      setExperimentReport(null);
    }
  }, [selectedDatasetId, target]);

  const loadRecommendations = async () => {
    setLoadingRecommend(true);
    try {
      const data = await runAnalysis("recommend", target);
      setRecommendReport(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingRecommend(false);
    }
  };

  const handleTrainModels = async () => {
    if (!target) return;
    setLoadingExperiment(true);
    try {
      const data = await runAnalysis("experiment", target);
      setExperimentReport(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingExperiment(false);
    }
  };

  if (loadingMetadata) {
    return (
      <div className="flex-1 flex flex-col justify-center items-center min-h-[300px]">
        <Loader2 className="w-8 h-8 text-emerald-400 animate-spin" />
        <span className="text-xs text-zinc-500 mt-3 font-mono">Loading dataset variables list...</span>
      </div>
    );
  }

  const results: any[] = experimentReport?.results || [];

  return (
    <div className="space-y-6 py-4">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-zinc-100">Experiment Studio</h1>
        <p className="text-xs text-zinc-500 mt-1">
          Machine Learning laboratory. Select a target column, inspect baseline suggestions, and run training pipelines.
        </p>
      </div>

      {/* Target Selector & Detection Card */}
      <div className="p-5 bg-zinc-900/30 border border-zinc-800 rounded-xl space-y-4">
        <div className="flex flex-col sm:flex-row gap-4 sm:items-center justify-between">
          <div className="space-y-1">
            <label className="text-[10px] font-bold uppercase tracking-wider text-zinc-500 block">
              Predictive Target Variable
            </label>
            <select
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              className="bg-zinc-950 border border-zinc-850 rounded px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer w-60"
            >
              <option value="">Select Target Column</option>
              {columns.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          {recommendReport && (
            <div className="text-right">
              <span className="text-[10px] text-zinc-500 font-medium block">Problem Family Detected</span>
              <span className="text-xs font-semibold text-emerald-400 uppercase font-mono mt-1 block">
                {recommendReport.problem_type?.replace("_", " ")}
              </span>
            </div>
          )}
        </div>

        {recommendReport?.summary && (
          <p className="text-xs text-zinc-400 leading-relaxed border-t border-zinc-850 pt-3">
            {recommendReport.summary}
          </p>
        )}
      </div>

      {/* Baseline Recommendations (Before Training) */}
      {recommendReport && !experimentReport && (
        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">
            Recommended Baselines
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {recommendReport.algorithms?.map((algo: any, idx: number) => (
              <div
                key={idx}
                className="bg-zinc-900/30 border border-zinc-800 rounded-lg p-5 flex flex-col justify-between"
              >
                <div>
                  <div className="flex justify-between items-center gap-2 mb-2">
                    <span className="text-xs font-semibold text-zinc-200">
                      {algo.name}
                    </span>
                    <span className={`text-[8px] font-bold uppercase tracking-wider font-mono px-2 py-0.5 rounded border ${
                      algo.is_baseline 
                        ? "bg-emerald-950 text-emerald-400 border-emerald-900/30" 
                        : "bg-zinc-800 text-zinc-400 border-zinc-700"
                    }`}>
                      {algo.is_baseline ? "BASELINE" : algo.complexity}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-400 mt-2 leading-relaxed">
                    <strong>Pros:</strong> {algo.pros?.join(", ") || "Fast training baseline."}
                  </p>
                  <p className="text-xs text-zinc-450 mt-1 leading-relaxed">
                    <strong>Cons:</strong> {algo.cons?.join(", ") || "Simplistic coefficients."}
                  </p>
                </div>
                <div className="text-[9px] text-zinc-650 font-mono mt-4">
                  Implementation: <code className="text-zinc-550">{algo.sklearn_path}</code>
                </div>
              </div>
            ))}
          </div>

          <div className="flex justify-center pt-4">
            <button
              onClick={handleTrainModels}
              disabled={loadingRecommend || loadingExperiment}
              className="flex items-center gap-1.5 px-6 py-2.5 bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-zinc-950 text-xs font-semibold shadow rounded transition cursor-pointer"
            >
              {loadingExperiment && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <Cpu className="w-4 h-4" />
              <span>{loadingExperiment ? "Training Pipelines..." : "Add to Experiment & Train"}</span>
            </button>
          </div>
        </div>
      )}

      {/* Leaderboard Comparison (After Training) */}
      {experimentReport && (
        <div className="space-y-6">
          <div className="flex justify-between items-center gap-4">
            <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">
              Experiments Leaderboard
            </h2>
            <button
              onClick={handleTrainModels}
              disabled={loadingExperiment}
              className="flex items-center gap-1.5 px-3 py-1.5 border border-zinc-800 hover:bg-zinc-900 text-zinc-300 text-[10px] font-semibold transition cursor-pointer"
            >
              {loadingExperiment && <Loader2 className="w-3 h-3 animate-spin" />}
              <span>Retrain Models</span>
            </button>
          </div>

          {/* Leaderboard Table */}
          <div className="border border-zinc-800 rounded-lg overflow-hidden bg-zinc-900/10">
            <table className="scientific-table w-full border-collapse">
              <thead>
                <tr className="bg-[#0f0f11] font-mono">
                  <th>Model</th>
                  <th>Primary ({experimentReport.primary_metric?.toUpperCase()})</th>
                  <th>Train Duration</th>
                  <th>F1 Score</th>
                  <th>ROC-AUC</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r: any, idx: number) => {
                  const isBest = r.name === experimentReport.best_model;
                  const f1 = r.metrics?.f1?.mean || r.metrics?.f1 || 0.0;
                  const roc = r.metrics?.roc_auc?.mean || r.metrics?.roc_auc || 0.0;
                  
                  return (
                    <tr key={idx} className={`border-b border-zinc-850 ${isBest ? "bg-emerald-950/5" : ""}`}>
                      <td className="text-zinc-200 font-semibold flex items-center gap-2">
                        {isBest && <Award className="w-4 h-4 text-emerald-400" />}
                        <span>{r.name}</span>
                        {r.is_baseline && (
                          <span className="text-[8px] bg-zinc-800 text-zinc-400 px-1 py-0.5 rounded font-mono">
                            baseline
                          </span>
                        )}
                      </td>
                      <td className="font-mono text-zinc-100 font-bold">
                        {r.primary_score ? r.primary_score.toFixed(4) : "..."}
                      </td>
                      <td className="font-mono text-zinc-450">{r.train_seconds?.toFixed(2)}s</td>
                      <td className="font-mono text-zinc-300">{f1 ? f1.toFixed(3) : "-"}</td>
                      <td className="font-mono text-zinc-300">{roc ? roc.toFixed(3) : "-"}</td>
                      <td>
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-400 font-mono">
                          Ready
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Winner Explanation card */}
          <div className="p-5 bg-emerald-950/15 border border-emerald-900/40 rounded-xl space-y-3">
            <div className="flex items-center gap-2 text-emerald-400">
              <Award className="w-5 h-5" />
              <h3 className="text-sm font-semibold uppercase tracking-wider">
                Winning Model: {experimentReport.best_model}
              </h3>
            </div>
            <div className="text-xs text-zinc-400 leading-relaxed space-y-2">
              <p>
                <strong>Why this model ranks first:</strong> {experimentReport.best_reasoning?.[0] || "Outperforms simple linear baselines and handles nonlinear relationship structures inside validation folds."}
              </p>
              {experimentReport.baseline_comparison && (
                <p className="text-[11px] font-mono text-zinc-550 border-t border-zinc-850 pt-2">
                  {experimentReport.baseline_comparison}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Placeholder state */}
      {!target && (
        <div className="flex flex-col justify-center items-center py-20 border border-dashed border-zinc-800 rounded-lg space-y-2">
          <ListFilter className="w-8 h-8 text-zinc-650" />
          <span className="text-xs text-zinc-400 font-semibold">Choose Target Variable</span>
          <span className="text-[10px] text-zinc-600">Select a predictive column to detect regression or classification baselines.</span>
        </div>
      )}
    </div>
  );
};
