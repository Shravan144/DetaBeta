"""Tests for backend JWT authentication.

Covers: valid tokens, expired tokens, wrong issuer, wrong audience, missing
header, missing secret, and short secret.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import main
from db import AnalysisSession, Base, Dataset, Project, get_db
from services import storage

_SECRET = "test-secret-that-is-at-least-32-chars-long!!"
_ISSUER = "detabeta-frontend"
_AUDIENCE = "detabeta-api"


def _make_token(
    sub: str = "test-user-1",
    email: str = "test@detabeta.local",
    name: str = "Test User",
    secret: str = _SECRET,
    issuer: str = _ISSUER,
    audience: str = _AUDIENCE,
    exp_offset: int = 600,
) -> str:
    """Create a signed JWT for testing."""
    now = int(time.time())
    payload = {
        "sub": sub,
        "email": email,
        "name": name,
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + exp_offset,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A TestClient wired to a throwaway SQLite and temp storage."""
    monkeypatch.setenv("BACKEND_JWT_SECRET", _SECRET)

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
        c.app.state.test_session_factory = TestSession
        yield c

    main.app.dependency_overrides.clear()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_valid_token_accepted(client):
    token = _make_token()
    resp = client.post(
        "projects",
        json={"name": "Auth Test"},
        headers=_auth(token),
    )
    assert resp.status_code == 201


def test_missing_auth_header_returns_401(client):
    resp = client.post("projects", json={"name": "No Auth"})
    assert resp.status_code == 401


def test_expired_token_returns_401(client):
    token = _make_token(exp_offset=-60)  # expired 1 minute ago
    resp = client.post("projects", json={"name": "Expired"}, headers=_auth(token))
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower()


def test_wrong_issuer_returns_401(client):
    token = _make_token(issuer="wrong-issuer")
    resp = client.post("projects", json={"name": "Wrong Issuer"}, headers=_auth(token))
    assert resp.status_code == 401


def test_wrong_audience_returns_401(client):
    token = _make_token(audience="wrong-audience")
    resp = client.post("projects", json={"name": "Wrong Audience"}, headers=_auth(token))
    assert resp.status_code == 401


def test_invalid_jwt_returns_401(client):
    resp = client.post(
        "projects",
        json={"name": "Bad Token"},
        headers=_auth("not-a-real-jwt"),
    )
    assert resp.status_code == 401


def test_wrong_secret_returns_401(client):
    token = _make_token(secret="different-secret-that-is-also-long-enough!!")
    resp = client.post("projects", json={"name": "Wrong Secret"}, headers=_auth(token))
    assert resp.status_code == 401


def test_missing_secret_returns_503(client, monkeypatch):
    monkeypatch.delenv("BACKEND_JWT_SECRET", raising=False)
    token = _make_token()
    resp = client.post("projects", json={"name": "No Secret"}, headers=_auth(token))
    assert resp.status_code == 503


def test_short_secret_returns_503(client, monkeypatch):
    monkeypatch.setenv("BACKEND_JWT_SECRET", "short")
    token = _make_token()
    resp = client.post("projects", json={"name": "Short Secret"}, headers=_auth(token))
    assert resp.status_code == 503


# --- User isolation tests ---

def test_user_cannot_see_other_users_project(client):
    token_a = _make_token(sub="user-a", email="a@test.com")
    token_b = _make_token(sub="user-b", email="b@test.com")

    # User A creates a project
    resp = client.post("projects", json={"name": "A's Project"}, headers=_auth(token_a))
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    # User A can see it
    assert client.get(f"projects/{project_id}", headers=_auth(token_a)).status_code == 200

    # User B gets 404
    assert client.get(f"projects/{project_id}", headers=_auth(token_b)).status_code == 404


def test_user_list_only_own_projects(client):
    token_a = _make_token(sub="user-a", email="a@test.com")
    token_b = _make_token(sub="user-b", email="b@test.com")

    client.post("projects", json={"name": "A's Project"}, headers=_auth(token_a))
    client.post("projects", json={"name": "B's Project"}, headers=_auth(token_b))

    a_projects = client.get("projects", headers=_auth(token_a)).json()
    b_projects = client.get("projects", headers=_auth(token_b)).json()

    assert len(a_projects) == 1
    assert a_projects[0]["name"] == "A's Project"
    assert len(b_projects) == 1
    assert b_projects[0]["name"] == "B's Project"


def test_user_cannot_delete_other_users_project(client):
    token_a = _make_token(sub="user-a", email="a@test.com")
    token_b = _make_token(sub="user-b", email="b@test.com")

    resp = client.post("projects", json={"name": "A's Project"}, headers=_auth(token_a))
    project_id = resp.json()["id"]

    # User B tries to delete A's project -> 404
    assert client.delete(f"projects/{project_id}", headers=_auth(token_b)).status_code == 404
    # It still exists for User A
    assert client.get(f"projects/{project_id}", headers=_auth(token_a)).status_code == 200


def test_legacy_unowned_project_is_not_exposed_to_authenticated_users(client):
    """Rows awaiting an explicit ownership migration must stay private."""
    db = client.app.state.test_session_factory()
    try:
        project = Project(name="Unclaimed legacy project", description="", user_id=None)
        db.add(project)
        db.commit()
        db.refresh(project)
        project_id = project.id
    finally:
        db.close()

    token = _make_token(sub="unrelated-user")
    listed = client.get("projects", headers=_auth(token))
    fetched = client.get(f"projects/{project_id}", headers=_auth(token))

    assert listed.status_code == 200
    assert all(item["id"] != project_id for item in listed.json())
    assert fetched.status_code == 404


def test_legacy_unowned_project_session_is_not_exposed(client):
    """Direct session lookup must enforce the same strict ownership rule."""
    db = client.app.state.test_session_factory()
    try:
        project = Project(name="Unclaimed legacy project", description="", user_id=None)
        db.add(project)
        db.flush()
        dataset = Dataset(
            project_id=project.id,
            name="legacy.csv",
            storage_path="legacy.csv",
            n_rows=1,
            n_columns=1,
        )
        db.add(dataset)
        db.flush()
        session = AnalysisSession(dataset_id=dataset.id, target=None)
        db.add(session)
        db.commit()
        db.refresh(session)
        session_id = session.id
    finally:
        db.close()

    token = _make_token(sub="unrelated-user")
    response = client.get(f"sessions/{session_id}", headers=_auth(token))

    assert response.status_code == 404
