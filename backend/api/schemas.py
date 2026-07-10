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


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

class Message(BaseModel):
    """A simple {'message': ...} response, e.g. after a delete."""

    message: str
