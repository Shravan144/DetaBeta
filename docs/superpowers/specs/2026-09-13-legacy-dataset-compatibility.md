# Legacy Dataset Compatibility Design

## Goal

Keep previously uploaded local datasets usable after the application switches to
Supabase Storage, and make failed transformations/reports understandable in the
user interface.

## Decision

Treat the local SQLite metadata database and `STORAGE_ROOT` as read-only legacy
sources. A small, idempotent command will copy their projects and each
database-referenced CSV to the configured Supabase PostgreSQL database/private
bucket. It supports a dry run by default and never deletes the original local
file or alters local metadata. Analysis caches are intentionally excluded;
they will be regenerated from the immutable CSV.

The application will also detect a legacy storage key while Supabase is active
and return a specific, actionable 409 response instead of a generic server
error.  A failed object-store write is converted to an actionable 503 response;
database cleanup remains intact.

## UI behaviour

Feature Lab and Reports display the API's user-safe message in their own error
card and toast.  Expected request failures are not sent to `console.error`, so
Next.js development mode no longer puts an error overlay over the workspace.

## Safety

- Migration runs only when explicitly invoked with `--apply`.
- Dry run reports candidate dataset ids and paths without a write.
- The database path changes only after a successful private bucket upload.
- Existing local files are retained as a rollback source.
