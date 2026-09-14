"use client";

import React from "react";
import { useWorkspace } from "@/context/WorkspaceContext";
import { X, AlertCircle, Sparkles, TrendingUp, Cpu, Copy, Check } from "lucide-react";
import {
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from "recharts";

type ColumnDetails = {
  name: string;
  semantic_type: string;
  raw_dtype: string;
  missing_pct: number;
  n_missing: number;
  n_total: number;
  n_unique: number;
  unique_pct: number;
  stats?: Record<string, unknown>;
  reasoning?: string[];
};

type FindingDetails = {
  finding_type: string;
  columns: string[];
  strength: string;
  title: string;
  reasoning?: string[];
  suggested_next_step?: string;
  evidence?: Record<string, unknown>;
};

type TransformDetails = {
  columns: string[];
  title: string;
  transform?: string;
  evidence?: Record<string, unknown>;
  reasoning?: string[];
  code_snippet?: string;
};

type ShapContribution = {
  feature: string;
  effect: number;
  value: unknown;
};

type ShapDetails = {
  row_index: number;
  predicted_label: unknown;
  predicted_probability?: number;
  summary?: string;
  contributions?: ShapContribution[];
};

const EvidenceTable: React.FC<{ evidence: Record<string, unknown> }> = ({ evidence }) => {
  const rows = Object.entries(evidence).filter(([, value]) =>
    typeof value !== "object" || value === null
  );
  if (rows.length === 0) {
    return <div className="text-[10px] text-zinc-500 text-center py-8 border border-dashed border-zinc-800 rounded">No chart-ready evidence was produced for this discovery.</div>;
  }
  return (
    <div className="rounded border border-zinc-800 bg-zinc-950/60 p-3 space-y-2 text-xs font-mono">
      {rows.map(([key, value]) => (
        <div key={key} className="flex justify-between gap-3 border-b border-zinc-800/60 pb-1.5 last:border-0 last:pb-0">
          <span className="text-zinc-500">{key.replaceAll("_", " ")}</span>
          <span className="text-zinc-200 text-right break-all">{String(value)}</span>
        </div>
      ))}
    </div>
  );
};

export const RightPanel: React.FC = () => {
  const { rightPanel, closeRightPanel, showToast } = useWorkspace();
  const [copied, setCopied] = React.useState(false);

  if (!rightPanel.isOpen || !rightPanel.type) return null;

  const { type, data } = rightPanel;

  const handleCopyCode = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    showToast("Code copied to clipboard!");
    setTimeout(() => setCopied(false), 2000);
  };

  const renderContent = () => {
    switch (type) {
      case "column":
        return renderColumnPanel(data);
      case "discovery":
        return renderDiscoveryPanel(data);
      case "transform":
        return renderTransformPanel(data);
      case "SHAP":
        return renderShapPanel(data);
      default:
        return <div className="text-zinc-500">No content available.</div>;
    }
  };

  // ----------------------------------------------------
  // Column Details view
  // ----------------------------------------------------
  const renderColumnPanel = (value: unknown) => {
    const col = value as ColumnDetails;
    const isNum = col.semantic_type.includes("numeric") || col.raw_dtype.includes("int") || col.raw_dtype.includes("float");
    const topStats = col.stats || {};
    
    return (
      <div className="space-y-6">
        <div>
          <div className="text-[10px] uppercase font-bold tracking-wider text-emerald-400 mb-1">
            Column Metadata
          </div>
          <h2 className="text-xl font-semibold text-zinc-100 font-mono tracking-tight break-all">
            {col.name}
          </h2>
          <div className="flex gap-2 mt-2">
            <span className="text-[10px] px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 font-mono border border-zinc-700">
              {col.raw_dtype}
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 font-mono border border-emerald-900/30 uppercase">
              {col.semantic_type.replace("_", " ")}
            </span>
          </div>
        </div>

        {/* Essential Metrics Grid */}
        <div className="grid grid-cols-2 gap-2">
          <div className="p-3 bg-zinc-900 border border-zinc-800/80 rounded">
            <div className="text-[10px] text-zinc-500 font-medium">Missing Values</div>
            <div className="text-lg font-bold text-zinc-200 mt-1 font-mono">
              {col.missing_pct}%
            </div>
            <div className="text-[9px] text-zinc-500">{col.n_missing} of {col.n_total} rows</div>
          </div>
          <div className="p-3 bg-zinc-900 border border-zinc-800/80 rounded">
            <div className="text-[10px] text-zinc-500 font-medium">Unique Values</div>
            <div className="text-lg font-bold text-zinc-200 mt-1 font-mono">
              {col.n_unique}
            </div>
            <div className="text-[9px] text-zinc-500">{(col.unique_pct * 100).toFixed(1)}% cardinality</div>
          </div>
        </div>

        {/* Statistical Summary */}
        {Object.keys(topStats).length > 0 && (
          <div className="p-4 bg-zinc-900 border border-zinc-800/80 rounded space-y-3">
            <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
              Statistical Summary
            </h3>
            <div className="grid grid-cols-2 gap-3 text-xs font-mono">
              {Object.entries(topStats).map(([key, val]) => (
                <div key={key} className="flex justify-between border-b border-zinc-800/60 pb-1.5">
                  <span className="text-zinc-500 capitalize">{key.replace("_", " ")}</span>
                  <span className="text-zinc-300 font-semibold">
                    {typeof val === "number" ? (val % 1 === 0 ? val : val.toFixed(2)) : String(val)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Semantic Classification Reasoning Trail */}
        {col.reasoning && col.reasoning.length > 0 && (
          <div className="space-y-2">
            <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Classification Reasoning
            </h3>
            <div className="space-y-1.5">
              {col.reasoning.map((reason: string, idx: number) => (
                <div key={idx} className="flex gap-2.5 items-start p-2.5 bg-zinc-900/60 rounded text-xs text-zinc-400">
                  <span className="text-emerald-500 font-bold font-mono">0{idx + 1}.</span>
                  <span>{reason}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Suggested investigation */}
        <div className="p-4 bg-emerald-950/20 border border-emerald-900/40 rounded space-y-2">
          <h3 className="text-xs font-semibold text-emerald-400 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Suggested Action</span>
          </h3>
          <p className="text-xs text-zinc-400 leading-relaxed">
            {isNum 
              ? "Consider checking for outliers using Box Plots or applying standard scaling before feeding this continuous variable to distance-based models."
              : "Consider grouping rare categories and applying One-Hot Encoding to prepare this variable for training."}
          </p>
        </div>
      </div>
    );
  };

  // ----------------------------------------------------
  // Discovery detailed Scientific Argument
  // ----------------------------------------------------
  const renderDiscoveryPanel = (value: unknown) => {
    const finding = value as FindingDetails;
    // Generate charts based on finding structure
    const renderDiscoveryChart = () => {
      const ev = finding.evidence || {};
      
      if (finding.finding_type === "correlation") {
        return <EvidenceTable evidence={ev} />;
      }

      if (finding.finding_type === "group_difference") {
        const means = ev.group_means || {};
        const chartData = Object.entries(means).map(([cat, meanVal]) => ({
          category: cat,
          mean: meanVal,
        }));

        return (
          <div className="h-44 bg-zinc-950/60 rounded border border-zinc-900 p-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 10, bottom: 25, left: -15 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis dataKey="category" stroke="#71717a" fontSize={9} />
                <YAxis stroke="#71717a" fontSize={9} />
                <RechartsTooltip />
                <Bar dataKey="mean" fill="#10b981" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        );
      }

      if (finding.finding_type === "distribution_skew") {
        return <EvidenceTable evidence={ev} />;
      }

      return (
        <EvidenceTable evidence={ev} />
      );
    };

    return (
      <div className="space-y-6">
        <div>
          <div className="flex justify-between items-center gap-2 mb-1">
            <span className="text-[9px] uppercase font-bold tracking-wider text-emerald-400">
              Scientific Evidence
            </span>
            <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-400 uppercase font-mono tracking-tighter border border-emerald-900/30">
              {finding.strength} Confidence
            </span>
          </div>
          <h2 className="text-md font-semibold text-zinc-100 leading-snug">
            {finding.title}
          </h2>
          <p className="text-[10px] text-zinc-500 mt-1 font-mono">
            Type: {finding.finding_type} · Columns: {finding.columns.join(", ")}
          </p>
        </div>

        {/* Scientific argument block */}
        <div className="space-y-4">
          {/* Section 1: Observation */}
          <div className="space-y-1">
            <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              01. Observation
            </h3>
            <p className="text-xs text-zinc-300 leading-relaxed bg-zinc-900/60 p-3 rounded border border-zinc-800/40">
              {finding.reasoning?.[0] || "We detected a strong pattern suggesting a structured relationship in the variables."}
            </p>
          </div>

          {/* Section 2: Visual Evidence */}
          <div className="space-y-2">
            <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              02. Evidence
            </h3>
            {renderDiscoveryChart()}
          </div>

          {/* Section 3: Statistical Validation */}
          <div className="space-y-2">
            <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              03. Statistical Verification
            </h3>
            <div className="p-3 bg-zinc-900 border border-zinc-800/80 rounded space-y-2.5 text-xs">
              <p className="text-zinc-400 leading-relaxed">
                This discovery is an exploratory lead. Use the Statistics stage to run a formal significance test; DetaBeta does not invent a p-value or effect size here.
              </p>
            </div>
          </div>

          {/* Section 4: Interpretation & Limitations */}
          <div className="space-y-2">
            <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              04. Interpretation & Limitations
            </h3>
            <div className="text-xs text-zinc-400 leading-relaxed space-y-2 bg-zinc-900/30 p-3 rounded border border-zinc-850">
              <p>
                <strong>What it means:</strong> {finding.reasoning?.[1] || "The variables exhibit structurally different properties across the groups."}
              </p>
              <div className="flex items-start gap-1.5 text-[11px] text-amber-500/90 border-t border-zinc-800/80 pt-2 mt-2">
                <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                <span>
                  <strong>Caveat:</strong> This identifies an association. It does not establish direct causality.
                </span>
              </div>
            </div>
          </div>

          {/* Suggested next question */}
          {finding.suggested_next_step && (
            <div className="p-3.5 bg-emerald-950/20 border border-emerald-900/40 rounded space-y-1.5">
              <h4 className="text-xs font-semibold text-emerald-400 flex items-center gap-1.5">
                <TrendingUp className="w-3.5 h-3.5" />
                <span>Next Investigation Question</span>
              </h4>
              <p className="text-xs text-zinc-400 leading-relaxed font-serif">
                &quot;{finding.suggested_next_step}&quot;
              </p>
            </div>
          )}
        </div>
      </div>
    );
  };

  // ----------------------------------------------------
  // Transform Preview (Before vs After)
  // ----------------------------------------------------
  const renderTransformPanel = (value: unknown) => {
    const rec = value as TransformDetails;

    return (
      <div className="space-y-6">
        <div>
          <span className="text-[10px] uppercase font-bold tracking-wider text-emerald-400 mb-1 block">
            Transformation Preview
          </span>
          <h2 className="text-lg font-semibold text-zinc-100">
            {rec.title}
          </h2>
          <p className="text-[10px] text-zinc-500 mt-0.5">
            Applies to: <span className="font-mono">{rec.columns.join(", ")}</span>
          </p>
        </div>

        <div className="p-3.5 bg-zinc-900 border border-zinc-800 rounded space-y-2 text-xs">
          <h3 className="font-semibold text-zinc-300">What will change</h3>
          <p className="text-zinc-400 leading-relaxed">
            {rec.reasoning?.[0] || "This preview describes the recommended operation. Apply it only when the change matches your modelling decision."}
          </p>
          {rec.evidence && <EvidenceTable evidence={rec.evidence} />}
        </div>

        {/* Copy paste Code Snippet */}
        {rec.code_snippet && (
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                Python Implementation
              </h3>
              <button
                onClick={() => handleCopyCode(rec.code_snippet ?? "")}
                className="flex items-center gap-1 text-[10px] text-zinc-500 hover:text-zinc-300 font-mono transition"
              >
                {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                <span>{copied ? "Copied" : "Copy"}</span>
              </button>
            </div>
            <pre className="p-3.5 bg-zinc-950 text-zinc-300 font-mono text-[10px] rounded border border-zinc-900 overflow-x-auto">
              <code>{rec.code_snippet}</code>
            </pre>
          </div>
        )}
      </div>
    );
  };

  // ----------------------------------------------------
  // local Explainability SHAP waterfall
  // ----------------------------------------------------
  const renderShapPanel = (value: unknown) => {
    const shap = value as ShapDetails;
    // Real Shapley values from Engine 8 (approximated by coalition sampling).
    const contributions = shap.contributions || [];
    // Classification exposes a probability; regression does not. This decides
    // whether effects are shown as percentage points or raw target units.
    const isProbability = typeof shap.predicted_probability === "number";
    const fmtEffect = (effect: number) =>
      isProbability
        ? `${effect >= 0 ? "+" : ""}${(effect * 100).toFixed(1)}%`
        : `${effect >= 0 ? "+" : ""}${effect.toFixed(3)}`;

    // Map contributions to chart data
    const chartData = contributions.map((contribution) => ({
      feature: contribution.feature,
      effect: contribution.effect,
      fill: contribution.effect >= 0 ? "#10b981" : "#ef4444", // green pushes prediction up, red pulls it down
    }));

    return (
      <div className="space-y-6">
        <div>
          <span className="text-[10px] uppercase font-bold tracking-wider text-emerald-400 mb-1 block">
            Local Explainability
          </span>
          <h2 className="text-lg font-semibold text-zinc-100 font-mono">
            Row #{shap.row_index} Explanation
          </h2>
          <div className="flex gap-2 items-center mt-2 text-xs">
            <span className="text-zinc-500">Prediction:</span>
            <span className="font-semibold text-zinc-200">{String(shap.predicted_label)}</span>
            {typeof shap.predicted_probability === "number" && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-900 text-zinc-300 border border-zinc-800 font-mono">
                Positive-class probability: {(shap.predicted_probability * 100).toFixed(0)}%
              </span>
            )}
          </div>
        </div>

        {/* Description */}
        <div className="p-3 bg-zinc-900 border border-zinc-850 rounded text-xs text-zinc-400 leading-relaxed">
          {shap.summary || "This represents how features pushed the prediction relative to the dataset average baseline."}
        </div>

        {/* Feature contribution graph */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Feature Contribution Signals
            </h3>
            <div className="flex items-center gap-3 text-[9px] text-zinc-500 font-mono">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-emerald-500 inline-block" />pushes up</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-rose-500 inline-block" />pulls down</span>
            </div>
          </div>
          <div className="h-56 bg-zinc-950/60 rounded border border-zinc-900 p-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={chartData}
                layout="vertical"
                margin={{ top: 10, right: 10, bottom: 5, left: 15 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis type="number" stroke="#71717a" fontSize={8} />
                <YAxis dataKey="feature" type="category" stroke="#71717a" fontSize={8} />
                <RechartsTooltip />
                <Bar dataKey="effect" radius={[0, 2, 2, 0]}>
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Detail Breakdown list */}
        <div className="space-y-2">
          <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
            Key Factor Breakdown
          </h3>
          <div className="space-y-1.5 text-xs">
            {contributions.map((c, idx) => {
              const isIncrease = c.effect >= 0;
              return (
                <div key={idx} className="flex justify-between items-center p-2 bg-zinc-900/60 rounded">
                  <div className="space-y-0.5">
                    <span className="font-medium text-zinc-300">{c.feature}</span>
                    <div className="text-[10px] text-zinc-500 font-mono">value: {String(c.value)}</div>
                  </div>
                  <span className={`font-mono font-semibold px-2 py-0.5 rounded text-[10px] ${
                    isIncrease
                      ? "bg-emerald-950/40 text-emerald-400 border border-emerald-900/20"
                      : "bg-rose-950/40 text-rose-400 border border-rose-900/20"
                  }`}>
                    {fmtEffect(c.effect)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  };

  return (
    <aside className="w-80 h-screen bg-[#0f0f11] border-l border-zinc-800 flex flex-col z-15 relative">
      {/* Panel Header */}
      <div className="h-14 flex items-center justify-between px-4 border-b border-zinc-800">
        <div className="flex items-center gap-1.5 text-zinc-400 text-xs">
          <Cpu className="w-4 h-4 text-emerald-400" />
          <span className="font-semibold tracking-wide">Context Inspector</span>
        </div>
        <button
          onClick={closeRightPanel}
          className="p-1 hover:bg-zinc-800 text-zinc-500 hover:text-zinc-100 rounded transition"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Panel Scrollable Content */}
      <div className="flex-1 overflow-y-auto p-5">{renderContent()}</div>
    </aside>
  );
};
