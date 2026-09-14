# DetaBeta — Automated Data Science Workbench

[![CI](https://github.com/Shravan144/DetaBeta/actions/workflows/ci.yml/badge.svg)](https://github.com/Shravan144/DetaBeta/actions/workflows/ci.yml)
[![Live demo](https://img.shields.io/badge/Live%20demo-Open%20DetaBeta-00c896?style=flat-square)](https://detabeta-shravan144.vercel.app)

**DetaBeta** is a full-stack data-science workspace for turning a CSV file into an evidence-led analysis. It guides users through data profiling, health diagnostics, pattern investigation, preparation recommendations, baseline modelling, explainability, and an exportable research report—without overwriting the original dataset.

**Live demo:** [detabeta-shravan144.vercel.app](https://detabeta-shravan144.vercel.app)

## Why DetaBeta?

Exploratory analysis often lives across notebooks, spreadsheets, and disconnected tools. DetaBeta brings the early data-science workflow into one guided application:

1. Upload a CSV and create an experiment workspace.
2. Inspect column profiles and data-quality diagnostics.
3. Investigate distributions, relationships, and group differences.
4. Review versioned, non-destructive preparation recommendations.
5. Train and compare baseline machine-learning models.
6. Inspect global feature importance and row-level prediction factors.
7. Generate and export a structured research report.

## Features

- **Secure sign-in:** Google, GitHub, and optional demo credentials through NextAuth.
- **CSV analysis workspace:** Upload CSV files up to 25 MB and retain datasets, sessions, and reports per user.
- **Dataset explorer:** Searchable data preview and column-level metadata, summaries, cardinality, and missing-value context.
- **Data diagnostics:** Evidence-backed checks for missing values, duplicates, outliers, and consistency concerns.
- **Investigation hub:** Surfaced distributions, associations, and group-difference findings with confidence and caveats.
- **Feature Lab:** Recommends cleaning and encoding steps; every applied change creates a new dataset version rather than replacing raw evidence.
- **Experiment Studio:** Select a target, compare Logistic Regression, Decision Tree, and Random Forest baselines, and review cross-validation metrics.
- **Explainability:** Review permutation-based global feature importance and local, row-level contribution signals.
- **Research reports:** Compose a plain-language analytical narrative and export it as HTML, Markdown, or PDF.

## Architecture

```text
Browser
  │
  ▼
Next.js + React frontend ── NextAuth session handling
  │
  ▼
FastAPI analysis API ── Pandas / SciPy / scikit-learn engines
  │                         │
  ▼                         ▼
PostgreSQL persistence       Private dataset storage
```

The repository also includes Docker Compose for a local PostgreSQL, FastAPI, and Next.js stack.

## Tech Stack

| Area | Technologies |
| --- | --- |
| Frontend | Next.js, React, TypeScript, Tailwind CSS, Recharts, NextAuth |
| Backend | Python, FastAPI, SQLAlchemy, Alembic |
| Analysis | Pandas, NumPy, SciPy, scikit-learn |
| Data & storage | PostgreSQL, Supabase Storage (optional in production) |
| Quality & delivery | Pytest, Node test runner, ESLint, GitHub Actions, Docker Compose |

## Run Locally

### Prerequisites

- Node.js 20+
- Python 3.11+
- PostgreSQL 16+ (or Docker)

### 1. Configure environment variables

Copy the template and fill in only the services you use:

```powershell
Copy-Item .env.example .env
```

At minimum, configure `NEXTAUTH_SECRET` and `BACKEND_JWT_SECRET` for authenticated local use. OAuth and Supabase settings are optional. Never commit `.env` or provider secrets.

### 2. Start the backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 3. Start the frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### Run with Docker

```powershell
docker compose up --build
```

This starts PostgreSQL, the backend at `http://localhost:8000`, and the frontend at `http://localhost:3000`.

## Configuration

The complete, safe-to-share configuration template is in [`.env.example`](.env.example). Key groups are:

- **Persistence:** `DATABASE_URL`, `STORAGE_ROOT`, and optional Supabase settings.
- **Upload safety:** `MAX_UPLOAD_BYTES` and `ALLOWED_ORIGINS`.
- **Authentication:** `NEXTAUTH_SECRET`, `NEXTAUTH_URL`, and optional GitHub/Google OAuth credentials.
- **Frontend/backend bridge:** `BACKEND_JWT_SECRET` must be a strong shared secret in production.

## Tests and Quality Checks

```powershell
# Backend tests
cd backend
pytest -q

# Frontend unit tests
cd frontend
npm test

# Frontend linting and production build
npm run lint
npm run build
```

Continuous integration runs the backend tests and frontend test, lint, and build checks on GitHub Actions.

## Project Structure

```text
DetaBeta/
├── backend/                 # FastAPI routes, analysis engines, persistence, tests
│   ├── app/
│   ├── alembic/             # Database migrations
│   ├── sample_data/         # Test fixtures
│   └── tests/
├── frontend/                # Next.js application
│   └── src/
│       ├── app/             # Routes and API handlers
│       ├── components/      # Workspace UI
│       └── lib/             # Client utilities and tests
├── .github/workflows/       # Continuous integration
├── .env.example             # Safe environment-variable template
└── compose.yaml             # Local multi-service development stack
```

## Design Principles

- **Evidence before claims:** Statistical and investigation views distinguish observation from inference.
- **Non-destructive preparation:** Recommendations create a new dataset version; raw uploads remain intact.
- **Model humility:** Small datasets and exploratory findings are presented with limitations, not as causal proof.
- **Production-aware defaults:** Scoped persistence, authentication, request validation, and upload-size limits are built into the application flow.

## Current Scope

DetaBeta is designed for tabular CSV exploration and supervised baseline modelling. It is not a replacement for domain review, rigorous experimentation, or independent validation on new data. Treat discoveries as analytical leads, especially for small datasets.

## Author

Built by [Shravan Bhat](https://github.com/Shravan144).
