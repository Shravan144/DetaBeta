# Supabase Persistence Design

## Goal

Make DetaBeta data durable in production without changing its existing NextAuth
login. A signed-in user must be able to return after a deployment or restart
and still see their projects, uploaded datasets, analysis-session history, and
cached engine results.

## Decisions

1. **Supabase Postgres is the system of record** for the existing SQLAlchemy
   models: `projects`, `datasets`, `analysis_sessions`, and `engine_results`.
   The app keeps its current NextAuth-to-backend JWT bridge; Supabase Auth is
   deliberately out of scope.
2. **A private Supabase Storage bucket named `datasets` holds CSV bytes.**
   Database rows store an opaque object key, never a public URL. The service
   role key stays only in the FastAPI environment and must never be exposed as
   a `NEXT_PUBLIC_*` variable or committed to Git.
3. **Storage remains pluggable.** `STORAGE_BACKEND=local` remains the default
   for tests and offline development. `STORAGE_BACKEND=supabase` is enabled
   only when all Supabase storage settings are present.
4. **Every write uses a unique object key** in the form
   `projects/<project-id>/<uuid>_<safe-filename>`. Uploading `sales.csv` twice
   creates two distinct datasets and never overwrites the first file.
5. **Schema changes use Alembic migrations.** Production never relies on
   `Base.metadata.create_all()` during a web request. Migrations are run once,
   manually or as an explicit release step, before a new backend is promoted.

## Required configuration

Backend-only variables:

```dotenv
DATABASE_URL=postgresql+psycopg://...
STORAGE_BACKEND=supabase
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SECRET_KEY=<server-only-secret>
SUPABASE_STORAGE_BUCKET=datasets
MAX_UPLOAD_BYTES=26214400
```

`DATABASE_URL` is copied from the Supabase dashboard's **Connect** dialog in
SQLAlchemy/URI form. The secret key is copied from the project's API
keys area, not from the browser client configuration. The bucket must remain
private. `MAX_UPLOAD_BYTES` is 25 MiB in this first release; a user exceeding
it receives a clear HTTP 413 response.

## Data flow

```text
Browser -> Next.js /api proxy -> FastAPI
          (25 MiB proxy limit)      |
                                      +-> validate CSV bytes
                                      +-> Supabase Storage private bucket
                                      +-> Supabase Postgres metadata + results
```

FastAPI downloads a private object only when it needs a Pandas DataFrame for a
preview, engine run, or feature transform. Dataset deletion removes its object
before its database row. If a database commit fails after an object is
uploaded, the backend removes that new object and rolls back the transaction.

## Acceptance criteria

- A fresh Supabase database is created solely through Alembic and can serve
  the full create-project, upload, preview, analysis, transform, and delete
  workflow.
- Two uploads with the same filename have distinct storage keys and retain
  their respective content.
- A private bucket is used; no CSV URL or secret key reaches the browser.
- Local tests keep using SQLite and local temporary storage without any live
  Supabase credentials.
- Oversized uploads fail before storage/database mutation; the frontend proxy
  permits the configured supported size.
- The app works after a backend restart using the same Supabase project.
