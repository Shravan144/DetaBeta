"use client";

import React, { useState } from "react";
import { useWorkspace, TabName } from "@/context/WorkspaceContext";
import {
  Compass,
  Database,
  Activity,
  Search,
  Sliders,
  Cpu,
  HelpCircle,
  FileText,
  Settings,
  ChevronLeft,
  ChevronRight,
  LayoutDashboard,
  BrainCircuit,
} from "lucide-react";

interface NavItemProps {
  tab: TabName;
  icon: React.ReactNode;
  label: string;
  badge?: string | number;
  disabled?: boolean;
}

export const Sidebar: React.FC = () => {
  const { activeTab, setActiveTab, selectedProjectId, selectedDatasetId, selectProject } = useWorkspace();
  const [isCollapsed, setIsCollapsed] = useState(false);

  const navItems: { category: string; items: NavItemProps[] }[] = [
    {
      category: "General",
      items: [
        { tab: "overview", icon: <Compass className="w-4 h-4" />, label: "Overview", disabled: !selectedProjectId },
      ],
    },
    {
      category: "Data",
      items: [
        { tab: "dataset", icon: <Database className="w-4 h-4" />, label: "Dataset Explorer", disabled: !selectedProjectId },
        { tab: "diagnostics", icon: <Activity className="w-4 h-4" />, label: "Data Diagnostics", disabled: !selectedProjectId },
        { tab: "investigation", icon: <Search className="w-4 h-4" />, label: "Investigation", disabled: !selectedProjectId },
      ],
    },
    {
      category: "Lab",
      items: [
        { tab: "feature-lab", icon: <Sliders className="w-4 h-4" />, label: "Feature Lab", disabled: !selectedProjectId },
        { tab: "experiment", icon: <Cpu className="w-4 h-4" />, label: "Experiment Studio", disabled: !selectedProjectId || !selectedDatasetId },
        { tab: "explain", icon: <BrainCircuit className="w-4 h-4" />, label: "Explainability", disabled: !selectedProjectId || !selectedDatasetId },
      ],
    },
    {
      category: "Output",
      items: [
        { tab: "report", icon: <FileText className="w-4 h-4" />, label: "Research Reports", disabled: !selectedProjectId },
      ],
    },
  ];

  const handleNavClick = (item: NavItemProps) => {
    if (item.disabled) return;
    setActiveTab(item.tab);
  };

  if (activeTab === "landing") return null;

  return (
    <aside
      className={`relative h-screen bg-[#0f0f11] border-r border-zinc-800 transition-all duration-300 flex flex-col justify-between z-20 ${
        isCollapsed ? "w-16" : "w-64"
      }`}
    >
      <div>
        {/* Sidebar Header */}
        <div className="h-14 flex items-center justify-between px-4 border-b border-zinc-800">
          {!isCollapsed && (
            <button
              onClick={() => selectProject(null)}
              className="flex items-center gap-2 font-semibold tracking-wider text-sm text-zinc-100 hover:text-emerald-400 transition"
            >
              <div className="w-5 h-5 rounded bg-emerald-500 flex items-center justify-center text-zinc-950 font-black text-xs">
                Δ
              </div>
              <span>DETABETA</span>
            </button>
          )}
          {isCollapsed && (
            <button
              onClick={() => selectProject(null)}
              className="w-8 h-8 rounded bg-emerald-500 flex items-center justify-center text-zinc-950 font-black text-sm mx-auto hover:scale-105 transition"
            >
              Δ
            </button>
          )}
          
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="p-1.5 hover:bg-zinc-800 rounded text-zinc-400 hover:text-zinc-100 transition hidden md:block"
          >
            {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>

        {/* Navigation Categories */}
        <nav className="p-3 space-y-6 overflow-y-auto max-h-[calc(100vh-140px)]">
          {/* Dashboard Shortcut */}
          <button
            onClick={() => selectProject(null)}
            className={`w-full flex items-center gap-3 px-3 py-2 text-xs font-medium rounded transition ${
              isCollapsed ? "justify-center" : ""
            } text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100`}
          >
            <LayoutDashboard className="w-4 h-4 text-zinc-500" />
            {!isCollapsed && <span>Dashboard</span>}
          </button>

          {navItems.map((cat) => (
            <div key={cat.category} className="space-y-1">
              {!isCollapsed && (
                <div className="px-3 text-[10px] uppercase font-bold tracking-wider text-zinc-600">
                  {cat.category}
                </div>
              )}
              <div className="space-y-[2px]">
                {cat.items.map((item) => {
                  const isActive = activeTab === item.tab;
                  return (
                    <button
                      key={item.tab}
                      disabled={item.disabled}
                      onClick={() => handleNavClick(item)}
                      className={`w-full flex items-center gap-3 px-3 py-2 text-xs font-medium rounded transition group relative ${
                        isCollapsed ? "justify-center" : ""
                      } ${
                        isActive
                          ? "bg-emerald-950/40 text-emerald-400 border border-emerald-900/30"
                          : item.disabled
                          ? "opacity-35 cursor-not-allowed text-zinc-500"
                          : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100"
                      }`}
                    >
                      <div className={isActive ? "text-emerald-400" : "text-zinc-500 group-hover:text-zinc-300"}>
                        {item.icon}
                      </div>
                      {!isCollapsed && <span className="truncate">{item.label}</span>}
                      
                      {/* Collapsed Tooltip */}
                      {isCollapsed && (
                        <div className="absolute left-14 bg-zinc-950 border border-zinc-800 text-zinc-200 text-[10px] px-2 py-1 rounded opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto transition-opacity whitespace-nowrap shadow-xl z-50">
                          {item.label} {item.disabled && "(Requires selected dataset)"}
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
      </div>

      {/* Sidebar Footer */}
      <div className="p-3 border-t border-zinc-800 space-y-1">
        <button
          className={`w-full flex items-center gap-3 px-3 py-2 text-xs font-medium text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100 rounded transition ${
            isCollapsed ? "justify-center" : ""
          }`}
        >
          <HelpCircle className="w-4 h-4 text-zinc-500" />
          {!isCollapsed && <span>Documentation</span>}
        </button>
        <button
          className={`w-full flex items-center gap-3 px-3 py-2 text-xs font-medium text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100 rounded transition ${
            isCollapsed ? "justify-center" : ""
          }`}
        >
          <Settings className="w-4 h-4 text-zinc-500" />
          {!isCollapsed && <span>Settings</span>}
        </button>
      </div>
    </aside>
  );
};
