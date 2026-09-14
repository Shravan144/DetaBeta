"use client";

import React, { useState, useEffect } from "react";
import { useWorkspace } from "@/context/WorkspaceContext";
import { pickDefaultTarget } from "@/lib/target-selection";
import { Loader2, BrainCircuit } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from "recharts";

// ----------------------------------------------------
// Real cross-validated confusion matrix (binary + multiclass)
// ----------------------------------------------------
type ConfusionMatrix = {
  accuracy: number;
  is_binary: boolean;
  positive_label?: unknown;
  n_samples: number;
  true_negative?: number;
  false_positive?: number;
  false_negative?: number;
  true_positive?: number;
  labels?: unknown[];
  matrix?: number[][];
};

type FeatureImportance = { feature: string; importance: number; share: number };

type FeatureContribution = { feature: string; effect: number; value: unknown };

type PredictionExplanation = {
  row_index: number;
  predicted_label: unknown;
  predicted_probability?: number;
  baseline_prediction: number;
  contributions: FeatureContribution[];
};

type ExplainabilityReport = {
  model_name: string;
  global_importances: FeatureImportance[];
  examples: PredictionExplanation[];
  confusion?: ConfusionMatrix | null;
};

const ConfusionMatrixPanel: React.FC<{ confusion: ConfusionMatrix | null | undefined }> = ({ confusion }) => {
  if (!confusion) {
    return (
      <div className="text-[11px] text-zinc-500 text-center py-8 border border-dashed border-zinc-800 rounded">
        A confusion matrix only applies to classification targets. This target is
        continuous (regression), so error is measured by residuals instead.
      </div>
    );
  }

  const accuracyPct = (confusion.accuracy * 100).toFixed(1);

  // Binary: the familiar TN / FP / FN / TP quadrants with real counts.
  if (confusion.is_binary) {
    const {
      true_negative: tn = 0,
      false_positive: fp = 0,
      false_negative: fn = 0,
      true_positive: tp = 0,
    } = confusion;
    const cell = (label: string, value: number, sub: string, good: boolean) => (
      <div className="p-4 bg-zinc-950/60 rounded border border-zinc-900 flex flex-col justify-center">
        <span className="text-[10px] text-zinc-500 uppercase">{label}</span>
        <strong className={`text-sm mt-1 ${good ? "text-zinc-200" : "text-rose-400"}`}>{value}</strong>
        <span className={`text-[9px] mt-0.5 ${good ? "text-emerald-400" : "text-rose-500/80"}`}>{sub}</span>
      </div>
    );
    return (
      <div className="space-y-3">
        <div className="text-[10px] text-zinc-500 text-center font-mono">
          Positive class: <span className="text-zinc-300">{String(confusion.positive_label)}</span> · Accuracy {accuracyPct}% · {confusion.n_samples} rows
        </div>
        <div className="grid grid-cols-2 gap-2 max-w-xs mx-auto text-center font-mono text-xs">
          {cell("True Negative", tn, "Correct", true)}
          {cell("False Positive", fp, "Type I Error", false)}
          {cell("False Negative", fn, "Type II Error", false)}
          {cell("True Positive", tp, "Correct", true)}
        </div>
      </div>
    );
  }

  // Multiclass: full labels x labels grid, diagonal (correct) highlighted.
  const labels = confusion.labels ?? [];
  const matrix: number[][] = confusion.matrix || [];
  return (
    <div className="space-y-3">
      <div className="text-[10px] text-zinc-500 text-center font-mono">
        Accuracy {accuracyPct}% · {confusion.n_samples} rows · rows = actual, columns = predicted
      </div>
      <div className="overflow-x-auto">
        <table className="mx-auto border-collapse font-mono text-[10px]">
          <thead>
            <tr>
              <th className="p-1.5" />
              {labels.map((l) => (
                <th key={`h-${l}`} className="p-1.5 text-zinc-500 font-medium">{String(l)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.map((row, i) => (
              <tr key={`r-${i}`}>
                <th className="p-1.5 text-right text-zinc-500 font-medium">{String(labels[i])}</th>
                {row.map((count, j) => {
                  const isDiag = i === j;
                  return (
                    <td
                      key={`c-${i}-${j}`}
                      className={`p-2.5 text-center border border-zinc-900 ${
                        isDiag ? "bg-emerald-950/40 text-emerald-300" : count > 0 ? "bg-rose-950/20 text-rose-300" : "bg-zinc-950/60 text-zinc-600"
                      }`}
                    >
                      {count}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export const ExplainabilityView: React.FC = () => {
  const { selectedDatasetId, runAnalysis, openRightPanel, apiFetch, selectedTarget, setSelectedTarget } = useWorkspace();
  
  const [columns, setColumns] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<ExplainabilityReport | null>(null);
  
  // Local prediction selection
  const [selectedRowIndex, setSelectedRowIndex] = useState<number | null>(null);

  // Load columns to set default target
  useEffect(() => {
    if (!selectedDatasetId) return;

    let cancelled = false;
    async function loadColumnsAndExplain() {
      setLoading(true);
      try {
        const preview = await apiFetch<{ columns?: string[] }>(`/datasets/${selectedDatasetId}/preview`);
        if (!cancelled) {
          const cols = preview.columns ?? [];
          setColumns(cols);

        // Pick a sensible default target: a column that looks like a label/
        // outcome, otherwise fall back to the last column. No dataset-specific
        // assumptions.
        const defaultTgt = selectedTarget ?? pickDefaultTarget(cols);

        if (defaultTgt) {
          if (!selectedTarget) setSelectedTarget(defaultTgt);
          // Run explain engine
          const data = await runAnalysis("explain", defaultTgt);
          const explainability = data as unknown as ExplainabilityReport;
          setReport(explainability);
          const examples = explainability.examples;
          if (examples && examples.length > 0) {
            setSelectedRowIndex(examples[0].row_index);
          }
        }
        }
      } catch {
        if (!cancelled) setReport(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadColumnsAndExplain();
    return () => { cancelled = true; };
  }, [apiFetch, runAnalysis, selectedDatasetId, selectedTarget, setSelectedTarget]);

  const target = selectedTarget ?? "";

  const handleTargetChange = async (newTarget: string) => {
    setSelectedTarget(newTarget || null);
    if (!newTarget) {
      setReport(null);
      return;
    }
    setLoading(true);
    try {
      const data = await runAnalysis("explain", newTarget);
      const explainability = data as unknown as ExplainabilityReport;
      setReport(explainability);
      const examples = explainability.examples;
      if (examples && examples.length > 0) {
        setSelectedRowIndex(examples[0].row_index);
      }
    } catch {
      setReport(null);
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
  const globalData = (report?.global_importances ?? []).map((imp) => ({
    name: imp.feature,
    importance: imp.importance,
    percentage: (imp.share * 100).toFixed(0) + "%",
  })).sort((a, b) => b.importance - a.importance);

  // Selected row explanation details
  const activeExplanation = (report?.examples ?? []).find((example) => example.row_index === selectedRowIndex);

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
                  Out-of-fold (cross-validated) predictions. Shows real misclassifications, not training-set memorization.
                </p>
              </div>

              <ConfusionMatrixPanel confusion={report.confusion} />
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
                  {report.examples.map((ex) => (
                    <option key={ex.row_index} value={ex.row_index}>
                      Row #{ex.row_index} → {target}: {String(ex.predicted_label)}
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
                      {typeof activeExplanation.predicted_probability === "number"
                        ? `Baseline: ${(activeExplanation.baseline_prediction * 100).toFixed(0)}% → Final: ${(activeExplanation.predicted_probability * 100).toFixed(0)}%`
                        : `Baseline: ${Number(activeExplanation.baseline_prediction).toFixed(2)} → Predicted: ${Number(activeExplanation.predicted_label).toFixed(2)}`}
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
