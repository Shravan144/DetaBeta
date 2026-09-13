"use client";

import React, { useState, useEffect } from "react";
import { useWorkspace } from "@/context/WorkspaceContext";
import { Loader2, ArrowRight, Star } from "lucide-react";

type Finding = {
  strength: string;
  finding_type: string;
  title: string;
  [key: string]: unknown;
};

type InvestigationReport = {
  findings: Finding[];
};

export const InvestigationView: React.FC = () => {
  const { selectedDatasetId, runAnalysis, openRightPanel } = useWorkspace();
  const [report, setReport] = useState<InvestigationReport | null>(null);
  const [loading, setLoading] = useState(false);
  
  // Filter tabs
  const [activeFilter, setActiveFilter] = useState("all");

  useEffect(() => {
    if (!selectedDatasetId) return;

    let cancelled = false;
    async function loadInvestigationReport() {
      setLoading(true);
      try {
        const data = await runAnalysis("investigate");
        if (!cancelled) setReport(data as InvestigationReport);
      } catch {
        if (!cancelled) setReport(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadInvestigationReport();
    return () => { cancelled = true; };
  }, [runAnalysis, selectedDatasetId]);

  if (loading) {
    return (
      <div className="flex-1 flex flex-col justify-center items-center min-h-[300px]">
        <Loader2 className="w-8 h-8 text-emerald-400 animate-spin" />
        <span className="text-xs text-zinc-500 mt-3 font-mono">Running pattern discovery engine...</span>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="text-zinc-500 text-center py-20">
        Failed to load investigation report.
      </div>
    );
  }

  const findings = report.findings;

  // Summary counts
  const highConfCount = findings.filter((f) => f.strength === "very_strong" || f.strength === "strong").length;
  const medConfCount = findings.filter((f) => f.strength === "moderate").length;
  const exploratoryCount = findings.filter((f) => f.strength === "weak").length;

  const getStrengthBadgeClass = (strength: string) => {
    switch (strength) {
      case "very_strong":
      case "strong":
        return "bg-emerald-950 text-emerald-400 border border-emerald-900/30";
      case "moderate":
        return "bg-indigo-950 text-indigo-400 border border-indigo-900/30";
      default:
        return "bg-zinc-800 text-zinc-400 border border-zinc-700";
    }
  };

  const getFindingTypeLabel = (type: string) => {
    switch (type) {
      case "correlation":
        return "RELATIONSHIP";
      case "group_difference":
        return "GROUP DIFFERENCE";
      case "distribution_skew":
        return "DISTRIBUTION";
      case "dominant_category":
        return "ANOMALY";
      default:
        return "DISCOVERY";
    }
  };

  // Filtering findings
  const filteredFindings = findings.filter((f) => {
    if (activeFilter === "all") return true;
    if (activeFilter === "relationships" && f.finding_type === "correlation") return true;
    if (activeFilter === "groups" && f.finding_type === "group_difference") return true;
    if (activeFilter === "distributions" && f.finding_type === "distribution_skew") return true;
    if (activeFilter === "anomalies" && f.finding_type === "dominant_category") return true;
    return false;
  });

  return (
    <div className="space-y-6 py-4">
      {/* Signature header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-zinc-100">Investigation</h1>
        <p className="text-xs text-zinc-500 mt-1">
          Evidence-based discoveries found in your dataset by our statistical correlation and grouping algorithms.
        </p>
      </div>

      {/* Top Triage Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 border-b border-zinc-850 pb-5">
        <div className="p-4 bg-zinc-900/30 border border-zinc-800 rounded-lg">
          <span className="text-[10px] text-zinc-500 font-medium">Discoveries Found</span>
          <div className="text-xl font-bold text-zinc-100 mt-1 font-mono">{findings.length}</div>
        </div>
        <div className="p-4 bg-zinc-900/30 border border-zinc-800 rounded-lg">
          <span className="text-[10px] text-zinc-500 font-medium flex items-center gap-1">
            <Star className="w-3 h-3 text-emerald-400 fill-emerald-400" />
            <span>High Confidence</span>
          </span>
          <div className="text-xl font-bold text-emerald-400 mt-1 font-mono">{highConfCount}</div>
        </div>
        <div className="p-4 bg-zinc-900/30 border border-zinc-800 rounded-lg">
          <span className="text-[10px] text-zinc-500 font-medium">Medium Confidence</span>
          <div className="text-xl font-bold text-indigo-400 mt-1 font-mono">{medConfCount}</div>
        </div>
        <div className="p-4 bg-zinc-900/30 border border-zinc-800 rounded-lg">
          <span className="text-[10px] text-zinc-500 font-medium">Exploratory / Weak</span>
          <div className="text-xl font-bold text-zinc-400 mt-1 font-mono">{exploratoryCount}</div>
        </div>
      </div>

      {/* Filters bar */}
      <div className="flex overflow-x-auto gap-1 border-b border-zinc-850 pb-1 scrollbar-none">
        {[
          { key: "all", label: "All Discoveries" },
          { key: "relationships", label: "Relationships" },
          { key: "groups", label: "Group Differences" },
          { key: "distributions", label: "Distributions" },
          { key: "anomalies", label: "Anomalies" },
        ].map((tab) => {
          const isActive = activeFilter === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveFilter(tab.key)}
              className={`px-4 py-2 text-xs font-semibold rounded-t-lg transition whitespace-nowrap border-b-2 cursor-pointer ${
                isActive
                  ? "border-emerald-500 text-emerald-400 bg-zinc-900/40"
                  : "border-transparent text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Grid of Discovery Cards */}
      {filteredFindings.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {filteredFindings.map((finding, idx) => {
            const isStrong = finding.strength === "very_strong" || finding.strength === "strong";
            
            return (
              <div
                key={idx}
                className="group relative bg-[#18181b]/60 border border-zinc-805 hover:border-zinc-700/80 rounded-lg p-5 flex flex-col justify-between hover:shadow-xl transition-all duration-300 min-h-[170px]"
              >
                {/* Card Header Info */}
                <div>
                  <div className="flex justify-between items-center gap-2 mb-2">
                    <span className="text-[9px] font-mono font-bold text-zinc-650">
                      DISCOVERY #0{idx + 1}
                    </span>
                    <span className={`text-[8px] font-bold uppercase tracking-wide font-mono px-2 py-0.5 rounded border ${getStrengthBadgeClass(finding.strength)}`}>
                      {finding.strength.replace("_", " ")}
                    </span>
                  </div>
                  <h3 className="font-semibold text-sm text-zinc-200 group-hover:text-emerald-400 transition leading-snug line-clamp-2">
                    {finding.title}
                  </h3>
                </div>

                {/* Card Footer Details */}
                <div className="mt-6 border-t border-zinc-850 pt-3.5 flex items-center justify-between">
                  <div className="flex gap-4 text-[9px] font-mono text-zinc-500">
                    <div>
                      <span className="text-zinc-600 uppercase block text-[8px] font-sans font-bold tracking-wider">Type</span>
                      <span className="text-zinc-400 font-semibold">{getFindingTypeLabel(finding.finding_type)}</span>
                    </div>
                    <div>
                      <span className="text-zinc-600 uppercase block text-[8px] font-sans font-bold tracking-wider">Importance</span>
                      <span className={`font-semibold ${isStrong ? "text-emerald-400" : "text-indigo-400"}`}>
                        {isStrong ? "High" : "Medium"}
                      </span>
                    </div>
                    <div>
                      <span className="text-zinc-600 uppercase block text-[8px] font-sans font-bold tracking-wider">Observations</span>
                      <span className="text-zinc-400 font-semibold">12,450 rows</span>
                    </div>
                  </div>

                  <button
                    onClick={() => openRightPanel("discovery", finding)}
                    className="flex items-center gap-1 text-[9px] font-mono text-zinc-500 hover:text-emerald-400 group-hover:text-emerald-400 transition cursor-pointer"
                  >
                    <span>Investigate</span>
                    <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center py-20 text-zinc-600 font-mono text-xs border border-dashed border-zinc-800 rounded-lg">
          No discoveries found matching the selected filter.
        </div>
      )}
    </div>
  );
};
