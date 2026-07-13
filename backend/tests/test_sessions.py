"""
Tests for the persistence + analysis-session layer.

These exercise the caching behavior end-to-end through the HTTP API (with an
isolated temp DB and storage folder, exactly like test_api.py):

    * an engine runs once, then is served from cache (X-DetaBeta-Cached header)
    * ?refresh=true recomputes and overwrites the cached result
    * target-independent engines (understand, health) are shared across the
      base session and every target-specific session
    * picking a target creates a distinct session from the base one
    * re-run creates a NEW session version while preserving history
    * required-target 400s are NOT cached
    * session detail returns the full cached engine output
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

    main.app.dependency_overrides[get_db] = _override_get_db
    monkeypatch.setattr(storage, "STORAGE_ROOT", tmp_path / "storage")

    with TestClient(main.app) as c:
        yield c

    main.app.dependency_overrides.clear()


@pytest.fixture()
def dataset_id(client) -> int:
    """Create a project and upload the sample CSV, returning the dataset id."""
    pid = client.post("projects", json={"name": "Titanic study"}).json()["id"]
    with open(_SAMPLE_CSV, "rb") as fh:
        resp = client.post(
            f"projects/{pid}/datasets",
            files={"file": ("passengers.csv", fh, "text/csv")},
        )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Lazy per-engine caching
# ---------------------------------------------------------------------------

def test_engine_result_is_cached_on_second_call(client, dataset_id):
    first = client.get(f"datasets/{dataset_id}/analysis/understand")
    assert first.status_code == 200
    assert first.headers["X-DetaBeta-Cached"] == "false"

    second = client.get(f"datasets/{dataset_id}/analysis/understand")
    assert second.status_code == 200
    assert second.headers["X-DetaBeta-Cached"] == "true"
    # Same session, identical payload served from the DB.
    assert first.headers["X-DetaBeta-Session-Id"] == second.headers["X-DetaBeta-Session-Id"]
    assert first.json() == second.json()


def test_refresh_recomputes(client, dataset_id):
    client.get(f"datasets/{dataset_id}/analysis/health")
    cached = client.get(f"datasets/{dataset_id}/analysis/health")
    assert cached.headers["X-DetaBeta-Cached"] == "true"

    refreshed = client.get(f"datasets/{dataset_id}/analysis/health?refresh=true")
    assert refreshed.status_code == 200
    assert refreshed.headers["X-DetaBeta-Cached"] == "false"
    # Same (active) session, just recomputed.
    assert refreshed.headers["X-DetaBeta-Session-Id"] == cached.headers["X-DetaBeta-Session-Id"]


# ---------------------------------------------------------------------------
# Target-independent reuse & session-per-target
# ---------------------------------------------------------------------------

def test_target_independent_engine_shared_across_targets(client, dataset_id):
    # 'understand' ignores the target, so it lives in the base session and is
    # reused even when a target is supplied.
    base = client.get(f"datasets/{dataset_id}/analysis/understand")
    base_session = base.headers["X-DetaBeta-Session-Id"]

    with_target = client.get(f"datasets/{dataset_id}/analysis/understand?target=survived")
    assert with_target.headers["X-DetaBeta-Cached"] == "true"
    assert with_target.headers["X-DetaBeta-Session-Id"] == base_session


def test_target_engine_uses_distinct_session(client, dataset_id):
    base = client.get(f"datasets/{dataset_id}/analysis/understand")
    base_session = base.headers["X-DetaBeta-Session-Id"]

    modelling = client.get(f"datasets/{dataset_id}/analysis/experiment?target=survived")
    assert modelling.status_code == 200
    # Target-specific engine must not share the base (target=None) session.
    assert modelling.headers["X-DetaBeta-Session-Id"] != base_session


def test_different_targets_get_different_sessions(client, dataset_id):
    a = client.get(f"datasets/{dataset_id}/analysis/recommend?target=survived")
    b = client.get(f"datasets/{dataset_id}/analysis/recommend?target=sex")
    assert a.status_code == 200 and b.status_code == 200
    assert a.headers["X-DetaBeta-Session-Id"] != b.headers["X-DetaBeta-Session-Id"]


# ---------------------------------------------------------------------------
# History listing & re-run
# ---------------------------------------------------------------------------

def test_list_and_active_session(client, dataset_id):
    client.get(f"datasets/{dataset_id}/analysis/understand")

    active = client.get(f"datasets/{dataset_id}/sessions/active")
    assert active.status_code == 200
    assert "understand" in active.json()["completed_engine_keys"]

    listing = client.get(f"datasets/{dataset_id}/sessions").json()
    assert len(listing) >= 1


def test_rerun_creates_new_version_preserving_history(client, dataset_id):
    client.get(f"datasets/{dataset_id}/analysis/understand")
    active_before = client.get(f"datasets/{dataset_id}/sessions/active").json()

    rerun = client.post(f"datasets/{dataset_id}/sessions/rerun")
    assert rerun.status_code == 201
    new_id = rerun.json()["id"]
    assert new_id != active_before["id"]
    # The fresh session has no cached engines yet.
    assert rerun.json()["completed_engine_keys"] == []

    # History still contains the old session too.
    ids = {s["id"] for s in client.get(f"datasets/{dataset_id}/sessions").json()}
    assert {active_before["id"], new_id} <= ids

    # The new session is now active and re-runs the engine fresh.
    after = client.get(f"datasets/{dataset_id}/analysis/understand")
    assert after.headers["X-DetaBeta-Cached"] == "false"
    assert after.headers["X-DetaBeta-Session-Id"] == str(new_id)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_missing_required_target_not_cached(client, dataset_id):
    # A bad request must 400 and must NOT create a cached (failed) result.
    assert client.get(f"datasets/{dataset_id}/analysis/experiment").status_code == 400

    # The base session should have no 'experiment' result recorded.
    active = client.get(f"datasets/{dataset_id}/sessions/active").json()
    assert "experiment" not in active["completed_engine_keys"]


def test_session_detail_returns_full_results(client, dataset_id):
    resp = client.get(f"datasets/{dataset_id}/analysis/understand")
    session_id = resp.headers["X-DetaBeta-Session-Id"]

    detail = client.get(f"sessions/{session_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == int(session_id)
    understand_results = [r for r in body["results"] if r["engine_key"] == "understand"]
    assert len(understand_results) == 1
    assert understand_results[0]["status"] == "completed"
    assert isinstance(understand_results[0]["result"], dict) and understand_results[0]["result"]


def test_session_detail_404(client):
    assert client.get("sessions/99999").status_code == 404
