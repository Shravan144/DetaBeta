"""
Database models: the shape of what we store.

WHY ONLY TWO TABLES?
--------------------
Per our plan, the backend does NOT cache engine results. The engines are pure
functions that run on demand. So the only things worth persisting are:

  * Project  -- a workspace/folder that groups related work.
  * Dataset  -- one uploaded CSV file that belongs to a project.

That is enough to model your document's "Project" concept and to let the UI
list projects, list their datasets, and run analyses on a chosen dataset.

Everything the engines produce (profiles, health reports, model results...) is
computed fresh from the stored CSV each time it is requested.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.session import Base


def _utcnow() -> datetime:
    """Timezone-aware UTC timestamp. Stored on every row for ordering/history."""
    return datetime.now(timezone.utc)


class Project(Base):
    """A workspace that groups datasets together (e.g. 'Titanic study')."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    # One project has many datasets. `cascade="all, delete-orphan"` means
    # deleting a project also deletes its datasets (and their files, which we
    # handle in the service layer).
    datasets: Mapped[list["Dataset"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Dataset.created_at",
    )


class Dataset(Base):
    """One uploaded CSV file belonging to a project.

    We store *metadata* here (name, shape, where the file lives on disk), never
    the raw table contents. The actual CSV sits in the storage folder and is
    loaded into a pandas DataFrame only when an analysis runs.
    """

    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Human-facing name (original uploaded filename, e.g. "passengers.csv").
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Relative path inside the storage folder, e.g. "3/passengers.csv".
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)

    # Cached shape so the UI can show "20 rows x 8 columns" without re-reading
    # the file. These are cheap facts, not analysis results.
    n_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    n_columns: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="datasets")
