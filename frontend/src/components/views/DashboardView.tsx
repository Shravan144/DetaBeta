"use client";

import React, { useState } from "react";
import { useWorkspace } from "@/context/WorkspaceContext";
import { Plus, Trash2, Calendar, FileSpreadsheet, Loader2 } from "lucide-react";
import { useSession } from "next-auth/react";

export const DashboardView: React.FC = () => {
  const { projects, selectProject, createProject, deleteProject } = useWorkspace();
  const { data: authSession } = useSession();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    try {
      await createProject(name.trim(), description.trim());
      setName("");
      setDescription("");
      setShowCreateModal(false);
    } catch {
      // The workspace toast contains the backend validation message.
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8 py-4">
      {/* Dashboard Greeting Header */}
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">
            {`Good ${new Date().getHours() < 12 ? "morning" : new Date().getHours() < 17 ? "afternoon" : "evening"}, ${authSession?.user?.name || "Researcher"}`}
          </h1>
          <p className="text-xs text-zinc-500 mt-1">
            Welcome to DetaBeta. Choose an existing experiment launcher or start a scientific analysis.
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-1.5 px-4 py-2 rounded bg-emerald-500 hover:bg-emerald-600 text-zinc-950 text-xs font-semibold shadow transition cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>New Experiment</span>
        </button>
      </div>

      {/* Projects Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {/* + Create Project Quick Card */}
        <div
          onClick={() => setShowCreateModal(true)}
          className="group relative flex flex-col justify-center items-center p-8 bg-zinc-900/30 hover:bg-zinc-900/60 border border-dashed border-zinc-800 hover:border-emerald-500/40 rounded-lg cursor-pointer transition-all duration-300 min-h-[180px]"
        >
          <div className="w-10 h-10 rounded-full bg-zinc-900 group-hover:bg-emerald-950/40 border border-zinc-800 group-hover:border-emerald-800/40 flex items-center justify-center text-zinc-400 group-hover:text-emerald-400 transition-all duration-300">
            <Plus className="w-5 h-5" />
          </div>
          <span className="text-xs font-semibold text-zinc-400 group-hover:text-zinc-200 mt-3 transition">
            Create new experiment
          </span>
          <span className="text-[10px] text-zinc-600 mt-1">Initialize workspace container</span>
        </div>

        {/* Existing Projects List */}
        {projects.map((project) => (
          <div
            key={project.id}
            className="group relative bg-[#18181b]/60 border border-zinc-800/80 hover:border-zinc-700/80 rounded-lg p-5 flex flex-col justify-between hover:shadow-xl transition-all duration-300 min-h-[180px]"
          >
            {/* Project Header */}
            <div>
              <div className="flex justify-between items-start gap-2">
                <h3
                  onClick={() => selectProject(project.id)}
                  className="font-semibold text-sm text-zinc-200 group-hover:text-emerald-400 transition cursor-pointer truncate"
                >
                  {project.name}
                </h3>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm(`Are you sure you want to delete project "${project.name}"?`)) {
                      deleteProject(project.id);
                    }
                  }}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:bg-zinc-800 text-zinc-500 hover:text-rose-400 rounded transition duration-250 cursor-pointer"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
              <p
                onClick={() => selectProject(project.id)}
                className="text-[11px] text-zinc-500 mt-1.5 line-clamp-2 leading-relaxed cursor-pointer"
              >
                {project.description || "No description provided."}
              </p>
            </div>

            {/* Project Footer Metrics */}
            <div
              onClick={() => selectProject(project.id)}
              className="mt-6 border-t border-zinc-850 pt-3 flex items-center justify-between text-[10px] text-zinc-500 font-mono cursor-pointer"
            >
              <div className="flex items-center gap-1">
                <FileSpreadsheet className="w-3.5 h-3.5 text-zinc-600" />
                <span>
                  {project.dataset_count} dataset{project.dataset_count === 1 ? "" : "s"}
                </span>
              </div>
              <div className="flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5 text-zinc-600" />
                <span>{new Date(project.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Create Project Modal Dialog */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg w-full max-w-md p-6 shadow-2xl space-y-4">
            <div>
              <h2 className="text-md font-semibold text-zinc-100">Create New Experiment Workspace</h2>
              <p className="text-[11px] text-zinc-500 mt-1">
                A container workspace holds datasets, cleaning steps, and model trials.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold uppercase tracking-wider text-zinc-400 block">
                  Project Name
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Customer Churn Analysis"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-850 rounded px-3 py-2 text-xs text-zinc-200 placeholder-zinc-650 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold uppercase tracking-wider text-zinc-400 block">
                  Description (optional)
                </label>
                <textarea
                  rows={3}
                  placeholder="Describe your research goals, variables, or hypothese..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-850 rounded px-3 py-2 text-xs text-zinc-200 placeholder-zinc-650 focus:outline-none focus:border-emerald-500 resize-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 text-xs font-semibold">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 border border-zinc-800 hover:bg-zinc-805 rounded text-zinc-400 transition cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading || !name.trim()}
                  className="flex items-center gap-1.5 px-4 py-2 bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-zinc-950 rounded transition cursor-pointer"
                >
                  {loading && <Loader2 className="w-3 h-3 animate-spin" />}
                  <span>Create Workspace</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
