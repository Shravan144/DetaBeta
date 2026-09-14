# DetaBeta Production-Trust Pass Design

## Goal

Make every visible analysis result in the deployed DetaBeta application honest,
dataset-specific, understandable, and actionable. Remove placeholder data from
production UI, make target selection consistent across modelling features, and
replace inactive controls with working in-app behavior.

## Scope

This pass covers the production issues observed during the `passengers_v2.csv`
smoke test:

1. Investigation cards and the context panel must use real finding evidence,
   statistics, chart values, and the selected dataset row count.
2. Feature Lab transformation previews must accurately describe the selected
   transform without presenting invented histogram output as real data.
3. Diagnostics "Inspect Evidence" must open a valid dataset-profile column
   record instead of an incomplete placeholder object.
4. Experiment Studio, Explainability, and Research Reports must share one
   selected predictive target per dataset during a browser visit.
5. Explainability must label class predictions and positive-class probabilities
   unambiguously, including a probability of exactly zero.
6. Upload messaging and browser-side validation must match the backend's
   configured 25 MiB limit.
7. Sidebar Documentation and Settings must open useful in-app panels rather
   than act like dead buttons.
8. Views must distinguish loading, empty, and request-failure states while a
   persisted workspace is being restored.

The existing dark visual language, Supabase persistence design, auth flow,
analysis engines, and report export formats remain unchanged.

## Design decisions

### 1. Real investigation evidence

The investigation engine already produces findings. Its response schema will
be extended only where needed to include:

- `n_observations`: number of rows analyzed for the finding;
- `evidence`: serializable chart-ready data and actual statistical fields;
- `test_name`, `test_statistic`, `p_value`, and `effect_size` when a finding
  has a formal statistical test.

The client will render a chart only when its matching real evidence is present.
When no chart is meaningful, it will show a concise evidence table rather than
generate synthetic points or values. The word "confidence" remains a finding
strength label, not a claim that an association is causal.

### 2. Truthful transform previews

Feature recommendations will provide transform-specific preview metadata:

- `drop_column`: removed columns and count of retained columns;
- `one_hot_encode`: generated feature names/categories;
- `map_binary`: source values and the resulting 0/1 mapping;
- numeric transforms: only display before/after distributions when actual
  histogram values are supplied by the engine.

The panel will use this metadata and recommendation reasoning. It will not
fabricate a "more symmetric" histogram for a drop or one-hot operation.

### 3. Reusable profile-backed column inspector

The frontend will introduce a small profile lookup helper. Dataset Explorer
and Diagnostics will both use the same profile record for a column. If a
diagnostic issue names a deleted/unavailable column, the button will be hidden
or disabled with a clear explanation instead of opening a broken inspector.

### 4. Dataset-scoped target selection

`WorkspaceContext` will own `selectedTarget` and `setSelectedTarget`.
On dataset selection it will clear the prior target. The first screen that has
available columns chooses a sensible label-like candidate only if no target is
already selected; it never overwrites a user choice. Experiment Studio,
Explainability, and Reports consume the same target state.

### 5. Clear explainability results

For classification, the UI will say:

`Predicted class: <label> · Probability of class <positive class>: <percent>`.

For regression it will show only the predicted numeric value. Checks use
`typeof value === "number"`, so `0%` renders correctly.

### 6. Product controls and upload limit

The browser enforces `25 * 1024 * 1024` bytes before sending the request and
shows "CSV files up to 25 MB". Documentation opens a concise workflow/help
panel; Settings opens an application-preferences panel for API connection and
workspace information. Neither panel exposes secrets or changes backend
configuration.

### 7. Loading and error states

Views reset stale state when `selectedDatasetId` changes, retain an explicit
`loading` state until the first request resolves, and offer a retry button on
request errors. Empty workspaces retain their existing upload entry point.

## Interfaces

### Frontend shared types

```ts
type SelectedTarget = string | null;

type FindingEvidence = {
  n_observations?: number;
  chart?: { kind: "bar" | "histogram"; data: Array<Record<string, string | number>> };
  test_name?: string;
  test_statistic?: number;
  p_value?: number;
  effect_size?: { label: string; value?: number };
};
```

### Backend response compatibility

Existing persisted engine results remain readable. New optional fields are
additive; the client uses compact evidence text when they are absent. No
database migration is required because analysis payloads are stored as JSON.

## Error handling

- Never display mock data as evidence.
- An unavailable profile column is handled locally without a failed API call.
- Invalid/oversize client uploads are blocked with a visible error; FastAPI
  remains the authoritative validator.
- A missing or invalid target leaves modelling screens in a clear selection
  state rather than silently choosing a different column.
- Documentation/Settings panels are keyboard closable and do not mutate data.

## Test plan

- Backend tests assert finding responses contain actual row counts and
  statistical metadata where applicable.
- Backend Feature Lab tests assert preview metadata matches each transform.
- Frontend unit tests cover target preservation, default-target selection,
  upload size validation, evidence formatting, and zero-probability display.
- Existing backend suite, frontend tests, ESLint, and a production Next build
  must pass before deployment.
- Manual production smoke test: upload CSV, inspect a diagnostic, inspect a
  finding, preview/apply a transform, train/explain/report with one target,
  open Documentation/Settings, refresh the page, and export a report.

## Out of scope

- New data formats beyond CSV.
- A user-editable settings backend or account preferences database.
- Replacing current analysis methods or introducing a new charting library.
- Mobile-layout redesign and broad visual rebranding.
