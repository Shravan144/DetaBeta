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

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import main
from db import Base, get_db
from services import storage

_SAMPLE_CSV = Path(__file__).resolve().parent.parent / "sample_data" / "passengers.csv"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A TestClient wired to a throwaway SQLite file and temp storage folder."""
    # --- isolated database ---------------------------------------------
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


def _make_project(client: TestClient) -> int:
    resp = client.post("projects", json={"name": "Titanic study"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _upload_sample(client: TestClient, project_id: int) -> int:
    with open(_SAMPLE_CSV, "rb") as fh:
        resp = client.post(
            f"projects/{project_id}/datasets",
            files={"file": ("passengers.csv", fh, "text/csv")},
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


def test_project_crud(client):
    pid = _make_project(client)
    # list
    listing = client.get("projects").json()
    assert any(p["id"] == pid for p in listing)
    # get
    assert client.get(f"projects/{pid}").json()["name"] == "Titanic study"
    # delete
    assert client.delete(f"projects/{pid}").status_code == 200
    # gone
    assert client.get(f"projects/{pid}").status_code == 404


def test_missing_project_404(client):
    assert client.get("projects/99999").status_code == 404


# ---------------------------------------------------------------------------
# Upload + preview
# ---------------------------------------------------------------------------

def test_upload_and_preview(client):
    pid = _make_project(client)
    did = _upload_sample(client, pid)

    meta = client.get(f"datasets/{did}").json()
    assert meta["n_rows"] == 20
    assert meta["n_columns"] == 11

    preview = client.get(f"datasets/{did}/preview").json()
    assert preview["n_columns"] == 11
    assert len(preview["rows"]) == 10  # first 10 rows
    assert "survived" in preview["columns"]


def test_reject_non_csv(client):
    pid = _make_project(client)
    resp = client.post(
        f"projects/{pid}/datasets",
        files={"file": ("bad.csv", b"", "text/csv")},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# The 9 engine endpoints
# ---------------------------------------------------------------------------

def test_analysis_no_target_engines(client):
    pid = _make_project(client)
    did = _upload_sample(client, pid)
    for engine in ["understand", "health", "investigate", "statistics", "feature-lab"]:
        resp = client.get(f"datasets/{did}/analysis/{engine}")
        assert resp.status_code == 200, f"{engine}: {resp.text}"
        assert isinstance(resp.json(), dict)


def test_analysis_target_engines(client):
    pid = _make_project(client)
    did = _upload_sample(client, pid)
    for engine in ["recommend", "experiment", "explain"]:
        resp = client.get(f"datasets/{did}/analysis/{engine}?target=survived")
        assert resp.status_code == 200, f"{engine}: {resp.text}"
        assert isinstance(resp.json(), dict)


def test_report_with_and_without_target(client):
    pid = _make_project(client)
    did = _upload_sample(client, pid)
    assert client.get(f"datasets/{did}/analysis/report").status_code == 200
    assert (
        client.get(f"datasets/{did}/analysis/report?target=survived").status_code == 200
    )


def test_required_target_missing_returns_400(client):
    pid = _make_project(client)
    did = _upload_sample(client, pid)
    # No target on a modelling engine -> 400.
    assert client.get(f"datasets/{did}/analysis/experiment").status_code == 400


def test_invalid_target_returns_400(client):
    pid = _make_project(client)
    did = _upload_sample(client, pid)
    resp = client.get(f"datasets/{did}/analysis/recommend?target=nope")
    assert resp.status_code == 400
    assert "not in the dataset" in resp.json()["detail"]


def test_analysis_on_missing_dataset_404(client):
    assert client.get("datasets/99999/analysis/understand").status_code == 404


# ---------------------------------------------------------------------------
# Feature Lab: apply a transform -> new dataset version
# ---------------------------------------------------------------------------

def test_apply_transform_creates_new_version(client):
    pid = _make_project(client)
    did = _upload_sample(client, pid)

    # Drop the identifier column; expect a NEW dataset with one fewer column.
    resp = client.post(
        f"datasets/{did}/apply-transform",
        json={"transform": "drop_column", "columns": ["passenger_id"]},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()

    # A brand-new dataset id + versioned name, original left intact.
    assert body["dataset"]["id"] != did
    assert body["dataset"]["name"] == "passengers_v2.csv"
    assert body["dataset"]["n_columns"] == 10  # was 11
    assert client.get(f"datasets/{did}").json()["n_columns"] == 11

    # Health snapshots are present and well-formed.
    assert "health_before" in body and "health_after" in body
    assert 0 <= body["health_after"]["score"] <= 100
    assert body["changes"]

    # The project now lists two datasets.
    listing = client.get(f"projects/{pid}/datasets").json()
    assert len(listing) == 2


def test_apply_transform_health_improves_when_clipping_outliers(client):
    pid = _make_project(client)
    did = _upload_sample(client, pid)

    # Feature Lab flags 'fare' for outlier clipping; applying it should not
    # lower the health score (clipping removes an outlier issue).
    resp = client.post(
        f"datasets/{did}/apply-transform",
        json={
            "transform": "clip_outliers",
            "columns": ["fare"],
            "evidence": {"lower_bound": 0.0, "upper_bound": 100.0},
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["health_after"]["score"] >= body["health_before"]["score"]


def test_apply_transform_versions_increment(client):
    pid = _make_project(client)
    did = _upload_sample(client, pid)
    payload = {"transform": "drop_column", "columns": ["passenger_id"]}
    first = client.post(f"datasets/{did}/apply-transform", json=payload).json()
    assert first["dataset"]["name"] == "passengers_v2.csv"
    # Applying again to the original produces _v3 (not a duplicate _v2).
    second = client.post(f"datasets/{did}/apply-transform", json=payload).json()
    assert second["dataset"]["name"] == "passengers_v3.csv"


def test_apply_transform_bad_column_returns_400(client):
    pid = _make_project(client)
    did = _upload_sample(client, pid)
    resp = client.post(
        f"datasets/{did}/apply-transform",
        json={"transform": "drop_column", "columns": ["does_not_exist"]},
    )
    assert resp.status_code == 400


def test_apply_transform_on_missing_dataset_404(client):
    resp = client.post(
        "datasets/99999/apply-transform",
        json={"transform": "drop_column", "columns": ["x"]},
    )
    assert resp.status_code == 404
