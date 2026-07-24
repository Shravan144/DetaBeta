# DetaBeta

DetaBeta is an interactive data-science laboratory. It guides a user from a
dataset upload through profiling, diagnostics, statistical evidence, feature
engineering recommendations, model experiments, explainability, and a
research report.

## Stack

- **Frontend:** Next.js, React, TypeScript, Tailwind CSS, Recharts
- **Backend:** FastAPI, SQLAlchemy, pandas, SciPy, scikit-learn
- **Data:** SQLite locally; PostgreSQL/Neon can be configured through
  `DATABASE_URL`

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

The current upload format is CSV. Authentication, persistent cloud object
storage, multi-format uploads, and schema migrations are the next production
hardening milestones.
