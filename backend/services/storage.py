"""Durable, private storage for uploaded CSV datasets."""

from __future__ import annotations

import io
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

import pandas as pd


STORAGE_ROOT = Path(
    os.environ.get("STORAGE_ROOT", Path(tempfile.gettempdir()) / "detabeta_storage")
)


def _safe_filename(filename: str) -> str:
    """Strip directory components and ensure a CSV extension."""
    name = os.path.basename(filename or "").strip()
    if not name:
        return "dataset.csv"
    return name if name.lower().endswith(".csv") else f"{name}.csv"


def _storage_key(project_id: int, filename: str) -> str:
    """Return an opaque non-colliding key, independent of the display name."""
    return f"projects/{project_id}/{uuid.uuid4().hex}_{_safe_filename(filename)}"


def _parse_csv(data: bytes) -> pd.DataFrame:
    """Validate a non-empty CSV before persisting it."""
    try:
        dataframe = pd.read_csv(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001 - turn parser details into an API validation error
        raise ValueError(f"Uploaded file is not a readable CSV: {exc}") from exc
    if dataframe.shape[0] == 0 or dataframe.shape[1] == 0:
        raise ValueError("CSV parsed but contains no rows/columns.")
    return dataframe


class LocalDatasetStorage:
    """Filesystem adapter for tests and offline development."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def save_csv_bytes(self, project_id: int, filename: str, data: bytes) -> tuple[str, int, int]:
        dataframe = _parse_csv(data)
        key = _storage_key(project_id, filename)
        destination = self.root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return key, int(dataframe.shape[0]), int(dataframe.shape[1])

    def save_dataframe(
        self, project_id: int, filename: str, dataframe: pd.DataFrame
    ) -> tuple[str, int, int]:
        key = _storage_key(project_id, filename)
        destination = self.root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        dataframe.to_csv(destination, index=False)
        return key, int(dataframe.shape[0]), int(dataframe.shape[1])

    def load_dataframe(self, storage_path: str) -> pd.DataFrame:
        path = self.root / storage_path
        if not path.exists():
            raise FileNotFoundError(f"Stored dataset not found: {storage_path}")
        return pd.read_csv(path)

    def delete_file(self, storage_path: str) -> None:
        (self.root / storage_path).unlink(missing_ok=True)


class SupabaseDatasetStorage:
    """Private Supabase Storage adapter; it stores keys, never public URLs."""

    def __init__(self, client: Any, bucket_name: str) -> None:
        self.bucket = client.storage.from_(bucket_name)

    def save_csv_bytes(self, project_id: int, filename: str, data: bytes) -> tuple[str, int, int]:
        dataframe = _parse_csv(data)
        key = _storage_key(project_id, filename)
        self.bucket.upload(
            path=key,
            file=data,
            file_options={"content-type": "text/csv", "upsert": "false"},
        )
        return key, int(dataframe.shape[0]), int(dataframe.shape[1])

    def save_dataframe(
        self, project_id: int, filename: str, dataframe: pd.DataFrame
    ) -> tuple[str, int, int]:
        key = _storage_key(project_id, filename)
        self.bucket.upload(
            path=key,
            file=dataframe.to_csv(index=False).encode("utf-8"),
            file_options={"content-type": "text/csv", "upsert": "false"},
        )
        return key, int(dataframe.shape[0]), int(dataframe.shape[1])

    def load_dataframe(self, storage_path: str) -> pd.DataFrame:
        try:
            data = self.bucket.download(storage_path)
        except Exception as exc:  # noqa: BLE001 - normalize both adapters to FileNotFoundError
            raise FileNotFoundError(f"Stored dataset not found: {storage_path}") from exc
        return pd.read_csv(io.BytesIO(data))

    def delete_file(self, storage_path: str) -> None:
        try:
            self.bucket.remove([storage_path])
        except Exception:  # deleting a missing object is intentionally idempotent
            return


def _supabase_storage_from_environment() -> SupabaseDatasetStorage:
    """Create a server-only Supabase client after validating configuration."""
    url = os.environ.get("SUPABASE_URL", "").strip()
    secret_key = (
        os.environ.get("SUPABASE_SECRET_KEY", "").strip()
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )
    bucket = os.environ.get("SUPABASE_STORAGE_BUCKET", "datasets").strip()
    missing = [
        name
        for name, value in {
            "SUPABASE_URL": url,
            "SUPABASE_SECRET_KEY": secret_key,
            "SUPABASE_STORAGE_BUCKET": bucket,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError("Supabase storage is enabled but missing: " + ", ".join(missing))

    try:
        from supabase import create_client
    except ImportError as exc:  # pragma: no cover - the package is declared below
        raise RuntimeError("Supabase storage requires the 'supabase' package.") from exc
    return SupabaseDatasetStorage(create_client(url, secret_key), bucket)


def _active_storage() -> LocalDatasetStorage | SupabaseDatasetStorage:
    backend = os.environ.get("STORAGE_BACKEND", "local").strip().lower()
    if backend in ("", "local"):
        return LocalDatasetStorage(STORAGE_ROOT)
    if backend == "supabase":
        return _supabase_storage_from_environment()
    raise RuntimeError(f"Unsupported STORAGE_BACKEND={backend!r}. Use 'local' or 'supabase'.")


def save_csv_bytes(project_id: int, filename: str, data: bytes) -> tuple[str, int, int]:
    """Persist validated upload bytes and return (object key, rows, columns)."""
    return _active_storage().save_csv_bytes(project_id, filename, data)


def save_dataframe(
    project_id: int, filename: str, dataframe: pd.DataFrame
) -> tuple[str, int, int]:
    """Persist a derived dataframe as a new immutable dataset object."""
    return _active_storage().save_dataframe(project_id, filename, dataframe)


def load_dataframe(storage_path: str) -> pd.DataFrame:
    """Load a dataframe from the currently selected storage adapter."""
    return _active_storage().load_dataframe(storage_path)


def delete_file(storage_path: str) -> None:
    """Delete one dataset object; repeated deletion is safe."""
    _active_storage().delete_file(storage_path)
