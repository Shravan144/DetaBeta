"""
Pydantic schemas: the validated shapes of API requests and responses.

WHY SCHEMAS?
------------
FastAPI uses these classes to (a) validate incoming JSON, (b) auto-generate the
interactive /docs page, and (c) serialize database rows into clean responses.
They are the *contract* between the backend and any frontend.

Note we only define schemas for the small, structured objects (projects,
datasets). The big engine outputs are already plain JSON dicts coming out of
the service layer, so we type those responses loosely as `dict`.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    """Body for creating a project."""

    name: str = Field(min_length=1, max_length=200, examples=["Titanic study"])
    description: str = Field(default="", max_length=5000)


class ProjectOut(BaseModel):
    """A project as returned to the client."""

    # from_attributes lets Pydantic read straight off a SQLAlchemy model object.
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    created_at: datetime
    dataset_count: int = 0


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------

class DatasetOut(BaseModel):
    """A dataset (uploaded CSV) as returned to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    n_rows: int
    n_columns: int
    created_at: datetime


class DatasetPreview(BaseModel):
    """A small peek at a dataset's contents for the UI."""

    id: int
    name: str
    n_rows: int
    n_columns: int
    columns: list[str]
    rows: list[dict]  # first N rows as records


class ApplyTransformRequest(BaseModel):
    """Body for applying one Feature Lab recommendation to create a new version."""

    # A TransformType value, e.g. "log_transform" (validated by the applier).
    transform: str = Field(min_length=1, examples=["log_transform"])
    # Column(s) the recommendation targeted.
    columns: list[str] = Field(min_length=1)
    # The recommendation's evidence dict (clip bounds, thresholds, ...). Optional.
    evidence: dict = Field(default_factory=dict)
    # Optional human label for the change (used in notes/lineage).
    title: str | None = None


class HealthSnapshot(BaseModel):
    """A tiny before/after health reading so the UI can show the improvement."""

    score: float
    grade: str


class ApplyTransformResult(BaseModel):
    """Result of applying a transform: the new dataset version + what changed."""

    dataset: DatasetOut               # the newly created dataset version
    changes: list[str]                # human-readable change notes
    health_before: HealthSnapshot
    health_after: HealthSnapshot


# ---------------------------------------------------------------------------
# Analysis sessions & cached engine results
# ---------------------------------------------------------------------------

class SessionOut(BaseModel):
    """An analysis session (one run over a dataset for a target), summarized."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    dataset_id: int
    # None for the target-independent "base" session (understand + health).
    target: str | None = None
    created_at: datetime
    # Which engines already have a cached result in this session.
    completed_engine_keys: list[str] = Field(default_factory=list)


class EngineResultOut(BaseModel):
    """A single engine's cached result inside a session (with parsed output)."""

    model_config = ConfigDict(from_attributes=True)

    engine_key: str
    status: str
    duration_ms: int | None = None
    error: str | None = None
    created_at: datetime
    # The parsed engine output. Loosely typed like the analysis responses.
    result: dict = Field(default_factory=dict)


class SessionDetailOut(SessionOut):
    """A session plus the full cached results of every engine that has run."""

    results: list[EngineResultOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

class Message(BaseModel):
    """A simple {'message': ...} response, e.g. after a delete."""

    message: str
