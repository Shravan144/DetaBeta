# DetaBeta Production-Trust Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove placeholder production UI data and make DetaBeta's analysis workflow consistent, actionable, and verifiable.

**Architecture:** Keep FastAPI analysis engines as the source of truth and extend only their JSON payloads with optional evidence/preview fields. Centralize dataset-scoped target selection and profile lookup in the React workspace layer; views and side panels become faithful renderers of those results.

**Tech Stack:** FastAPI, pandas, SciPy, scikit-learn, pytest, Next.js 16, React 19, TypeScript, Recharts, Node test runner, ESLint.

**Spec:** `docs/superpowers/specs/2026-09-14-production-trust-pass.md`

## Global Constraints

- Never generate synthetic values, random charts, or hard-coded statistics in analysis UI.
- Preserve existing persisted JSON result compatibility; new fields are optional.
- Keep the configured frontend/backend upload limit at 25 MiB.
- Do not expose secrets or introduce user-editable backend configuration.
- Retain the existing visual style and CSV-only scope.

---

### Task 1: Real investigation evidence

**Files:**
- Modify: `backend/engines/investigation/types.py`
- Modify: `backend/engines/investigation/checks.py`
- Modify: `backend/engines/investigation/engine.py`
- Modify: `backend/tests/test_investigation.py`
- Modify: `frontend/src/components/views/InvestigationView.tsx`
- Modify: `frontend/src/components/RightPanel.tsx`

**Interfaces:**
- Produces `Finding.evidence` with real chart data and statistical metadata.
- Produces `Finding.n_observations: int`.

- [ ] Add failing backend assertions for real row counts and evidence fields.
- [ ] Run `pytest backend/tests/test_investigation.py -q` and observe failure.
- [ ] Populate row counts/evidence from pandas/SciPy results without altering finding semantics.
- [ ] Render the observation count and evidence fields in the frontend; remove all random and hard-coded values.
- [ ] Run the focused backend test and frontend lint.

### Task 2: Accurate feature-transform previews

**Files:**
- Modify: `backend/engines/feature_lab/types.py`
- Modify: `backend/engines/feature_lab/suggestions.py`
- Modify: `backend/tests/test_feature_lab.py`
- Modify: `frontend/src/components/RightPanel.tsx`

**Interfaces:**
- Produces `Recommendation.preview?: { kind, summary, before?, after? }`.

- [ ] Add failing tests for preview metadata for drop, one-hot, and binary-map recommendations.
- [ ] Implement recommendation-specific preview metadata.
- [ ] Render a factual summary by default and charts only for supplied histogram data.
- [ ] Run feature-lab tests and lint.

### Task 3: Valid diagnostics inspection

**Files:**
- Modify: `frontend/src/components/views/DiagnosticsView.tsx`
- Modify: `frontend/src/components/views/DatasetView.tsx`
- Create: `frontend/src/lib/column-profile.ts`
- Create: `frontend/src/lib/column-profile.test.ts`

**Interfaces:**
- `findColumnProfile(columns, name)` returns an exact profile or `undefined`.

- [ ] Add failing tests for finding a profile and rejecting a missing column.
- [ ] Implement the pure profile helper.
- [ ] Load/use the shared profile in Diagnostics before opening the inspector.
- [ ] Hide unavailable inspect actions; remove placeholder metadata.
- [ ] Run frontend tests and lint.

### Task 4: Dataset-scoped target selection and clear explanations

**Files:**
- Modify: `frontend/src/context/WorkspaceContext.tsx`
- Modify: `frontend/src/components/views/ExperimentStudioView.tsx`
- Modify: `frontend/src/components/views/ExplainabilityView.tsx`
- Modify: `frontend/src/components/views/ReportsView.tsx`
- Modify: `frontend/src/components/RightPanel.tsx`
- Create: `frontend/src/lib/target-selection.ts`
- Create: `frontend/src/lib/target-selection.test.ts`

**Interfaces:**
- `pickDefaultTarget(columns): string | null` chooses a label-like column.
- Workspace exposes `selectedTarget: string | null` and `setSelectedTarget(target)`.

- [ ] Add failing unit tests for target priority/preservation rules.
- [ ] Implement the pure target helper.
- [ ] Add shared target state and reset it upon dataset change.
- [ ] Make all modelling views consume the shared value without overwriting a user choice.
- [ ] Render zero probabilities and label classification probability explicitly.
- [ ] Run frontend tests, lint, and build.

### Task 5: Active product controls, upload validation, and stable view states

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx`
- Modify: `frontend/src/components/views/OverviewView.tsx`
- Modify: `frontend/src/context/WorkspaceContext.tsx`
- Create: `frontend/src/components/HelpPanel.tsx`
- Create: `frontend/src/lib/upload-validation.ts`
- Create: `frontend/src/lib/upload-validation.test.ts`
- Modify: relevant data views for initial loading/error reset.

**Interfaces:**
- `MAX_UPLOAD_BYTES = 25 * 1024 * 1024`.
- `validateCsvUpload(file)` returns an error message or `null`.

- [ ] Add failing validation tests for file type and 25 MiB boundary.
- [ ] Implement client-side validation and matching upload copy.
- [ ] Add a non-destructive help/settings panel with keyboard-close behavior.
- [ ] Reset stale reports before an async reload and offer retries after errors.
- [ ] Run frontend tests, lint, and build.

### Task 6: Full verification and deployment readiness

**Files:**
- Modify: `README.md`

- [ ] Run `python -m pytest -q -p no:cacheprovider backend/tests`.
- [ ] Run `npm.cmd --prefix frontend test`.
- [ ] Run `npm.cmd --prefix frontend run lint`.
- [ ] Run `npm.cmd --prefix frontend run build`.
- [ ] Update README verification/manual-smoke instructions.
- [ ] Commit the verified production-trust pass.
