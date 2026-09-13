"use client";

import React from "react";
import { useWorkspace } from "@/context/WorkspaceContext";
import { Play, FileDown, CheckCircle, AlertCircle, Loader2 } from "lucide-react";
import { LogOut } from "lucide-react";
import { useSession, signOut } from "next-auth/react";
import { clearBackendToken } from "@/lib/backend-token";
export const TopBar: React.FC = () => {
  const {
    activeTab,
    selectedProjectId,
    selectedDatasetId,
    selectedDataset,
    projects,
    datasets,
    selectProject,
    selectDataset,
    setActiveTab,
    session,
  } = useWorkspace();

  const { data: authSession } = useSession();

  const handleSignOut = () => {
    clearBackendToken();
    signOut();
  };

  if (activeTab === "landing") return null;

  const currentProject = projects.find((p) => p.id === selectedProjectId);

  const getStatusBadge = () => {
    switch (session.status) {
      case "running":
        return (
          <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded bg-amber-950 text-amber-400 border border-amber-900/30">
            <Loader2 className="w-3 h-3 animate-spin" />
            Analyzing
          </span>
        );
      case "completed":
        return (
          <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-900/30">
            <CheckCircle className="w-3 h-3" />
            Completed
          </span>
        );
      case "failed":
        return (
          <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded bg-rose-950 text-rose-400 border border-rose-900/30">
            <AlertCircle className="w-3 h-3" />
            Error
          </span>
        );
      default:
        return (
          <span className="text-[10px] px-2 py-0.5 rounded bg-zinc-900 text-zinc-400 border border-zinc-800">
            Idle
          </span>
        );
    }
  };

  return (
    <header className="h-14 border-b border-zinc-800 bg-[#09090b]/80 backdrop-blur-md flex items-center justify-between px-6 z-10 select-none">
      {/* Left side: Context Breadcrumbs */}
      <div className="flex items-center gap-2 text-xs text-zinc-400 font-medium">
        <button
          onClick={() => selectProject(null)}
          className="hover:text-zinc-100 transition text-zinc-500 hover:bg-zinc-900 px-2 py-1 rounded"
        >
          Launcher
        </button>

        {currentProject && (
          <>
            <span className="text-zinc-600">/</span>
            <button
              onClick={() => selectProject(currentProject.id)}
              className={`hover:text-zinc-100 transition px-2 py-1 rounded ${
                !selectedDatasetId ? "text-zinc-200" : "text-zinc-500"
              }`}
            >
              {currentProject.name}
            </button>
          </>
        )}

        {selectedDataset && (
          <>
            <span className="text-zinc-600">/</span>
            <select
              value={selectedDatasetId || ""}
              onChange={(e) => {
                const val = e.target.value;
                selectDataset(val ? Number(val) : null);
              }}
              className="bg-zinc-900 border border-zinc-800 text-zinc-200 px-2 py-1 rounded text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
            >
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
            
            <span className="text-zinc-600">/</span>
            <div className="flex items-center gap-2">
              <span className="text-zinc-200 font-semibold tracking-wider uppercase text-[10px] bg-zinc-900 px-2 py-1 border border-zinc-800 rounded">
                {session.id ? `Session #${session.id}` : "No session"}
              </span>
              {getStatusBadge()}
            </div>
          </>
        )}
      </div>

      {/* Right side: Top Bar Actions */}
      <div className="flex items-center gap-2">
        {selectedDataset && (
          <>
            <button
              onClick={() => setActiveTab("overview")}
              disabled={session.status === "running"}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-zinc-950 text-xs font-semibold shadow transition cursor-pointer"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Analysis Overview</span>
            </button>
            <button
              onClick={() => setActiveTab("report")}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded border border-zinc-800 hover:bg-zinc-900 text-zinc-300 text-xs font-semibold transition cursor-pointer"
            >
              <FileDown className="w-3.5 h-3.5" />
              <span>Export</span>
            </button>
          </>
        )}

        {/* User info + sign out */}
        {authSession?.user && (
          <div className="flex items-center gap-2 ml-3 pl-3 border-l border-zinc-800">
            <div className="text-right">
              <p className="text-[11px] font-medium text-zinc-300 leading-tight">
                {authSession.user.name || authSession.user.email}
              </p>
              {authSession.user.name && authSession.user.email && (
                <p className="text-[9px] text-zinc-500 leading-tight">
                  {authSession.user.email}
                </p>
              )}
            </div>
            {authSession.user.image ? (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src={authSession.user.image}
                alt=""
                className="w-7 h-7 rounded-full border border-zinc-700"
              />
            ) : (
              <div className="w-7 h-7 rounded-full bg-emerald-900 border border-emerald-800 flex items-center justify-center text-[10px] font-bold text-emerald-400">
                {(authSession.user.name || authSession.user.email || "U")[0].toUpperCase()}
              </div>
            )}
            <button
              onClick={handleSignOut}
              title="Sign out"
              className="p-1.5 rounded hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300 transition cursor-pointer"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>
    </header>
  );
};
