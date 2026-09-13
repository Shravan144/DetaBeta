# Supabase Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Persist DetaBeta projects, analysis history, and uploaded CSV files in Supabase without replacing the existing NextAuth login.

**Architecture:** SQLAlchemy connects to Supabase Postgres via DATABASE_URL; Alembic owns the database schema. The storage service keeps a local implementation for tests and offline development, and adds a private Supabase Storage implementation for production. Existing routers and Pandas engines retain their save/load/delete interfaces.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, psycopg 3, supabase-py, Pandas, Next.js 16, Supabase Postgres and private Storage.

**Spec:** docs/superpowers/specs/2026-09-13-supabase-persistence.md

## Global Constraints

- Keep NextAuth and the JWT bridge; do not add Supabase Auth in this release.
- Never commit .env, a Supabase service-role key, or a Postgres password.
- Keep the datasets bucket private; FastAPI is its only client.
- Keep STORAGE_BACKEND=local for tests and offline development.
- Store opaque object keys, never public URLs, in Dataset.storage_path.
- Enforce a 25 MiB upload limit in both the Next.js proxy and FastAPI.
- Run migrations once as a release step; do not run them from a serverless request startup.

## Files and responsibilities

- backend/services/storage.py: local/Supabase storage adapters and CSV conversion.
- backend/api/routers/datasets.py: bounded uploads and database/storage cleanup.
- backend/alembic.ini and backend/migrations/: versioned database schema.
- backend/db/__init__.py and backend/main.py: schema verification rather than runtime creation.
- backend/requirements.txt and backend/pyproject.toml: required runtime packages.
- backend/tests/test_storage.py and backend/tests/test_api.py: persistence and safety coverage.
- .env.example and README.md: safe configuration and deployment directions.
- frontend/next.config.ts: same-origin proxy upload size limit.

### Task 1: Create Supabase resources without exposing secrets

**Files:**
- Modify locally only: .env
- Modify: .env.example

**Produces:** production configuration used by the backend.

- [ ] **Step 1: Create the project**

  In the Supabase dashboard, create a project named detabeta-production, select the closest region to its expected users, and save the generated database password in a password manager. Wait for the project health status to become ready.

- [ ] **Step 2: Create private file storage**

  Open Storage, create one bucket named datasets, and leave the Public option off. Do not add browser upload policies: all file access stays in FastAPI.

- [ ] **Step 3: Fill local backend-only variables**

  Copy the SQLAlchemy-compatible URI from Connect into DATABASE_URL. Copy the project URL and service_role key from the dashboard into these local-only variables:

    STORAGE_BACKEND=supabase
    SUPABASE_URL=https://project-ref.supabase.co
    SUPABASE_SERVICE_ROLE_KEY=server-only-value
    SUPABASE_STORAGE_BUCKET=datasets
    MAX_UPLOAD_BYTES=26214400

- [ ] **Step 4: Verify secret hygiene**

  Run: git check-ignore .env; git status --short .env .env.example

  Expected: .env is ignored; no secret appears in Git status, staged changes, or application source.

### Task 2: Make database schema versioned

**Files:**
- Create: backend/alembic.ini
- Create: backend/migrations/env.py
- Create: backend/migrations/script.py.mako
- Create: backend/migrations/versions/0001_initial_schema.py
- Modify: backend/db/__init__.py
- Modify: backend/main.py
- Create: backend/tests/test_migrations.py

**Consumes:** db.session.Base.metadata and DATABASE_URL.

**Produces:** alembic upgrade head, creating the existing four tables and indexes.

- [ ] **Step 1: Write the migration test**

    def test_upgrade_creates_application_tables(tmp_path):
        database_url = f"sqlite:///{tmp_path / 'migrated.db'}"
        run_alembic_upgrade(database_url)
        assert application_tables(database_url) == {
            "projects", "datasets", "analysis_sessions", "engine_results"
        }

- [ ] **Step 2: Verify the test fails**

  Run: python -m pytest backend/tests/test_migrations.py -q

  Expected: FAIL because no Alembic configuration exists.

- [ ] **Step 3: Add the initial revision**

  Configure Alembic to target db.session.Base.metadata. The revision creates the four current tables, foreign keys with ondelete="CASCADE", the existing indexes, and the uq_engine_per_session constraint. Remove create_all() and the ad-hoc ALTER TABLE migration from init_db; startup instead checks that alembic_version and application tables exist and tells the operator to run alembic upgrade head when they do not.

- [ ] **Step 4: Verify migration behaviour**

  Run: python -m pytest backend/tests/test_migrations.py -q

  Expected: PASS. Once the user has supplied a real DATABASE_URL, run alembic -c backend/alembic.ini upgrade head exactly once against Supabase.

- [ ] **Step 5: Commit**

  Run:
    git add backend/alembic.ini backend/migrations backend/db/__init__.py backend/main.py backend/tests/test_migrations.py
    git commit -m "feat: manage database schema with Alembic"

### Task 3: Add the private Supabase Storage adapter

**Files:**
- Modify: backend/services/storage.py
- Modify: backend/services/__init__.py
- Modify: backend/requirements.txt
- Modify: backend/pyproject.toml
- Create: backend/tests/test_storage.py

**Consumes:** STORAGE_BACKEND, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, and SUPABASE_STORAGE_BUCKET.

**Produces:** the current public functions save_csv_bytes, save_dataframe, load_dataframe, and delete_file with the same tuple return type.

- [ ] **Step 1: Write adapter-contract tests**

    def test_same_filename_creates_two_distinct_storage_keys(storage):
        first, _, _ = storage.save_csv_bytes(7, "sales.csv", b"amount\n10\n")
        second, _, _ = storage.save_csv_bytes(7, "sales.csv", b"amount\n20\n")
        assert first != second
        assert storage.load_dataframe(first)["amount"].tolist() == [10]
        assert storage.load_dataframe(second)["amount"].tolist() == [20]

    def test_supabase_adapter_uses_an_opaque_private_key(fake_supabase):
        storage = SupabaseDatasetStorage(fake_supabase, "datasets")
        key, _, _ = storage.save_csv_bytes(7, "sales.csv", b"amount\n10\n")
        assert key.startswith("projects/7/")
        assert fake_supabase.uploaded[key] == b"amount\n10\n"

- [ ] **Step 2: Verify the tests fail**

  Run: python -m pytest backend/tests/test_storage.py -q

  Expected: FAIL because save_csv_bytes currently overwrites matching filenames and no remote adapter exists.

- [ ] **Step 3: Implement adapters**

  Add LocalDatasetStorage and SupabaseDatasetStorage behind a factory selected by STORAGE_BACKEND. Parse and load CSV bytes with io.BytesIO; serialize derived frames to UTF-8 bytes. Build each storage key with uuid.uuid4() and _safe_filename, using projects/<project-id>/<uuid>_<filename>. The Supabase client must be initialized only with server-side environment variables and must raise a clear configuration error when any required variable is absent.

  Add these dependencies in both manifests:

    alembic>=1.13
    python-dotenv>=1.0
    supabase>=2.0

- [ ] **Step 4: Verify the adapters**

  Run: python -m pytest backend/tests/test_storage.py -q

  Expected: PASS without live network access; tests use a fake Supabase client.

- [ ] **Step 5: Commit**

  Run:
    git add backend/services/storage.py backend/services/__init__.py backend/requirements.txt backend/pyproject.toml backend/tests/test_storage.py
    git commit -m "feat: store datasets in private Supabase Storage"

### Task 4: Make writes bounded and transactional

**Files:**
- Modify: backend/api/routers/datasets.py
- Modify: backend/tests/test_api.py
- Modify: frontend/next.config.ts

**Consumes:** storage functions from Task 3 and MAX_UPLOAD_BYTES.

**Produces:** HTTP 413 for a file over 25 MiB and no orphan object if database persistence fails.

- [ ] **Step 1: Write failing endpoint tests**

    def test_upload_over_limit_returns_413_without_a_dataset(client, auth_headers, monkeypatch):
        monkeypatch.setattr(datasets, "MAX_UPLOAD_BYTES", 4)
        project_id = _make_project(client, auth_headers)
        response = client.post(
            f"projects/{project_id}/datasets",
            files={"file": ("large.csv", b"a\n12345\n", "text/csv")},
            headers=auth_headers,
        )
        assert response.status_code == 413
        assert client.get(
            f"projects/{project_id}/datasets", headers=auth_headers
        ).json() == []

- [ ] **Step 2: Verify focused test fails**

  Run: python -m pytest backend/tests/test_api.py -k over_limit -q

  Expected: FAIL because the route currently reads the full upload unbounded.

- [ ] **Step 3: Implement the safety boundary**

  Read UploadFile in chunks until EOF or MAX_UPLOAD_BYTES + 1. For excess bytes return HTTPException with status 413 and detail: Dataset is larger than the 25 MiB upload limit. After an object is saved, wrap database add, commit, and refresh in try/except: call db.rollback(), delete only the new object key, and return a safe API error. Apply the same rollback/delete rule to the transformed-dataset route.

  Match the proxy limit in Next configuration:

    experimental: {
      proxyClientMaxBodySize: "25mb",
    },

- [ ] **Step 4: Verify endpoints and frontend build**

  Run:
    python -m pytest backend/tests/test_api.py -q
    npm --prefix frontend run lint
    npm --prefix frontend run build

  Expected: all commands pass; files above 25 MiB give a human-readable 413 rather than a proxy reset.

- [ ] **Step 5: Commit**

  Run:
    git add backend/api/routers/datasets.py backend/tests/test_api.py frontend/next.config.ts
    git commit -m "fix: make dataset uploads bounded and transactional"

### Task 5: Run the first cloud smoke test and document it

**Files:**
- Modify: .env.example
- Modify: README.md

**Consumes:** migrated Supabase database and Task 3 adapter.

**Produces:** verified persistence across a backend restart.

- [ ] **Step 1: Document variables without values**

  Add this backend-only block to both setup documents:

    DATABASE_URL=
    STORAGE_BACKEND=supabase
    SUPABASE_URL=
    SUPABASE_SERVICE_ROLE_KEY=
    SUPABASE_STORAGE_BUCKET=datasets
    MAX_UPLOAD_BYTES=26214400

  State that only FastAPI receives the service-role key.

- [ ] **Step 2: Install and check dependencies**

  Run: .venv\Scripts\python.exe -m pip install -r backend\requirements.txt

  Then run: .venv\Scripts\python.exe -c "import alembic, dotenv, supabase; print('dependencies ready')"

  Expected: both commands exit with code 0.

- [ ] **Step 3: Execute the smoke test**

  1. Start FastAPI with Supabase variables loaded.
  2. Start the frontend with BACKEND_URL=http://127.0.0.1:8000.
  3. Sign in, create a project, upload a small CSV, run Dataset Understanding, and apply one Feature Lab transform.
  4. Stop and restart FastAPI; refresh the browser.
  5. Confirm both datasets, previews, and session history still load.
  6. Confirm Supabase Table Editor has the rows and the private bucket has two distinct object keys.

- [ ] **Step 4: Run final checks and commit**

  Run:
    python -m pytest -q
    npm --prefix frontend run lint
    npm --prefix frontend run build
    git diff --check

  Expected: all checks pass.

  Run:
    git add .env.example README.md
    git commit -m "docs: add Supabase persistence setup"

### Task 6: Deploy without losing data

**Files:**
- Modify: hosting provider's encrypted backend environment settings only

**Consumes:** the tested Supabase configuration and completed migration.

**Produces:** an application that preserves data after a production redeploy.

- [ ] **Step 1: Add deployment secrets**

  Add DATABASE_URL, STORAGE_BACKEND, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_STORAGE_BUCKET, MAX_UPLOAD_BYTES, BACKEND_JWT_SECRET, and the final allowed frontend origin to the backend's encrypted environment. Do not add the Supabase service-role key to frontend environment settings.

- [ ] **Step 2: Run migrations explicitly before release**

  Run alembic upgrade head against the production connection. Verify that alembic_version reports revision 0001_initial_schema before the backend release.

- [ ] **Step 3: Verify deployed persistence**

  Create one production project, upload a CSV, run one analysis, refresh, and redeploy/restart the backend. The same project, dataset preview, and cached session must remain present.

## Plan review

- **Spec coverage:** Tasks 1–2 establish secure Supabase and versioned schema; Tasks 3–4 implement durable private files and bounded writes; Tasks 5–6 prove local, restart, and deployed persistence.
- **Type consistency:** the public storage function signatures are unchanged, so existing routers and engine services remain compatible.
- **Security review:** service-role credentials are backend-only, the bucket is private, and object keys are opaque rather than user-supplied paths.

