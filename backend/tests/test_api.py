"""
End-to-end API tests using FastAPI's TestClient.

    NOTE ON PATHS: the backend defines routes WITHOUT the "/api" prefix (Vercel
    adds/strips it in the deployed multi-service setup). These tests call the
    backend app directly, so they use the un-prefixed paths (e.g. "/projects").

    These exercise the real HTTP stack -- routing, dependencies, DB, file storage,
and the engines behind them -- but against an ISOLATED, temporary database and
storage folder so they never touch your real dev data.

The flow mirrors how a frontend would use the API:
    create a project -> upload a CSV -> preview it -> run every engine.
Plus the important edge cases: 404s for missing ids and 400s when a required
target is missing.
"""

from __future__ import annotations

import time
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlalchemy.orm import sessionmaker

import main
from api.routers import datasets
from db import Base, Dataset, get_db
from services import storage

_SAMPLE_CSV = Path(__file__).resolve().parent.parent / "sample_data" / "passengers.csv"

_JWT_SECRET = "test-secret-that-is-at-least-32-chars-long!!"

def _make_test_token(sub: str = "test-user-1") -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": sub, "email": "test@detabeta.local", "name": "Test",
         "iss": "detabeta-frontend", "aud": "detabeta-api",
         "iat": now, "exp": now + 600},
        _JWT_SECRET, algorithm="HS256",
    )


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A TestClient wired to a throwaway SQLite file and temp storage folder."""
    # --- isolated database ---------------------------------------------
    monkeypatch.setenv("BACKEND_JWT_SECRET", _JWT_SECRET)
    db_file = tmp_path / "test.db"
    test_engine = create_engine(
        f"sqlite:///{db_file}", connect_args={"check_same_thread": False}, future=True
    )
    TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=test_engine)

    def _override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    # Point get_db at the temp DB, and storage at a temp folder.
    main.app.dependency_overrides[get_db] = _override_get_db
    monkeypatch.setattr(storage, "STORAGE_ROOT", tmp_path / "storage")

    with TestClient(main.app) as c:
        yield c

    main.app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers():
    return {"Authorization": f"Bearer {_make_test_token()}"}


def _make_project(client: TestClient, headers: dict | None = None) -> int:
    resp = client.post("projects", json={"name": "Titanic study"}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _upload_sample(client: TestClient, project_id: int, headers: dict | None = None) -> int:
    with open(_SAMPLE_CSV, "rb") as fh:
        resp = client.post(
            f"projects/{project_id}/datasets",
            files={"file": ("passengers.csv", fh, "text/csv")},
            headers=headers,
        )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Meta + CRUD
# ---------------------------------------------------------------------------

def test_root_health(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_project_crud(client, auth_headers):
    pid = _make_project(client, headers=auth_headers)
    # list
    listing = client.get("projects", headers=auth_headers).json()
    assert any(p["id"] == pid for p in listing)
    # get
    assert client.get(f"projects/{pid}", headers=auth_headers).json()["name"] == "Titanic study"
    # delete
    assert client.delete(f"projects/{pid}", headers=auth_headers).status_code == 200
    # gone
    assert client.get(f"projects/{pid}", headers=auth_headers).status_code == 404


def test_missing_project_404(client, auth_headers):
    assert client.get("projects/99999", headers=auth_headers).status_code == 404


# ---------------------------------------------------------------------------
# Upload + preview
# ---------------------------------------------------------------------------

def test_upload_and_preview(client, auth_headers):
    pid = _make_project(client, headers=auth_headers)
    did = _upload_sample(client, pid, headers=auth_headers)

    meta = client.get(f"datasets/{did}", headers=auth_headers).json()
    assert meta["n_rows"] == 20
    assert meta["n_columns"] == 11

    preview = client.get(f"datasets/{did}/preview", headers=auth_headers).json()
    assert preview["n_columns"] == 11
    assert len(preview["rows"]) == 10  # first 10 rows
    assert "survived" in preview["columns"]


def test_reject_non_csv(client, auth_headers):
    pid = _make_project(client, headers=auth_headers)
    resp = client.post(
        f"projects/{pid}/datasets",
        files={"file": ("bad.csv", b"", "text/csv")},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_reject_upload_larger_than_configured_limit(client, auth_headers, monkeypatch):
    """Oversized files must fail before they create a DB row or stored object."""
    monkeypatch.setattr(datasets, "MAX_UPLOAD_BYTES", 4, raising=False)
    pid = _make_project(client, headers=auth_headers)

    response = client.post(
        f"projects/{pid}/datasets",
        files={"file": ("large.csv", b"amount\n12345\n", "text/csv")},
        headers=auth_headers,
    )

    assert response.status_code == 413
    assert client.get(f"projects/{pid}/datasets", headers=auth_headers).json() == []


def test_failed_dataset_commit_removes_new_storage_object(client, auth_headers, monkeypatch):
    """Storage must not retain an object when its metadata row cannot commit."""
    pid = _make_project(client, headers=auth_headers)
    deleted_keys: list[str] = []
    monkeypatch.setattr(storage, "save_csv_bytes", lambda *_: ("projects/1/new.csv", 1, 1))
    monkeypatch.setattr(storage, "delete_file", deleted_keys.append)

    original_commit = SQLAlchemySession.commit

    def fail_only_dataset_commit(self):
        if any(isinstance(item, Dataset) for item in self.new):
            raise SQLAlchemyError("database unavailable")
        return original_commit(self)

    monkeypatch.setattr(SQLAlchemySession, "commit", fail_only_dataset_commit)
    client._transport.raise_server_exceptions = False

    response = client.post(
        f"projects/{pid}/datasets",
        files={"file": ("sales.csv", b"amount\n10\n", "text/csv")},
        headers=auth_headers,
    )

    assert response.status_code == 500
    assert deleted_keys == ["projects/1/new.csv"]


# ---------------------------------------------------------------------------
# The 9 engine endpoints
# ---------------------------------------------------------------------------

def test_analysis_no_target_engines(client, auth_headers):
    pid = _make_project(client, headers=auth_headers)
    did = _upload_sample(client, pid, headers=auth_headers)
    for engine in ["understand", "health", "investigate", "statistics", "feature-lab"]:
        resp = client.get(f"datasets/{did}/analysis/{engine}", headers=auth_headers)
        assert resp.status_code == 200, f"{engine}: {resp.text}"
        assert isinstance(resp.json(), dict)


def test_analysis_target_engines(client, auth_headers):
    pid = _make_project(client, headers=auth_headers)
    did = _upload_sample(client, pid, headers=auth_headers)
    for engine in ["recommend", "experiment", "explain"]:
        resp = client.get(f"datasets/{did}/analysis/{engine}?target=survived", headers=auth_headers)
        assert resp.status_code == 200, f"{engine}: {resp.text}"
        assert isinstance(resp.json(), dict)


def test_report_with_and_without_target(client, auth_headers):
    pid = _make_project(client, headers=auth_headers)
    did = _upload_sample(client, pid, headers=auth_headers)
    assert client.get(f"datasets/{did}/analysis/report", headers=auth_headers).status_code == 200
    assert (
        client.get(f"datasets/{did}/analysis/report?target=survived", headers=auth_headers).status_code == 200
    )


def test_required_target_missing_returns_400(client, auth_headers):
    pid = _make_project(client, headers=auth_headers)
    did = _upload_sample(client, pid, headers=auth_headers)
    # No target on a modelling engine -> 400.
    assert client.get(f"datasets/{did}/analysis/experiment", headers=auth_headers).status_code == 400


def test_invalid_target_returns_400(client, auth_headers):
    pid = _make_project(client, headers=auth_headers)
    did = _upload_sample(client, pid, headers=auth_headers)
    resp = client.get(f"datasets/{did}/analysis/recommend?target=nope", headers=auth_headers)
    assert resp.status_code == 400
    assert "not in the dataset" in resp.json()["detail"]


def test_analysis_on_missing_dataset_404(client, auth_headers):
    assert client.get("datasets/99999/analysis/understand", headers=auth_headers).status_code == 404


# ---------------------------------------------------------------------------
# Feature Lab: apply a transform -> new dataset version
# ---------------------------------------------------------------------------

def test_apply_transform_creates_new_version(client, auth_headers):
    pid = _make_project(client, headers=auth_headers)
    did = _upload_sample(client, pid, headers=auth_headers)

    # Drop the identifier column; expect a NEW dataset with one fewer column.
    resp = client.post(
        f"datasets/{did}/apply-transform",
        json={"transform": "drop_column", "columns": ["passenger_id"]},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()

    # A brand-new dataset id + versioned name, original left intact.
    assert body["dataset"]["id"] != did
    assert body["dataset"]["name"] == "passengers_v2.csv"
    assert body["dataset"]["n_columns"] == 10  # was 11
    assert client.get(f"datasets/{did}", headers=auth_headers).json()["n_columns"] == 11

    # Health snapshots are present and well-formed.
    assert "health_before" in body and "health_after" in body
    assert 0 <= body["health_after"]["score"] <= 100
    assert body["changes"]

    # The project now lists two datasets.
    listing = client.get(f"projects/{pid}/datasets", headers=auth_headers).json()
    assert len(listing) == 2


def test_apply_transform_health_improves_when_clipping_outliers(client, auth_headers):
    pid = _make_project(client, headers=auth_headers)
    did = _upload_sample(client, pid, headers=auth_headers)

    # Feature Lab flags 'fare' for outlier clipping; applying it should not
    # lower the health score (clipping removes an outlier issue).
    resp = client.post(
        f"datasets/{did}/apply-transform",
        json={
            "transform": "clip_outliers",
            "columns": ["fare"],
            "evidence": {"lower_bound": 0.0, "upper_bound": 100.0},
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["health_after"]["score"] >= body["health_before"]["score"]


def test_apply_transform_versions_increment(client, auth_headers):
    pid = _make_project(client, headers=auth_headers)
    did = _upload_sample(client, pid, headers=auth_headers)
    payload = {"transform": "drop_column", "columns": ["passenger_id"]}
    first = client.post(f"datasets/{did}/apply-transform", json=payload, headers=auth_headers).json()
    assert first["dataset"]["name"] == "passengers_v2.csv"
    # Applying again to the original produces _v3 (not a duplicate _v2).
    second = client.post(f"datasets/{did}/apply-transform", json=payload, headers=auth_headers).json()
    assert second["dataset"]["name"] == "passengers_v3.csv"


def test_apply_transform_bad_column_returns_400(client, auth_headers):
    pid = _make_project(client, headers=auth_headers)
    did = _upload_sample(client, pid, headers=auth_headers)
    resp = client.post(
        f"datasets/{did}/apply-transform",
        json={"transform": "drop_column", "columns": ["does_not_exist"]},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_apply_transform_on_missing_dataset_404(client, auth_headers):
    resp = client.post(
        "datasets/99999/apply-transform",
        json={"transform": "drop_column", "columns": ["x"]},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_apply_transform_legacy_source_explains_how_to_recover(client, auth_headers):
    """A local-era path must not turn into an opaque server error after migration."""
    pid = _make_project(client, headers=auth_headers)
    did = _upload_sample(client, pid, headers=auth_headers)
    dataset = client.get(f"datasets/{did}", headers=auth_headers).json()

    # This path deliberately does not exist in the temporary storage root.
    db = next(main.app.dependency_overrides[get_db]())
    db.get(Dataset, dataset["id"]).storage_path = "2/missing-legacy.csv"
    db.commit()
    db.close()

    resp = client.post(
        f"datasets/{did}/apply-transform",
        json={"transform": "drop_column", "columns": ["passenger_id"]},
        headers=auth_headers,
    )

    assert resp.status_code == 409
    assert "migrate" in resp.json()["detail"].lower()


def test_apply_transform_storage_failure_returns_service_error(client, auth_headers, monkeypatch):
    pid = _make_project(client, headers=auth_headers)
    did = _upload_sample(client, pid, headers=auth_headers)
    monkeypatch.setattr(storage, "save_dataframe", lambda *_: (_ for _ in ()).throw(RuntimeError("bucket down")))

    resp = client.post(
        f"datasets/{did}/apply-transform",
        json={"transform": "drop_column", "columns": ["passenger_id"]},
        headers=auth_headers,
    )

    assert resp.status_code == 503
    assert "could not be saved" in resp.json()["detail"].lower()
