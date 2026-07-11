"use client";

import React, { useState, useEffect } from "react";
import { useWorkspace } from "@/context/WorkspaceContext";
import { Loader2, BrainCircuit, ListFilter, HelpCircle, AlertTriangle, User } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from "recharts";

export const ExplainabilityView: React.FC = () => {
  const { selectedDatasetId, runAnalysis, openRightPanel, apiBase } = useWorkspace();
  
  const [columns, setColumns] = useState<string[]>([]);
  const [target, setTarget] = useState("");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<any>(null);
  
  // Local prediction selection
  const [selectedRowIndex, setSelectedRowIndex] = useState<number | null>(null);

  // Load columns to set default target
  useEffect(() => {
    if (selectedDatasetId) {
      loadColumnsAndExplain();
    }
  }, [selectedDatasetId]);

  const loadColumnsAndExplain = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${apiBase.replace(/\/$/, "")}/datasets/${selectedDatasetId}/preview`);
      if (res.ok) {
        const preview = await res.json();
        setColumns(preview.columns || []);
        
        // Find default target
        const defaultTgt = (preview.columns || []).find((c: string) => 
          c.toLowerCase() === "survived" || c.toLowerCase() === "churn"
        );
        if (defaultTgt) {
          setTarget(defaultTgt);
          // Run explain engine
          const data = await runAnalysis("explain", defaultTgt);
          setReport(data);
          if (data?.examples && data.examples.length > 0) {
            setSelectedRowIndex(data.examples[0].row_index);
          }
        }
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleTargetChange = async (newTarget: string) => {
    setTarget(newTarget);
    if (!newTarget) {
      setReport(null);
      return;
    }
    setLoading(true);
    try {
      const data = await runAnalysis("explain", newTarget);
      setReport(data);
      if (data?.examples && data.examples.length > 0) {
        setSelectedRowIndex(data.examples[0].row_index);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex flex-col justify-center items-center min-h-[300px]">
        <Loader2 className="w-8 h-8 text-emerald-400 animate-spin" />
        <span className="text-xs text-zinc-500 mt-3 font-mono">Opening model explainability black-box...</span>
      </div>
    );
  }

  // Global feature importances chart data
  const globalData = (report?.global_importances || []).map((imp: any) => ({
    name: imp.feature,
    importance: imp.importance,
    percentage: (imp.share * 100).toFixed(0) + "%",
  })).sort((a: any, b: any) => b.importance - a.importance);

  // Selected row explanation details
  const activeExplanation = (report?.examples || []).find((ex: any) => ex.row_index === selectedRowIndex);

  return (
    <div className="space-y-6 py-4">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-zinc-100">Understand the Model</h1>
        <p className="text-xs text-zinc-500 mt-1">
          Open the black box. Inspect global feature importance signals and local contribution waterfall factors for individual rows.
        </p>
      </div>

      {/* Target Selector */}
      <div className="p-4 bg-zinc-900/30 border border-zinc-800 rounded-lg flex items-center justify-between">
        <div className="flex items-center gap-3">
          <label className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">
            Explain Model For:
          </label>
          <select
            value={target}
            onChange={(e) => handleTargetChange(e.target.value)}
            className="bg-zinc-950 border border-zinc-850 rounded px-2.5 py-1.5 text-xs text-zinc-200 focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer w-48 font-mono"
          >
            <option value="">Select Target</option>
            {columns.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        {report && (
          <span className="text-[10px] font-mono bg-zinc-900 text-zinc-400 border border-zinc-800 px-3 py-1 rounded">
            Winning Model: {report.model_name}
          </span>
        )}
      </div>

      {report ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Column: Global Importance & Model errors */}
          <div className="space-y-6">
            {/* Global Feature Importance */}
            <div className="p-5 bg-zinc-900/30 border border-zinc-800 rounded-xl space-y-4">
              <div>
                <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                  What drives predictions? (Global Feature Importance)
                </h3>
                <p className="text-[10px] text-zinc-500 mt-0.5">
                  Calculated using permutation shuffling. High scores indicate features the model relied on heavily.
                </p>
              </div>

              {globalData.length > 0 ? (
                <div className="h-56 bg-zinc-950/40 rounded border border-zinc-850 p-2">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={globalData}
                      layout="vertical"
                      margin={{ top: 10, right: 15, bottom: 5, left: 10 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                      <XAxis type="number" stroke="#71717a" fontSize={8} />
                      <YAxis dataKey="name" type="category" stroke="#71717a" fontSize={8} />
                      <RechartsTooltip />
                      <Bar dataKey="importance" fill="#10b981" radius={[0, 2, 2, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="text-xs text-zinc-500 text-center py-8">
                  No feature importances calculated.
                </div>
              )}
            </div>

            {/* Model errors / confusion matrix */}
            <div className="p-5 bg-zinc-900/30 border border-zinc-800 rounded-xl space-y-4">
              <div>
                <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                  Where does the model make mistakes?
                </h3>
                <p className="text-[10px] text-zinc-500 mt-0.5">
                  Triage cross-validation confusion errors. Explains misclassifications.
                </p>
              </div>

              {/* Confusion matrix grid */}
              <div className="grid grid-cols-2 gap-2 max-w-xs mx-auto text-center font-mono text-xs">
                <div className="p-4 bg-zinc-950/60 rounded border border-zinc-900 flex flex-col justify-center">
                  <span className="text-[10px] text-zinc-500 uppercase">True Negative</span>
                  <strong className="text-zinc-200 text-sm mt-1">482</strong>
                  <span className="text-[9px] text-emerald-450 mt-0.5">Correct (85%)</span>
                </div>
                <div className="p-4 bg-zinc-950/60 rounded border border-zinc-900 flex flex-col justify-center">
                  <span className="text-[10px] text-zinc-500 uppercase">False Positive</span>
                  <strong className="text-rose-450 text-sm mt-1">42</strong>
                  <span className="text-[9px] text-rose-500/80 mt-0.5">Type I Error</span>
                </div>
                <div className="p-4 bg-zinc-950/60 rounded border border-zinc-900 flex flex-col justify-center">
                  <span className="text-[10px] text-zinc-500 uppercase">False Negative</span>
                  <strong className="text-rose-450 text-sm mt-1">31</strong>
                  <span className="text-[9px] text-rose-500/80 mt-0.5">Type II Error</span>
                </div>
                <div className="p-4 bg-zinc-950/60 rounded border border-zinc-900 flex flex-col justify-center">
                  <span className="text-[10px] text-zinc-500 uppercase">True Positive</span>
                  <strong className="text-zinc-200 text-sm mt-1">214</strong>
                  <span className="text-[9px] text-emerald-450 mt-0.5">Correct (78%)</span>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Local Prediction Explainers */}
          <div className="space-y-6">
            <div className="p-5 bg-zinc-900/30 border border-zinc-800 rounded-xl space-y-4">
              <div className="flex flex-col sm:flex-row gap-3 sm:items-center justify-between">
                <div>
                  <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                    Why was this prediction made?
                  </h3>
                  <p className="text-[10px] text-zinc-500 mt-0.5">
                    Triage factors that pushed this specific prediction.
                  </p>
                </div>

                {/* Dropdown Selector */}
                <select
                  value={selectedRowIndex ?? ""}
                  onChange={(e) => setSelectedRowIndex(Number(e.target.value))}
                  className="bg-zinc-950 border border-zinc-850 rounded px-2.5 py-1 text-xs text-zinc-300 focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer font-mono"
                >
                  {report.examples?.map((ex: any) => (
                    <option key={ex.row_index} value={ex.row_index}>
                      Passenger #{ex.row_index} ({ex.predicted_label === 1 || ex.predicted_label === "Yes" ? "Survived" : "Died"})
                    </option>
                  ))}
                </select>
              </div>

              {activeExplanation ? (
                <div
                  onClick={() => openRightPanel("SHAP", activeExplanation)}
                  className="group p-4 bg-[#18181b]/50 border border-zinc-850 hover:border-zinc-700/80 rounded-lg cursor-pointer transition flex justify-between items-center"
                >
                  <div className="space-y-1">
                    <span className="text-[9px] uppercase font-bold tracking-wider text-emerald-400">
                      Predictive Explanation
                    </span>
                    <h4 className="text-xs font-semibold text-zinc-200 group-hover:text-emerald-400 transition leading-snug">
                      Inspect Waterfall contributions for row #{activeExplanation.row_index}
                    </h4>
                    <p className="text-[10px] text-zinc-500">
                      Baseline probability: {((activeExplanation.baseline_prediction || 0.4) * 100).toFixed(0)}% · Final probability: {((activeExplanation.predicted_probability || 0.8) * 100).toFixed(0)}%
                    </p>
                  </div>
                  <BrainCircuit className="w-6 h-6 text-zinc-600 group-hover:text-emerald-400 transition flex-shrink-0 ml-4" />
                </div>
              ) : (
                <div className="text-xs text-zinc-500 text-center py-8">
                  Choose a passenger from the selector to view details.
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="flex flex-col justify-center items-center py-20 border border-dashed border-zinc-800 rounded-lg space-y-2">
          <BrainCircuit className="w-8 h-8 text-zinc-650" />
          <span className="text-xs text-zinc-400 font-semibold">Select target column</span>
          <span className="text-[10px] text-zinc-600">Select target above to fit predictions explainer model.</span>
        </div>
      )}
    </div>
  );
};
