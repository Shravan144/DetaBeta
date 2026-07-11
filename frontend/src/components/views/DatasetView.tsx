"use client";

import React, { useState, useEffect } from "react";
import { useWorkspace } from "@/context/WorkspaceContext";
import { Search, Loader2, Sparkles, Filter, Info } from "lucide-react";

export const DatasetView: React.FC = () => {
  const { selectedDatasetId, apiBase, runAnalysis, openRightPanel } = useWorkspace();
  
  const [preview, setPreview] = useState<any>(null);
  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeSearchCol, setActiveSearchCol] = useState("");
  const [sortConfig, setSortConfig] = useState<{ key: string; direction: "asc" | "desc" | null }>({
    key: "",
    direction: null,
  });

  useEffect(() => {
    if (selectedDatasetId) {
      loadPreviewAndProfile();
    }
  }, [selectedDatasetId]);

  const loadPreviewAndProfile = async () => {
    setLoading(true);
    try {
      // 1. Fetch preview
      const res = await fetch(`${apiBase.replace(/\/$/, "")}/datasets/${selectedDatasetId}/preview`);
      if (res.ok) {
        const previewData = await res.json();
        setPreview(previewData);
      }
      
      // 2. Fetch understanding profile for columns metadata
      const profileData = await runAnalysis("understand");
      setProfile(profileData);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleHeaderClick = (colName: string) => {
    if (!profile?.columns) return;
    const colProfile = profile.columns.find((c: any) => c.name === colName);
    if (colProfile) {
      openRightPanel("column", colProfile);
    }
  };

  const handleSort = (colName: string) => {
    let direction: "asc" | "desc" | null = "asc";
    if (sortConfig.key === colName && sortConfig.direction === "asc") {
      direction = "desc";
    } else if (sortConfig.key === colName && sortConfig.direction === "desc") {
      direction = null;
    }
    setSortConfig({ key: direction ? colName : "", direction });
  };

  if (loading) {
    return (
      <div className="flex-1 flex flex-col justify-center items-center min-h-[300px]">
        <Loader2 className="w-8 h-8 text-emerald-400 animate-spin" />
        <span className="text-xs text-zinc-500 mt-3 font-mono">Loading dataset spreadsheet preview...</span>
      </div>
    );
  }

  if (!preview) {
    return (
      <div className="text-zinc-500 text-center py-20">
        No preview loaded. Please choose another dataset.
      </div>
    );
  }

  // Filter & Sort logic
  let filteredRows = [...(preview.rows || [])];

  if (searchQuery.trim() && activeSearchCol) {
    filteredRows = filteredRows.filter((row: any) => {
      const val = row[activeSearchCol];
      return String(val ?? "").toLowerCase().includes(searchQuery.toLowerCase());
    });
  }

  if (sortConfig.key && sortConfig.direction) {
    const { key, direction } = sortConfig;
    filteredRows.sort((a: any, b: any) => {
      const valA = a[key];
      const valB = b[key];
      if (typeof valA === "number" && typeof valB === "number") {
        return direction === "asc" ? valA - valB : valB - valA;
      }
      return direction === "asc"
        ? String(valA).localeCompare(String(valB))
        : String(valB).localeCompare(String(valA));
    });
  }

  return (
    <div className="space-y-6 py-4">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-zinc-100">Dataset Explorer</h1>
        <p className="text-xs text-zinc-500 mt-1">
          Interactive preview of your spreadsheet. Clicking column headers opens column-level summaries in the context panel.
        </p>
      </div>

      {/* Grid Controls (Search + Filters) */}
      <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between border-b border-zinc-850 pb-4">
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-zinc-600" />
            <input
              type="text"
              placeholder="Search values..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-zinc-900 border border-zinc-850 rounded-lg pl-8 pr-3 py-2 text-xs text-zinc-200 placeholder-zinc-650 w-full sm:w-60 focus:outline-none focus:border-emerald-500"
            />
          </div>

          <select
            value={activeSearchCol}
            onChange={(e) => {
              setActiveSearchCol(e.target.value);
              if (!e.target.value) setSearchQuery("");
            }}
            className="bg-zinc-900 border border-zinc-850 rounded-lg px-3 py-2 text-xs text-zinc-300 focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
          >
            <option value="">Choose Column</option>
            {preview.columns.map((c: string) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        <div className="text-[10px] text-zinc-500 font-mono flex items-center gap-1.5 bg-zinc-900/40 px-3 py-1.5 rounded-lg border border-zinc-850">
          <Info className="w-3.5 h-3.5 text-emerald-400" />
          <span>Click headers to inspect columns</span>
        </div>
      </div>

      {/* Spreadsheet Table Wrap */}
      <div className="border border-zinc-800 rounded-lg overflow-hidden bg-zinc-900/10">
        <div className="overflow-x-auto max-h-[50vh]">
          <table className="scientific-table w-full border-collapse">
            <thead>
              <tr className="bg-[#0f0f11] select-none">
                {preview.columns.map((colName: string) => {
                  const isSorted = sortConfig.key === colName;
                  const sortDir = sortConfig.direction;
                  
                  return (
                    <th key={colName} className="font-mono">
                      <div className="flex items-center justify-between gap-2">
                        <button
                          onClick={() => handleHeaderClick(colName)}
                          className="hover:text-emerald-400 font-bold transition text-left cursor-pointer flex-1 py-1"
                          title="Click to view column stats in side panel"
                        >
                          {colName}
                        </button>
                        <button
                          onClick={() => handleSort(colName)}
                          className={`p-1 hover:bg-zinc-800 text-zinc-650 hover:text-zinc-300 rounded transition cursor-pointer text-[9px]`}
                        >
                          {isSorted && sortDir === "asc" ? "▲" : isSorted && sortDir === "desc" ? "▼" : "⇅"}
                        </button>
                      </div>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {filteredRows.length > 0 ? (
                filteredRows.map((row: any, rowIdx: number) => (
                  <tr key={rowIdx} className="border-b border-zinc-850">
                    {preview.columns.map((colName: string) => {
                      const value = row[colName];
                      return (
                        <td key={colName} className="text-zinc-300 font-mono max-w-[150px]">
                          {value === null || value === undefined ? (
                            <span className="text-zinc-700 italic">null</span>
                          ) : (
                            String(value)
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={preview.columns.length} className="text-center py-10 text-zinc-600 font-mono text-xs">
                    No rows match current search criteria.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        
        {/* Table Footer */}
        <div className="bg-[#0f0f11] border-t border-zinc-800 px-4 py-3 flex items-center justify-between text-[10px] text-zinc-500 font-mono">
          <div>
            Showing {filteredRows.length} of {preview.n_rows} rows (spreadsheet preview mode)
          </div>
          <div>
            {preview.n_columns} columns total
          </div>
        </div>
      </div>
    </div>
  );
};
