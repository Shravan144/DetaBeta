"use client";

import React, { useEffect } from "react";
import { X } from "lucide-react";

export type HelpPanelKind = "documentation" | "settings";

export const HelpPanel: React.FC<{ kind: HelpPanelKind; onClose: () => void }> = ({ kind, onClose }) => {
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  const documentation = kind === "documentation";
  return (
    <div role="dialog" aria-modal="true" aria-label={documentation ? "Documentation" : "Workspace settings"} className="fixed inset-0 z-50 bg-black/60 flex justify-end">
      <section className="h-full w-full max-w-md bg-[#0f0f11] border-l border-zinc-800 p-6 overflow-y-auto">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
          <h2 className="text-lg font-semibold text-zinc-100">{documentation ? "DetaBeta guide" : "Workspace settings"}</h2>
          <button onClick={onClose} aria-label="Close panel" className="p-2 rounded text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100"><X className="w-4 h-4" /></button>
        </div>
        {documentation ? (
          <div className="mt-6 space-y-5 text-sm text-zinc-400 leading-relaxed">
            <p><strong className="text-zinc-200">1. Upload</strong><br />Create a project, then add a CSV up to 25 MB.</p>
            <p><strong className="text-zinc-200">2. Inspect</strong><br />Review Dataset Explorer, Diagnostics, and Investigation before modelling.</p>
            <p><strong className="text-zinc-200">3. Prepare</strong><br />Feature Lab suggestions create a new dataset version and never overwrite the original upload.</p>
            <p><strong className="text-zinc-200">4. Model and report</strong><br />Choose one target in Experiment Studio; Explainability and Reports use the same selection.</p>
          </div>
        ) : (
          <div className="mt-6 space-y-5 text-sm text-zinc-400 leading-relaxed">
            <p><strong className="text-zinc-200">Workspace persistence</strong><br />Projects, datasets, analysis sessions, and cached results are restored for your signed-in account.</p>
            <p><strong className="text-zinc-200">Data safety</strong><br />CSV files are private and can be deleted from the Dashboard when no longer needed.</p>
            <p><strong className="text-zinc-200">Connection</strong><br />Your deployment connection is managed securely by DetaBeta. API secrets are never shown in this panel.</p>
          </div>
        )}
      </section>
    </div>
  );
};
