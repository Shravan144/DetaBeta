# DetaBeta

DetaBeta is an interactive data-science laboratory. It guides a user from a
dataset upload through profiling, diagnostics, statistical evidence, feature
engineering recommendations, model experiments, explainability, and a
research report.

## Stack

- **Frontend:** Next.js, React, TypeScript, Tailwind CSS, Recharts
- **Backend:** FastAPI, SQLAlchemy, pandas, SciPy, scikit-learn
- **Data:** SQLite and local files for offline work; Supabase Postgres plus a
  private Supabase Storage bucket for durable production data

## Prerequisites

- Python 3.11 or later
- Node.js 20 or later

## Local setup

1. Create a fresh virtual environment at the repository root:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -r backend\requirements.txt
   ```

2. Copy `.env.example` to `.env` and adjust values if needed. For local
   development, `STORAGE_ROOT=backend/storage` keeps uploaded datasets in the
   project folder rather than in a temporary directory.

3. Install frontend dependencies:

   ```powershell
   npm.cmd --prefix frontend ci
   ```

4. Run the backend in one terminal:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --env-file .env --reload --port 8000
   ```

5. Run the frontend in a second terminal:

   ```powershell
   npm.cmd --prefix frontend run dev
   ```

   Open `http://localhost:3000`.

## Supabase production persistence

Supabase stores DetaBeta's project metadata, datasets, analysis sessions, and
cached results in Postgres. The raw CSV bytes live in a **private** `datasets`
bucket. Keep the app's existing authentication; Supabase Auth is not required
for this integration.

1. In Supabase, create a project and a private Storage bucket named `datasets`.
2. Add these backend-only values to `.env` or to your deployment provider's
   encrypted backend environment settings:

   ```dotenv
   DATABASE_URL=postgresql://...
   STORAGE_BACKEND=supabase
   SUPABASE_URL=https://your-project-ref.supabase.co
   SUPABASE_SECRET_KEY=sb_secret_...
   SUPABASE_STORAGE_BUCKET=datasets
   MAX_UPLOAD_BYTES=26214400
   ```

   The database URI uses the password selected when the Supabase project was
   created. URL-encode reserved password characters, for example `@` becomes
   `%40`. `SUPABASE_SECRET_KEY` bypasses Supabase Storage policies, so it must
   be supplied only to FastAPI—never to the browser, Git, or a `NEXT_PUBLIC_`
   variable.
3. Apply the database schema once, before starting or deploying the backend:

   ```powershell
   Push-Location backend
   ..\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
   Pop-Location
   ```

4. Start the backend, create a project, upload a small CSV, run one analysis,
   restart the backend, and refresh the browser. The project, file preview,
   and session history should remain present.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider backend\tests
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
```

## Docker

Docker Compose starts the frontend, FastAPI backend, PostgreSQL database, and
persistent dataset storage together:

```powershell
docker compose up --build
```

Open `http://localhost:3000`. The frontend proxies browser requests from
`/api/*` to the backend container, so the API is never exposed to browser code
as an internal container hostname. Compose uses local-only default database
credentials; set `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` in
your `.env` file before using it outside local development.

## Continuous integration

GitHub Actions installs the backend and frontend from their locked dependency
definitions, runs the backend test suite, then lints and builds the frontend.
All of these checks are required for pull requests and pushes to `main`.

## Architecture

The FastAPI API owns projects, CSV datasets, session history, cached engine
outputs, and report exports. The nine analysis engines remain modular pure-ish
services under `backend/engines`. The Next.js client presents the laboratory
workflow and calls the backend through `/api` in deployment or a configured
local API base in development.

## Current scope

The current upload format is CSV. Persistent cloud storage and versioned
schema migrations are now supported; the next milestone is multi-format
uploads.
