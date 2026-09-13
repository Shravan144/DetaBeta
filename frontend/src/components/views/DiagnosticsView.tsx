"use client";

import React, { useState, useEffect } from "react";
import { useWorkspace } from "@/context/WorkspaceContext";
import { CheckCircle, Loader2 } from "lucide-react";

type HealthIssue = {
  severity: string;
  category: string;
  title: string;
  column?: string;
  reasoning?: string[];
  evidence?: Record<string, unknown>;
  recommendation?: string;
};

type HealthReport = {
  score: number;
  grade: string;
  issues: HealthIssue[];
};

export const DiagnosticsView: React.FC = () => {
  const { selectedDatasetId, runAnalysis, openRightPanel } = useWorkspace();
  const [report, setReport] = useState<HealthReport | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selectedDatasetId) return;

    let cancelled = false;
    async function loadHealthReport() {
      setLoading(true);
      try {
        const data = await runAnalysis("health");
        if (!cancelled) setReport(data as HealthReport);
      } catch {
        if (!cancelled) setReport(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadHealthReport();
    return () => { cancelled = true; };
  }, [runAnalysis, selectedDatasetId]);

  if (loading) {
    return (
      <div className="flex-1 flex flex-col justify-center items-center min-h-[300px]">
        <Loader2 className="w-8 h-8 text-emerald-400 animate-spin" />
        <span className="text-xs text-zinc-500 mt-3 font-mono">Running scientific diagnostics checks...</span>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="text-zinc-500 text-center py-20">
        Failed to load diagnostics report.
      </div>
    );
  }

  // Derived breakdowns from issues
  const calculateBreakdown = () => {
    let completeness = 100;
    let consistency = 100;
    let validity = 100;
    let uniqueness = 100;
    let distribution = 100;

    const penaltyMap: Record<string, number> = {
      info: 0,
      low: 2,
      medium: 6,
      high: 12,
      critical: 25,
    };

    report.issues.forEach((issue) => {
      const penalty = penaltyMap[issue.severity] || 2;
      switch (issue.category) {
        case "missing_values":
          completeness = Math.max(0, completeness - penalty * 1.5);
          break;
        case "inconsistent_values":
        case "rare_category":
          consistency = Math.max(0, consistency - penalty * 1.5);
          break;
        case "constant_column":
        case "class_imbalance":
          validity = Math.max(0, validity - penalty * 1.5);
          break;
        case "duplicate_rows":
        case "high_cardinality":
          uniqueness = Math.max(0, uniqueness - penalty * 1.5);
          break;
        case "outliers":
          distribution = Math.max(0, distribution - penalty * 1.5);
          break;
      }
    });

    return {
      completeness: Math.round(completeness),
      consistency: Math.round(consistency),
      validity: Math.round(validity),
      uniqueness: Math.round(uniqueness),
      distribution: Math.round(distribution),
    };
  };

  const breakdown = calculateBreakdown();
  const issuesList = report.issues;

  const getSeverityBadgeClass = (severity: string) => {
    switch (severity) {
      case "critical":
      case "high":
        return "bg-rose-950/40 text-rose-400 border-rose-900/30";
      case "medium":
        return "bg-amber-950/40 text-amber-400 border-amber-900/30";
      default:
        return "bg-zinc-800 text-zinc-400 border-zinc-700";
    }
  };

  return (
    <div className="space-y-8 py-4">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-zinc-100">Data Diagnostics</h1>
        <p className="text-xs text-zinc-500 mt-1">
          Automated evaluation of dataset health. Surfaces evidence-backed issues and recommended mitigations.
        </p>
      </div>

      {/* Prominent Health Score & Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 bg-zinc-900/30 border border-zinc-800 rounded-xl p-6">
        {/* Left Circular Metric */}
        <div className="flex flex-col items-center justify-center border-b lg:border-b-0 lg:border-r border-zinc-800 pb-6 lg:pb-0 lg:pr-6">
          <span className="text-[10px] uppercase font-bold tracking-wider text-zinc-500 mb-4">
            Overall Health Score
          </span>
          <div className="relative w-36 h-36 flex items-center justify-center">
            {/* SVG radial track */}
            <svg className="w-full h-full transform -rotate-90">
              <circle
                cx="72"
                cy="72"
                r="64"
                stroke="#18181b"
                strokeWidth="8"
                fill="transparent"
              />
              <circle
                cx="72"
                cy="72"
                r="64"
                stroke="#10b981"
                strokeWidth="8"
                fill="transparent"
                strokeDasharray="402"
                strokeDashoffset={402 - (402 * report.score) / 100}
                strokeLinecap="round"
                className="transition-all duration-1000 ease-out"
              />
            </svg>
            <div className="absolute flex flex-col items-center">
              <span className="text-3xl font-black text-zinc-100 font-mono tracking-tighter">
                {report.score}
              </span>
              <span className="text-[10px] text-zinc-500 uppercase tracking-widest font-bold">
                GRADE {report.grade}
              </span>
            </div>
          </div>
          <span className="text-[11px] text-zinc-400 font-medium mt-4">
            {report.score >= 75 ? "Dataset is clean & trustworthy" : "Requires attention before modeling"}
          </span>
        </div>

        {/* Right Breakdown Grid */}
        <div className="lg:col-span-2 flex flex-col justify-center space-y-4">
          <span className="text-[10px] uppercase font-bold tracking-wider text-zinc-500">
            Dimensions Breakdown
          </span>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            {[
              { label: "Completeness", val: breakdown.completeness, desc: "Nulls percentage" },
              { label: "Consistency", val: breakdown.consistency, desc: "Format anomalies" },
              { label: "Validity", val: breakdown.validity, desc: "Range checks" },
              { label: "Uniqueness", val: breakdown.uniqueness, desc: "Row duplication" },
              { label: "Distribution", val: breakdown.distribution, desc: "Skew/outliers" },
            ].map((metric) => (
              <div key={metric.label} className="p-3 bg-zinc-900 border border-zinc-850 rounded-lg">
                <span className="text-[10px] text-zinc-500 font-medium block">{metric.label}</span>
                <div className="text-md font-bold text-zinc-200 mt-1 font-mono">{metric.val}%</div>
                <div className="text-[9px] text-zinc-600 font-mono mt-0.5">{metric.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Diagnostics Issues list */}
      <div className="space-y-4">
        <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">
          {issuesList.length} Issue{issuesList.length === 1 ? "" : "s"} require attention
        </h2>

        {issuesList.length > 0 ? (
          <div className="space-y-4">
            {issuesList.map((issue, idx) => (
              <div
                key={idx}
                className="bg-[#18181b]/40 border border-zinc-800 rounded-lg overflow-hidden"
              >
                {/* Header */}
                <div className="px-5 py-3 bg-[#0f0f11] border-b border-zinc-850 flex justify-between items-center gap-4">
                  <div className="flex items-center gap-2.5">
                    <span className={`text-[8px] uppercase px-1.5 py-0.5 rounded font-mono font-bold tracking-wider border ${getSeverityBadgeClass(issue.severity)}`}>
                      {issue.severity} Impact
                    </span>
                    <span className="font-semibold text-xs text-zinc-200 truncate">
                      {issue.title}
                    </span>
                  </div>
                  {issue.column && (
                    <span className="text-[10px] font-mono bg-zinc-900 text-zinc-500 border border-zinc-800 px-2 py-0.5 rounded">
                      Column: {issue.column}
                    </span>
                  )}
                </div>

                {/* Structure: Observation -> Why it matters -> Evidence -> Suggested next step */}
                <div className="p-5 space-y-4 text-xs leading-relaxed">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Observation & Why it matters */}
                    <div className="space-y-3">
                      <div>
                        <div className="text-[9px] uppercase font-bold tracking-wider text-zinc-500 mb-1">
                          Observation
                        </div>
                        <p className="text-zinc-300">
                          We detected {issue.category.replace("_", " ")} issues affecting {issue.column || "the dataset"}.
                        </p>
                      </div>
                      <div>
                        <div className="text-[9px] uppercase font-bold tracking-wider text-zinc-500 mb-1">
                          Why this matters
                        </div>
                        <p className="text-zinc-400">
                          {issue.reasoning?.[0] || "Distortions or missing fields can bias statistics and result in poor ML model performance."}
                        </p>
                      </div>
                    </div>

                    {/* Evidence & Suggested Action */}
                    <div className="space-y-3">
                      <div>
                        <div className="text-[9px] uppercase font-bold tracking-wider text-zinc-500 mb-1">
                          Evidence
                        </div>
                        <p className="text-zinc-300 font-mono">
                          {Object.entries(issue.evidence || {}).map(([key, value]) => `${key}: ${String(value)}`).join(" · ") || "Statistical flags triggered."}
                        </p>
                      </div>
                      <div>
                        <div className="text-[9px] uppercase font-bold tracking-wider text-zinc-500 mb-1">
                          Suggested next step
                        </div>
                        <p className="text-zinc-400">
                          {issue.recommendation}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Actions footer */}
                  <div className="flex justify-end pt-3 border-t border-zinc-850">
                    <button
                      onClick={() => openRightPanel("column", { name: issue.column, semantic_type: "unknown", raw_dtype: "unknown", reasoning: issue.reasoning, stats: issue.evidence })}
                      className="px-3.5 py-1.5 rounded border border-zinc-800 hover:bg-zinc-850 text-zinc-300 text-[10px] font-semibold transition cursor-pointer"
                    >
                      Inspect Evidence
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex flex-col justify-center items-center py-16 border border-dashed border-zinc-800 rounded-lg space-y-2">
            <CheckCircle className="w-8 h-8 text-emerald-400" />
            <span className="text-xs text-zinc-300 font-semibold">Perfect dataset health!</span>
            <span className="text-[10px] text-zinc-500">We detected no data diagnostics anomalies.</span>
          </div>
        )}
      </div>
    </div>
  );
};
