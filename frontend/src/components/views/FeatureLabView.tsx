"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useWorkspace } from "@/context/WorkspaceContext";
import { Info, Loader2, AlertTriangle } from "lucide-react";

type FeatureRecommendation = {
  transform: string;
  columns: string[];
  evidence?: Record<string, unknown>;
  title?: string;
  priority: string;
  reasoning?: string[];
  warnings?: string[];
};

type FeatureLabReport = {
  recommendations: FeatureRecommendation[];
};

export const FeatureLabView: React.FC = () => {
  const { selectedDatasetId, runAnalysis, openRightPanel, applyTransform, showToast } = useWorkspace();
  const [report, setReport] = useState<FeatureLabReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [applyingIdx, setApplyingIdx] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadFeatureRecommendations = useCallback(async () => {
    if (!selectedDatasetId) return;

    setLoading(true);
    setError(null);
    setReport(null);
    try {
      const data = await runAnalysis("feature-lab");
      setReport(data as FeatureLabReport);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Feature recommendations could not be loaded."
      );
    } finally {
      setLoading(false);
    }
  }, [runAnalysis, selectedDatasetId]);

  useEffect(() => {
    if (!selectedDatasetId) return;

    let cancelled = false;
    async function load() {
      if (cancelled) return;
      await loadFeatureRecommendations();
    }

    void load();
    return () => { cancelled = true; };
  }, [loadFeatureRecommendations, selectedDatasetId]);

  const handleApplyTransform = async (rec: FeatureRecommendation, idx: number) => {
    if (!selectedDatasetId) return;
    setApplyingIdx(idx);
    try {
      const result = await applyTransform(selectedDatasetId, {
        transform: rec.transform,
        columns: rec.columns,
        evidence: rec.evidence,
        title: rec.title,
      });
      const { score: before } = result.health_before;
      const { score: after, grade } = result.health_after;
      const delta = Math.round((after - before) * 10) / 10;
      const deltaText =
        delta > 0 ? `health +${delta} → ${after}/100 (${grade})`
        : delta < 0 ? `health ${delta} → ${after}/100 (${grade})`
        : `health unchanged at ${after}/100 (${grade})`;
      showToast(`Created ${result.dataset.name} — ${deltaText}`);
    } catch {
      // apiFetch has already shown the detailed error toast.
    } finally {
      setApplyingIdx(null);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex flex-col justify-center items-center min-h-[300px]">
        <Loader2 className="w-8 h-8 text-emerald-400 animate-spin" />
        <span className="text-xs text-zinc-500 mt-3 font-mono">Running feature recommendation engine...</span>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="max-w-xl mx-auto mt-12 p-6 text-center rounded-xl border border-rose-900/40 bg-rose-950/10 space-y-4">
        <AlertTriangle className="w-6 h-6 text-rose-400 mx-auto" />
        <div>
          <h2 className="text-sm font-semibold text-zinc-200">Feature Lab could not load</h2>
          <p className="text-xs text-zinc-400 mt-2 leading-relaxed">
            {error || "Select a dataset to receive feature recommendations."}
          </p>
        </div>
        {selectedDatasetId && (
          <button
            onClick={() => void loadFeatureRecommendations()}
            className="px-3.5 py-1.5 rounded bg-emerald-500 hover:bg-emerald-600 text-zinc-950 text-xs font-semibold transition"
          >
            Try Again
          </button>
        )}
      </div>
    );
  }

  const recommendations = report.recommendations;

  const getPriorityBadgeClass = (priority: string) => {
    switch (priority) {
      case "essential":
        return "bg-rose-950 text-rose-400 border border-rose-900/30";
      case "recommended":
        return "bg-emerald-950 text-emerald-400 border border-emerald-900/30";
      default:
        return "bg-zinc-800 text-zinc-400 border border-zinc-700";
    }
  };

  return (
    <div className="space-y-6 py-4">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-zinc-100">Feature Lab</h1>
        <p className="text-xs text-zinc-500 mt-1">
          Explore ways to improve how your data represents the problem. Recommends mathematical encodings, scales, and cleanups.
        </p>
      </div>

      {/* Intro alert */}
      <div className="p-4 bg-zinc-900/30 border border-zinc-800 rounded-lg flex items-start gap-3">
        <Info className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
        <div className="text-xs text-zinc-400 leading-relaxed">
          <strong>Design principle:</strong> DetaBeta recommends but never forces. Applying a transformation creates a new version of the dataset so you never overwrite your raw evidence.
        </div>
      </div>

      {/* Recommendations Cards list */}
      <div className="space-y-4">
        {recommendations.length > 0 ? (
          recommendations.map((rec, idx) => {
            const isApplying = applyingIdx === idx;
            
            return (
              <div
                key={idx}
                className="bg-[#18181b]/60 border border-zinc-800 hover:border-zinc-700/80 rounded-lg p-5 flex flex-col justify-between transition"
              >
                <div>
                  <div className="flex justify-between items-center gap-2 mb-2">
                    <span className="text-[9px] font-mono font-bold text-zinc-500 uppercase tracking-widest">
                      RECOMMENDED TRANSFORMATION
                    </span>
                    <span className={`text-[8px] font-bold uppercase tracking-wider font-mono px-2 py-0.5 rounded border ${getPriorityBadgeClass(rec.priority)}`}>
                      {rec.priority}
                    </span>
                  </div>
                  
                  <h3 className="font-semibold text-sm text-zinc-200">
                    {rec.title}
                  </h3>
                  <div className="text-[10px] text-zinc-500 font-mono mt-1">
                    Target Column: {rec.columns.join(", ")} · Code: <code className="text-emerald-400">{rec.transform}</code>
                  </div>

                  <p className="text-xs text-zinc-400 mt-3 leading-relaxed">
                    <strong>Why?</strong> {rec.reasoning?.[0] || "We recommend applying this encoder to resolve statistical constraints."}
                  </p>

                  {rec.warnings && rec.warnings.length > 0 && (
                    <div className="flex items-start gap-1.5 text-[10px] text-amber-500/90 mt-2">
                      <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                      <span>{rec.warnings[0]}</span>
                    </div>
                  )}
                </div>

                {/* Footer Buttons */}
                <div className="mt-5 border-t border-zinc-850 pt-3.5 flex justify-end gap-2 text-[10px] font-semibold">
                  <button
                    onClick={() => openRightPanel("transform", rec)}
                    className="px-3 py-1.5 border border-zinc-800 hover:bg-zinc-850 rounded text-zinc-400 transition cursor-pointer"
                  >
                    Preview Transformation
                  </button>
                  <button
                    onClick={() => handleApplyTransform(rec, idx)}
                    disabled={isApplying}
                    className="flex items-center gap-1 px-3.5 py-1.5 bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-zinc-950 rounded transition cursor-pointer"
                  >
                    {isApplying && <Loader2 className="w-3 h-3 animate-spin" />}
                    <span>{isApplying ? "Creating Version..." : "Apply to New Dataset Version"}</span>
                  </button>
                </div>
              </div>
            );
          })
        ) : (
          <div className="text-center py-20 text-zinc-650 font-mono text-xs border border-dashed border-zinc-800 rounded-lg">
            No transformations needed. Columns are already well structured.
          </div>
        )}
      </div>
    </div>
  );
};
