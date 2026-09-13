"""Safety tests for moving pre-Supabase dataset objects to private storage."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db import Base, Dataset, Project
from scripts.migrate_legacy_datasets import _source_storage_root, migrate_legacy_datasets


class FakeDestination:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.writes: list[tuple[int, str, bytes]] = []

    def save_csv_bytes(self, project_id: int, filename: str, data: bytes):
        if self.fail:
            raise RuntimeError("bucket unavailable")
        self.writes.append((project_id, filename, data))
        return (f"projects/{project_id}/cloud_{filename}", 1, 1)


def test_relative_storage_root_is_resolved_from_project_root(tmp_path):
    project_root = tmp_path / "project"

    assert _source_storage_root(Path("backend/storage"), project_root) == project_root / "backend" / "storage"


def _source_and_destination_sessions(tmp_path: Path):
    source_root = tmp_path / "legacy-storage"
    legacy_path = source_root / "2" / "sales.csv"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_bytes(b"amount\n10\n")

    source_engine = create_engine(f"sqlite:///{tmp_path / 'legacy-metadata.db'}")
    destination_engine = create_engine(f"sqlite:///{tmp_path / 'cloud-metadata.db'}")
    Base.metadata.create_all(source_engine)
    Base.metadata.create_all(destination_engine)
    session = sessionmaker(bind=source_engine)()
    project = Project(name="Legacy project", description="", user_id="legacy-user")
    session.add(project)
    session.flush()
    dataset = Dataset(
        project_id=project.id,
        name="sales.csv",
        storage_path="2/sales.csv",
        n_rows=1,
        n_columns=1,
    )
    session.add(dataset)
    session.commit()
    return session, sessionmaker(bind=destination_engine)(), source_root, dataset.id


def test_dry_run_reports_legacy_dataset_without_writing_or_updating(tmp_path):
    source_db, destination_db, source_root, dataset_id = _source_and_destination_sessions(tmp_path)
    destination = FakeDestination()

    summary = migrate_legacy_datasets(source_db, destination_db, source_root, destination, apply=False)

    assert summary.candidates == [dataset_id]
    assert summary.migrated == []
    assert destination.writes == []
    assert source_db.get(Dataset, dataset_id).storage_path == "2/sales.csv"
    assert destination_db.query(Project).count() == 0


def test_apply_copies_file_before_updating_storage_path(tmp_path):
    source_db, destination_db, source_root, dataset_id = _source_and_destination_sessions(tmp_path)
    destination = FakeDestination()

    summary = migrate_legacy_datasets(source_db, destination_db, source_root, destination, apply=True)

    assert summary.migrated == [dataset_id]
    assert destination.writes == [(1, "sales.csv", b"amount\n10\n")]
    copied_project = destination_db.query(Project).one()
    copied_dataset = destination_db.query(Dataset).one()
    assert copied_project.name == "Legacy project"
    assert copied_project.user_id == "legacy-user"
    assert copied_dataset.project_id == copied_project.id
    assert copied_dataset.storage_path == "projects/1/cloud_sales.csv"
    assert (source_root / "2" / "sales.csv").exists()


def test_failed_upload_keeps_original_metadata_and_file(tmp_path):
    source_db, destination_db, source_root, dataset_id = _source_and_destination_sessions(tmp_path)

    summary = migrate_legacy_datasets(source_db, destination_db, source_root, FakeDestination(fail=True), apply=True)

    assert summary.failed == [dataset_id]
    assert source_db.get(Dataset, dataset_id).storage_path == "2/sales.csv"
    assert destination_db.query(Project).count() == 0
    assert (source_root / "2" / "sales.csv").exists()
