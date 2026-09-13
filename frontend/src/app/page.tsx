"use client";

import React from "react";
import { useWorkspace } from "@/context/WorkspaceContext";
import { Sidebar } from "@/components/Sidebar";
import { TopBar } from "@/components/TopBar";
import { RightPanel } from "@/components/RightPanel";

// Views
import { DashboardView } from "@/components/views/DashboardView";
import { OverviewView } from "@/components/views/OverviewView";
import { DatasetView } from "@/components/views/DatasetView";
import { DiagnosticsView } from "@/components/views/DiagnosticsView";
import { InvestigationView } from "@/components/views/InvestigationView";
import { FeatureLabView } from "@/components/views/FeatureLabView";
import { ExperimentStudioView } from "@/components/views/ExperimentStudioView";
import { ExplainabilityView } from "@/components/views/ExplainabilityView";
import { ReportsView } from "@/components/views/ReportsView";

import {
  Upload,
  Activity,
  Search,
  Sliders,
  Cpu,
  BrainCircuit,
  Sparkles,
  ArrowRight,
} from "lucide-react";

export default function Home() {
  const { activeTab, setActiveTab, toast, selectedProjectId, createProject, selectProject } = useWorkspace();

  const handleStartInvestigation = () => {
    if (selectedProjectId) {
      setActiveTab("overview");
    } else {
      setActiveTab("dashboard");
    }
  };

  const handleExploreDemo = async () => {
    try {
      // 1. Create a demo Titanic project
      const demoProj = await createProject(
        "Titanic Survival Study (Demo)",
        "Scientific investigation of survival factors on the Titanic using demographics, fares, and class indicators."
      );
      
      // Select the project
      await selectProject(demoProj.id);
      
      // Let the user upload a file or simulate it by switching to overview
      setActiveTab("overview");
    } catch {
      setActiveTab("dashboard");
    }
  };

  // Render Landing Page
  if (activeTab === "landing") {
    return (
      <main className="relative min-h-screen bg-[#09090b] flex flex-col justify-between overflow-hidden select-none">
        {/* Ambient glow backgrounds */}
        <div className="absolute top-[-10%] left-[-10%] w-[500px] h-[500px] rounded-full bg-emerald-500/5 blur-[120px] pointer-events-none" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[500px] h-[500px] rounded-full bg-emerald-500/5 blur-[120px] pointer-events-none" />

        {/* Top Header Logo */}
        <header className="h-16 flex items-center justify-between px-8 md:px-16 border-b border-zinc-900 z-10">
          <div className="flex items-center gap-2 font-semibold tracking-wider text-sm text-zinc-100">
            <div className="w-5 h-5 rounded bg-emerald-500 flex items-center justify-center text-zinc-950 font-black text-xs">
              Δ
            </div>
            <span>DETABETA</span>
          </div>
          <span className="text-[10px] uppercase font-mono tracking-widest text-zinc-500 border border-zinc-800 px-3 py-1 rounded-full">
            Laboratory v0.1
          </span>
        </header>

        {/* Hero Section */}
        <div className="flex-1 flex flex-col justify-center items-center px-4 max-w-4xl mx-auto text-center space-y-8 z-10 py-16">
          <div className="space-y-4">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-950/40 border border-emerald-900/30 text-[10px] font-semibold text-emerald-450 tracking-wide uppercase font-mono">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Interactive Data Science Workspace</span>
            </span>
            <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-zinc-100 max-w-2xl mx-auto leading-[1.15]">
              Understand your data. <br className="hidden sm:inline" />
              <span className="bg-gradient-to-r from-emerald-400 via-emerald-500 to-teal-500 bg-clip-text text-transparent">
                Don&apos;t just process it.
              </span>
            </h1>
            <p className="text-xs sm:text-sm text-zinc-400 max-w-xl mx-auto leading-relaxed font-serif">
              DetaBeta is an interactive data science laboratory for investigating datasets, validating evidence, engineering features, and experimenting with machine learning.
            </p>
          </div>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row gap-3 justify-center items-center text-xs font-semibold">
            <button
              onClick={handleStartInvestigation}
              className="flex items-center gap-1.5 px-6 py-3 bg-emerald-500 hover:bg-emerald-600 text-zinc-950 rounded-lg shadow-lg hover:shadow-emerald-500/10 hover:scale-[1.02] transition duration-300 w-full sm:w-auto cursor-pointer"
            >
              <span>Start an Investigation</span>
              <ArrowRight className="w-4 h-4" />
            </button>
            <button
              onClick={handleExploreDemo}
              className="px-6 py-3 border border-zinc-800 hover:bg-zinc-900 rounded-lg text-zinc-300 transition duration-300 w-full sm:w-auto cursor-pointer"
            >
              Explore Demo Dataset
            </button>
          </div>

          {/* Process Workflow Visual Stepper */}
          <div className="w-full pt-16 grid grid-cols-2 md:grid-cols-6 gap-4">
            {[
              { step: "01", icon: <Upload className="w-4 h-4" />, label: "Upload", desc: "Validate CSV bytes" },
              { step: "02", icon: <Activity className="w-4 h-4" />, label: "Diagnose", desc: "Compute health score" },
              { step: "03", icon: <Search className="w-4 h-4" />, label: "Investigate", desc: "Discover patterns" },
              { step: "04", icon: <Sliders className="w-4 h-4" />, label: "Engineer", desc: "Recommend transforms" },
              { step: "05", icon: <Cpu className="w-4 h-4" />, label: "Experiment", desc: "Compare baselines" },
              { step: "06", icon: <BrainCircuit className="w-4 h-4" />, label: "Explain", desc: "Waterfall Shap logs" },
            ].map((step, idx) => (
              <div
                key={step.step}
                className="bg-[#18181b]/30 border border-zinc-850 p-4 rounded-lg flex flex-col items-center text-center space-y-2 relative"
              >
                {idx < 5 && (
                  <div className="hidden md:block absolute right-[-10px] top-1/2 -translate-y-1/2 text-zinc-800 z-0">
                    →
                  </div>
                )}
                <span className="text-[9px] font-bold font-mono text-zinc-650 bg-[#0f0f11] border border-zinc-900 px-1.5 py-0.5 rounded">
                  {step.step}
                </span>
                <div className="w-8 h-8 rounded-full bg-zinc-900 border border-zinc-850 flex items-center justify-center text-emerald-450">
                  {step.icon}
                </div>
                <div>
                  <span className="text-[11px] font-semibold text-zinc-300 block">{step.label}</span>
                  <span className="text-[9px] text-zinc-650 mt-0.5 block leading-tight">{step.desc}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <footer className="h-14 border-t border-zinc-900 flex items-center justify-center text-[10px] text-zinc-600 font-mono">
          © {new Date().getFullYear()} DetaBeta Studio. Premium Data Science Laboratory.
        </footer>
      </main>
    );
  }

  // Render main Workspace Shell
  const renderWorkspaceView = () => {
    switch (activeTab) {
      case "dashboard":
        return <DashboardView />;
      case "overview":
        return <OverviewView />;
      case "dataset":
        return <DatasetView />;
      case "diagnostics":
        return <DiagnosticsView />;
      case "investigation":
        return <InvestigationView />;
      case "feature-lab":
        return <FeatureLabView />;
      case "experiment":
        return <ExperimentStudioView />;
      case "explain":
        return <ExplainabilityView />;
      case "report":
        return <ReportsView />;
      default:
        return <div className="text-zinc-500 font-mono text-xs">{`View "${activeTab}" is not registered.`}</div>;
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-zinc-950 text-zinc-100 font-sans">
      {/* Collapsible Left Sidebar */}
      <Sidebar />

      {/* Main Workspace Frame */}
      <div className="flex-1 flex flex-col h-full overflow-hidden relative">
        {/* Context Top Bar */}
        <TopBar />

        {/* Core Canvas View */}
        <main className="flex-1 overflow-y-auto px-8 py-6 relative z-0">
          <div className="max-w-5xl mx-auto h-full">{renderWorkspaceView()}</div>
        </main>
      </div>

      {/* Unified Right Inspector Context Panel */}
      <RightPanel />

      {/* Toast Alert overlay */}
      {toast.type && (
        <div
          role="alert"
          className={`fixed bottom-6 right-6 px-4 py-3 rounded-lg border text-xs font-semibold shadow-2xl z-50 flex items-center gap-2 animate-bounce ${
            toast.type === "success"
              ? "bg-emerald-950 text-emerald-400 border-emerald-900"
              : "bg-rose-950 text-rose-450 border-rose-900"
          }`}
        >
          <div className={`w-2 h-2 rounded-full ${toast.type === "success" ? "bg-emerald-450" : "bg-rose-500"}`} />
          <span>{toast.message}</span>
        </div>
      )}
    </div>
  );
}
