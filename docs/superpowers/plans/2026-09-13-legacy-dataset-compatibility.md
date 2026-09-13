# Legacy Dataset Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve old local datasets while moving active storage to Supabase and make Feature Lab/Reports fail cleanly.

**Architecture:** A dedicated migration command copies only legacy keys from the local store to Supabase and updates metadata atomically after each successful copy. Runtime storage errors are normalized by the dataset router. Frontend views own expected error rendering.

**Tech Stack:** FastAPI, SQLAlchemy, pandas, Supabase Storage, React/TypeScript, pytest.

**Spec:** `docs/superpowers/specs/2026-09-13-legacy-dataset-compatibility.md`

## Global Constraints

- Never delete local source files during migration.
- Do not reveal Supabase credentials or object-store exceptions to browser users.
- Keep raw datasets immutable; transforms create a new dataset version.
- Migration defaults to dry run and needs `--apply` to write.

---

### Task 1: Legacy-storage migration command

**Files:**
- Create: `backend/scripts/migrate_legacy_datasets.py`
- Test: `backend/tests/test_legacy_storage_migration.py`

**Interfaces:**
- Produces `migrate_legacy_datasets(db, source, destination, apply=False) -> MigrationSummary`.
- Consumes existing `Dataset.storage_path`, `LocalDatasetStorage`, and `SupabaseDatasetStorage` compatible adapters.

- [ ] **Step 1: Write failing tests** for dry-run no mutation, successful copy/path update, and failed copy retaining the original path.
- [ ] **Step 2: Run those tests** and verify they fail because the module does not exist.
- [ ] **Step 3: Implement** a typed summary and idempotent copy command; reject non-legacy keys and only commit metadata after upload succeeds.
- [ ] **Step 4: Run migration tests** and verify all pass.

### Task 2: Transform storage errors

**Files:**
- Modify: `backend/api/routers/datasets.py`
- Modify: `backend/tests/test_api.py`

**Interfaces:**
- `POST /datasets/{id}/apply-transform` returns 409 for legacy/missing source and 503 for a derived-object persistence failure.

- [ ] **Step 1: Write failing route tests** for save failure and legacy source failure.
- [ ] **Step 2: Run the focused tests** and verify the old route returns an unhandled 500.
- [ ] **Step 3: Implement** explicit exception boundaries around read/save with concise user-safe `detail` messages, retaining existing rollback/delete behaviour.
- [ ] **Step 4: Run focused transform tests** and verify all pass.

### Task 3: Feature Lab and Reports recovery states

**Files:**
- Modify: `frontend/src/components/views/FeatureLabView.tsx`
- Modify: `frontend/src/components/views/ReportsView.tsx`

**Interfaces:**
- Both views render a retryable inline error instead of only logging expected API failures.

- [ ] **Step 1: Add view-level `error` state** and clear it before each request.
- [ ] **Step 2: Render an accessible inline error panel** with the API message and a retry action.
- [ ] **Step 3: Remove expected-failure `console.error` calls** while keeping successful toast feedback.
- [ ] **Step 4: Run frontend lint and production build.**

### Task 4: Final verification

**Files:**
- Verify: backend tests, frontend lint/build

- [ ] **Step 1: Run migration, transform, and report-export tests.**
- [ ] **Step 2: Run `npm run lint` and `npm run build` in `frontend`.**
- [ ] **Step 3: Run the migration command in dry-run mode only** against the configured records; report candidates without applying writes.
