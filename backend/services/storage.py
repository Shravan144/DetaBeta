"""
File storage for uploaded CSVs.

WHY A SEPARATE LAYER?
---------------------
The database stores *metadata* about a dataset (name, shape, path). The actual
bytes of the CSV live on disk. This module is the single owner of that folder:
it decides where files go, saves them, loads them back as DataFrames, and
deletes them. Routes and other services never build file paths by hand.

In development everything lives under `backend/storage/`. Swapping this for S3
or Vercel Blob later means changing only this one file.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd

# Root folder for all stored files. Defaults to a folder in the system temp dir
# (/tmp) because that is reliably writable under Vercel's services runtime and
# in serverless deployments. Overridable via the STORAGE_ROOT env var (and for
# tests, which point it at a throwaway folder).
STORAGE_ROOT = Path(os.environ.get("STORAGE_ROOT", Path(tempfile.gettempdir()) / "detabeta_storage"))


def _project_dir(project_id: int) -> Path:
    """Folder that holds one project's files, created on demand."""
    d = STORAGE_ROOT / str(project_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_csv_bytes(project_id: int, filename: str, data: bytes) -> tuple[str, int, int]:
    """Persist raw uploaded bytes as a CSV and report its shape.

    Returns a tuple of (relative_storage_path, n_rows, n_columns).

    We validate that the bytes actually parse as a CSV *before* committing
    anything to the database, so we never end up with a Dataset row pointing at
    an unreadable file. Raises ValueError on a bad/empty CSV.
    """
    safe_name = _safe_filename(filename)
    dest = _project_dir(project_id) / safe_name

    # Write the bytes first, then try to parse. If parsing fails we remove the
    # file and raise, leaving no orphan behind.
    dest.write_bytes(data)
    try:
        df = pd.read_csv(dest)
    except Exception as exc:  # noqa: BLE001 - we re-raise as a clean ValueError
        dest.unlink(missing_ok=True)
        raise ValueError(f"Uploaded file is not a readable CSV: {exc}") from exc

    if df.shape[1] == 0 or df.shape[0] == 0:
        dest.unlink(missing_ok=True)
        raise ValueError("CSV parsed but contains no rows/columns.")

    rel_path = f"{project_id}/{safe_name}"
    return rel_path, int(df.shape[0]), int(df.shape[1])


def load_dataframe(storage_path: str) -> pd.DataFrame:
    """Load a stored CSV back into a pandas DataFrame.

    `storage_path` is the relative path we saved on the Dataset row
    (e.g. "3/passengers.csv"). Raises FileNotFoundError if it is missing.
    """
    full = STORAGE_ROOT / storage_path
    if not full.exists():
        raise FileNotFoundError(f"Stored dataset not found: {storage_path}")
    return pd.read_csv(full)


def delete_file(storage_path: str) -> None:
    """Remove a stored CSV. Silent if it is already gone."""
    (STORAGE_ROOT / storage_path).unlink(missing_ok=True)


def _safe_filename(filename: str) -> str:
    """Strip any directory components so an upload can't escape its folder.

    e.g. "../../etc/passwd" -> "passwd". A tiny but important guard against
    path-traversal via a malicious filename.
    """
    name = os.path.basename(filename or "").strip()
    if not name:
        return "dataset.csv"
    if not name.lower().endswith(".csv"):
        name += ".csv"
    return name
