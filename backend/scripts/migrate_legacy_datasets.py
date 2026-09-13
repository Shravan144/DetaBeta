"""Safely copy local-era dataset files into the configured Supabase bucket.

Run from the backend directory:
    python scripts/migrate_legacy_datasets.py           # inspect only
    python scripts/migrate_legacy_datasets.py --apply   # copy + update metadata

The command intentionally never removes local source files.  Re-running it is
safe: already-migrated ``projects/...`` keys are skipped.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from dotenv import load_dotenv
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

# Loading before importing db/storage makes the command behave like FastAPI.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))
load_dotenv(_BACKEND_ROOT.parent / ".env")

from db import Dataset, Project, SessionLocal  # noqa: E402
from services import storage  # noqa: E402


class DestinationStorage(Protocol):
    def save_csv_bytes(self, project_id: int, filename: str, data: bytes) -> tuple[str, int, int]: ...


@dataclass
class MigrationSummary:
    candidates: list[int] = field(default_factory=list)
    migrated: list[int] = field(default_factory=list)
    failed: list[int] = field(default_factory=list)
    error_types: dict[int, str] = field(default_factory=dict)


def _is_legacy_key(key: str) -> bool:
    """Old local objects use ``<numeric project id>/<filename>`` keys."""
    parts = Path(key.replace("\\", "/")).parts
    return len(parts) >= 2 and parts[0].isdigit() and not key.startswith("projects/")


def _legacy_file(root: Path, key: str) -> Path:
    """Resolve a legacy key without allowing it to escape the local root."""
    root = root.resolve()
    candidate = (root / key).resolve()
    if root not in candidate.parents:
        raise ValueError("Legacy storage path is outside STORAGE_ROOT.")
    return candidate


def _source_storage_root(configured_root: Path, project_root: Path) -> Path:
    """Resolve a relative STORAGE_ROOT from the repository, not the shell CWD."""
    return configured_root if configured_root.is_absolute() else project_root / configured_root


def migrate_legacy_datasets(
    source_db: Session,
    destination_db: Session,
    source_root: Path,
    destination: DestinationStorage,
    *,
    apply: bool = False,
) -> MigrationSummary:
    """Copy local projects/objects into cloud metadata after each upload succeeds."""
    summary = MigrationSummary()
    rows = source_db.scalars(select(Dataset).order_by(Dataset.id)).all()
    projects: dict[int, Project] = {}

    for source_dataset in rows:
        if not _is_legacy_key(source_dataset.storage_path):
            continue
        summary.candidates.append(source_dataset.id)
        if not apply:
            continue
        try:
            target_project = projects.get(source_dataset.project_id)
            if target_project is None:
                source_project = source_db.get(Project, source_dataset.project_id)
                if source_project is None:
                    raise ValueError("Dataset has no source project.")
                user_match = (
                    Project.user_id.is_(None)
                    if source_project.user_id is None
                    else Project.user_id == source_project.user_id
                )
                target_project = destination_db.scalar(
                    select(Project).where(
                        Project.name == source_project.name,
                        Project.description == source_project.description,
                        user_match,
                    )
                )
                if target_project is None:
                    target_project = Project(
                        name=source_project.name,
                        description=source_project.description,
                        user_id=source_project.user_id,
                        created_at=source_project.created_at,
                    )
                    destination_db.add(target_project)
                    destination_db.flush()
                projects[source_dataset.project_id] = target_project

            existing = destination_db.scalar(
                select(Dataset).where(
                    Dataset.project_id == target_project.id,
                    Dataset.name == source_dataset.name,
                    Dataset.n_rows == source_dataset.n_rows,
                    Dataset.n_columns == source_dataset.n_columns,
                    Dataset.created_at == source_dataset.created_at,
                )
            )
            if existing is not None:
                summary.migrated.append(source_dataset.id)
                continue

            raw = _legacy_file(source_root, source_dataset.storage_path).read_bytes()
            cloud_key, _, _ = destination.save_csv_bytes(
                target_project.id, source_dataset.name, raw
            )
            destination_db.add(
                Dataset(
                    project_id=target_project.id,
                    name=source_dataset.name,
                    storage_path=cloud_key,
                    n_rows=source_dataset.n_rows,
                    n_columns=source_dataset.n_columns,
                    created_at=source_dataset.created_at,
                )
            )
            destination_db.commit()
            summary.migrated.append(source_dataset.id)
        except Exception as exc:  # Preserve local metadata and move on to the next row.
            destination_db.rollback()
            projects.pop(source_dataset.project_id, None)
            summary.failed.append(source_dataset.id)
            summary.error_types[source_dataset.id] = type(exc).__name__
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Copy files and update database rows.")
    parser.add_argument(
        "--source-database-url",
        default=f"sqlite:///{Path(tempfile.gettempdir()) / 'detabeta.db'}",
        help="SQLite URL containing pre-Supabase project and dataset metadata.",
    )
    args = parser.parse_args()

    source_engine = create_engine(args.source_database_url)
    source_db = sessionmaker(bind=source_engine)()
    destination_db = SessionLocal()
    try:
        destination = storage._supabase_storage_from_environment()
        summary = migrate_legacy_datasets(
            source_db,
            destination_db,
            _source_storage_root(storage.STORAGE_ROOT, _BACKEND_ROOT.parent),
            destination,
            apply=args.apply,
        )
    finally:
        source_db.close()
        destination_db.close()

    action = "Processed" if args.apply else "Would process"
    print(f"{action} {len(summary.candidates)} legacy dataset candidate(s).")
    if summary.migrated:
        print("Migrated ids: " + ", ".join(map(str, summary.migrated)))
    if summary.failed:
        print("Failed ids: " + ", ".join(map(str, summary.failed)))
        print(
            "Failure categories: "
            + ", ".join(f"{dataset_id}={kind}" for dataset_id, kind in summary.error_types.items())
        )
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
