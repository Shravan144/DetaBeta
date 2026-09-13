"use client";

import React, { useState, useEffect } from "react";
import { useWorkspace } from "@/context/WorkspaceContext";
import { Loader2, FileDown, FileText, FileCode, BookOpen } from "lucide-react";
import { getBackendToken } from "@/lib/backend-token";

type ReportSection = {
  key: string;
  title: string;
  headline: string;
  body?: string[];
  key_points?: string[];
};

type ResearchReport = {
  title?: string;
  dataset_name?: string;
  executive_summary?: string[];
  sections?: ReportSection[];
  caveats?: string[];
  next_steps?: string[];
};

export const ReportsView: React.FC = () => {
  const { selectedDatasetId, runAnalysis, apiBase, apiFetch, showToast } = useWorkspace();
  
  const [columns, setColumns] = useState<string[]>([]);
  const [target, setTarget] = useState("");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<ResearchReport | null>(null);
  const [exporting, setExporting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Load columns to set default target
  useEffect(() => {
    if (!selectedDatasetId) return;

    let cancelled = false;
    async function loadColumns() {
      try {
        const preview = await apiFetch<{ columns?: string[] }>(`/datasets/${selectedDatasetId}/preview`);
        if (!cancelled) {
          const nextColumns = preview.columns ?? [];
          setColumns(nextColumns);
          const defaultTgt = nextColumns.find((column) =>
            column.toLowerCase() === "survived" || column.toLowerCase() === "churn"
          );
          if (defaultTgt) setTarget(defaultTgt);
        }
      } catch (requestError) {
        if (!cancelled) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Dataset columns could not be loaded."
          );
        }
      }
    }

    void loadColumns();
    return () => { cancelled = true; };
  }, [apiFetch, selectedDatasetId]);

  const handleGenerateReport = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await runAnalysis("report", target || undefined);
      setReport(data as ResearchReport);
      showToast("Composed complete Research Report successfully.");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The report could not be composed."
      );
    } finally {
      setLoading(false);
    }
  };

  // Build the export URL for the current dataset/target and a given format.
  const exportUrl = (format: "html" | "md" | "print") => {
    const base = apiBase.replace(/\/$/, "");
    const params = new URLSearchParams({ format });
    if (target) params.set("target", target);
    return `${base}/datasets/${selectedDatasetId}/analysis/report/export?${params.toString()}`;
  };

  // Download an HTML or Markdown file by fetching it as a blob.
  const handleDownload = async (format: "html" | "md") => {
    setExporting(format);
    try {
      const token = await getBackendToken();
      const res = await fetch(exportUrl(format), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      // Prefer the server-provided filename from Content-Disposition.
      const disp = res.headers.get("content-disposition") || "";
      const match = disp.match(/filename="?([^"]+)"?/);
      const filename = match?.[1] || `detabeta_report.${format}`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      showToast(`Exported report as ${format.toUpperCase()}.`);
    } catch {
      showToast("Could not export the report.", "error");
    } finally {
      setExporting(null);
    }
  };

  // PDF export: open the print-optimized page in a new tab; it auto-opens the
  // browser print dialog, where the user picks "Save as PDF". No PDF library
  // is needed on the server, which keeps the free serverless tier happy.
  const handleExportPdf = async () => {
    if (typeof window === "undefined") return;
    const printWindow = window.open("", "_blank");
    if (!printWindow) {
      showToast("Allow pop-ups to open the printable report.", "error");
      return;
    }
    printWindow.opener = null;
    printWindow.document.title = "Preparing DetaBeta report...";
    printWindow.document.body.textContent = "Preparing printable report...";
    setExporting("print");
    try {
      const token = await getBackendToken();
      const response = await fetch(exportUrl("print"), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error("Print export failed");
      const blobUrl = URL.createObjectURL(await response.blob());
      printWindow.location.replace(blobUrl);
      window.setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
    } catch {
      printWindow.close();
      showToast("Could not open the printable report.", "error");
    } finally {
      setExporting(null);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex flex-col justify-center items-center min-h-[300px]">
        <Loader2 className="w-8 h-8 text-emerald-400 animate-spin" />
        <span className="text-xs text-zinc-500 mt-3 font-mono">Composing complete scientific data story report...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6 py-4">
      {/* Title */}
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">Research Reports</h1>
          <p className="text-xs text-zinc-500 mt-1">
            Generate a single narrative, top-to-bottom scientific argument combining all analysis engine findings.
          </p>
        </div>

        {report && (
          <div className="flex gap-2 print:hidden">
            <button
              onClick={() => handleDownload("html")}
              disabled={exporting !== null}
              className="flex items-center gap-1.5 px-3.5 py-1.5 border border-zinc-800 hover:bg-zinc-850 disabled:opacity-50 rounded text-zinc-300 text-[10px] font-semibold transition cursor-pointer"
            >
              {exporting === "html" ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <FileCode className="w-3.5 h-3.5" />
              )}
              <span>HTML</span>
            </button>
            <button
              onClick={() => void handleExportPdf()}
              disabled={exporting !== null}
              className="flex items-center gap-1.5 px-3.5 py-1.5 border border-zinc-800 hover:bg-zinc-850 disabled:opacity-50 rounded text-zinc-300 text-[10px] font-semibold transition cursor-pointer"
            >
              <FileDown className="w-3.5 h-3.5" />
              <span>PDF</span>
            </button>
            <button
              onClick={() => handleDownload("md")}
              disabled={exporting !== null}
              className="flex items-center gap-1.5 px-3.5 py-1.5 border border-zinc-800 hover:bg-zinc-850 disabled:opacity-50 rounded text-zinc-300 text-[10px] font-semibold transition cursor-pointer"
            >
              {exporting === "md" ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <FileText className="w-3.5 h-3.5" />
              )}
              <span>Markdown</span>
            </button>
          </div>
        )}
      </div>

      {/* Target config & generate buttons */}
      {!report && (
        <div className="p-8 bg-zinc-900/30 border border-zinc-800 rounded-xl max-w-xl mx-auto flex flex-col items-center text-center space-y-6">
          <BookOpen className="w-10 h-10 text-emerald-500" />
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-zinc-200">Compose Complete Narrative</h3>
            <p className="text-xs text-zinc-500 max-w-xs">
              This gathers profiles, health issues, statistical correlations, ML leaderboard results, and explainability factors into a formal report.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <label className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">
              Optional Target:
            </label>
            <select
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              className="bg-zinc-950 border border-zinc-850 rounded px-2.5 py-1.5 text-xs text-zinc-200 focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer w-48 font-mono"
            >
              <option value="">No Target</option>
              {columns.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={handleGenerateReport}
            className="flex items-center gap-1.5 px-6 py-2.5 bg-emerald-500 hover:bg-emerald-600 text-zinc-950 text-xs font-semibold rounded shadow transition cursor-pointer"
          >
            <span>Compose Research Report</span>
          </button>

          {error && (
            <div role="alert" className="w-full rounded-lg border border-rose-900/40 bg-rose-950/10 p-3 text-left text-xs text-rose-200">
              <p className="font-semibold">Report unavailable</p>
              <p className="mt-1 text-rose-200/80 leading-relaxed">{error}</p>
              <button
                onClick={handleGenerateReport}
                className="mt-3 text-[10px] font-semibold text-emerald-300 hover:text-emerald-200"
              >
                Try Again
              </button>
            </div>
          )}
        </div>
      )}

      {/* Narrative Report View */}
      {report && (
        <article className="max-w-3xl mx-auto bg-zinc-900/10 border border-zinc-800 rounded-xl p-8 space-y-8 shadow-2xl overflow-hidden print:border-0 print:bg-white print:text-zinc-950 print:p-0">
          {/* Report Header */}
          <div className="border-b border-zinc-800 print:border-zinc-300 pb-6 text-center space-y-2">
            <span className="text-[10px] tracking-widest text-emerald-400 font-bold uppercase font-mono print:text-emerald-600">
              DetaBeta Research Report
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-zinc-100 print:text-zinc-950 capitalize">
              {report.title || "Dataset Narrative Report"}
            </h1>
            <div className="text-[10px] text-zinc-500 font-mono">
              Dataset: {report.dataset_name} · Generated: {new Date().toLocaleDateString()}
            </div>
          </div>

          {/* Executive Summary */}
          {report.executive_summary && report.executive_summary.length > 0 && (
            <div className="space-y-3 bg-[#18181b]/30 p-5 rounded-lg border border-zinc-850 print:bg-zinc-100 print:border-zinc-300">
              <h2 className="text-xs font-bold uppercase tracking-wider text-emerald-400 print:text-emerald-600">
                Executive Summary
              </h2>
              <div className="text-xs text-zinc-300 print:text-zinc-800 leading-relaxed space-y-2">
                {report.executive_summary.map((para: string, idx: number) => (
                  <p key={idx}>{para}</p>
                ))}
              </div>
            </div>
          )}

          {/* Chapters loop */}
          <div className="space-y-8">
            {report.sections?.map((sec, idx) => (
              <section key={sec.key} className="space-y-3 border-t border-zinc-850/60 print:border-zinc-200 pt-6">
                <div className="flex gap-2.5 items-center">
                  <span className="text-[10px] font-mono font-bold text-zinc-650 bg-[#0f0f11] border border-zinc-850 px-2 py-0.5 rounded print:border-zinc-300">
                    Chapter 0{idx + 1}
                  </span>
                  <h3 className="text-sm font-semibold text-zinc-200 print:text-zinc-900">
                    {sec.title}
                  </h3>
                </div>

                <div className="pl-0 sm:pl-10 space-y-3">
                  {/* Takeaway headline */}
                  <blockquote className="border-l-2 border-emerald-500 pl-3 italic text-xs text-zinc-300 print:text-zinc-800">
                    &quot;{sec.headline}&quot;
                  </blockquote>

                  {/* Body description */}
                  <div className="text-xs text-zinc-400 print:text-zinc-700 leading-relaxed space-y-2">
                    {sec.body?.map((para: string, pIdx: number) => (
                      <p key={pIdx}>{para}</p>
                    ))}
                  </div>

                  {/* Key points bullets */}
                  {sec.key_points && sec.key_points.length > 0 && (
                    <div className="space-y-1.5 pt-2">
                      {sec.key_points.map((pt: string, ptIdx: number) => (
                        <div key={ptIdx} className="flex gap-2 items-start text-[11px] text-zinc-450 print:text-zinc-605">
                          <span className="text-emerald-500 font-bold">•</span>
                          <span>{pt}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </section>
            ))}
          </div>

          {/* Verdicts, Caveats, Next Steps */}
          <div className="border-t border-zinc-800 print:border-zinc-300 pt-6 grid grid-cols-1 md:grid-cols-2 gap-6 text-xs leading-relaxed">
            {/* Caveats */}
            {report.caveats && report.caveats.length > 0 && (
              <div className="space-y-2 p-4 bg-rose-950/10 border border-rose-950/30 rounded-lg print:border-zinc-300">
                <h4 className="font-bold text-rose-400 print:text-rose-600 uppercase tracking-wider text-[10px]">
                  Scientific Limitations
                </h4>
                <div className="space-y-1.5">
                  {report.caveats.map((c: string, idx: number) => (
                    <div key={idx} className="flex gap-2 items-start text-zinc-400 print:text-zinc-750">
                      <span className="text-rose-500 font-bold">•</span>
                      <span>{c}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Next Steps */}
            {report.next_steps && report.next_steps.length > 0 && (
              <div className="space-y-2 p-4 bg-emerald-950/10 border border-emerald-950/30 rounded-lg print:border-zinc-300">
                <h4 className="font-bold text-emerald-400 print:text-emerald-600 uppercase tracking-wider text-[10px]">
                  Prioritized Next Steps
                </h4>
                <div className="space-y-1.5">
                  {report.next_steps.map((ns: string, idx: number) => (
                    <div key={idx} className="flex gap-2 items-start text-zinc-400 print:text-zinc-750">
                      <span className="text-emerald-500 font-bold font-mono text-[10px]">{idx + 1}.</span>
                      <span>{ns}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          
          <div className="flex justify-center pt-4">
            <button
              onClick={() => setReport(null)}
              className="px-4 py-2 border border-zinc-800 hover:bg-zinc-850 rounded text-zinc-400 text-xs font-semibold transition cursor-pointer"
            >
              Compose New Report
            </button>
          </div>
        </article>
      )}
    </div>
  );
};
