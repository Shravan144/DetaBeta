"""
Reusable route dependencies.

These small helpers are shared by several routers. Keeping them here avoids
copy-pasting the same "fetch this row or return 404" logic into every endpoint.
"""

from __future__ import annotations

import pandas as pd
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from db import Dataset, Project, get_db
from services import storage


def get_project_or_404(project_id: int, db: Session = Depends(get_db)) -> Project:
    """Load a project by id or raise a clean 404."""
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found.",
        )
    return project


def get_dataset_or_404(dataset_id: int, db: Session = Depends(get_db)) -> Dataset:
    """Load a dataset by id or raise a clean 404."""
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found.",
        )
    return dataset


def load_dataset_df(dataset: Dataset = Depends(get_dataset_or_404)) -> pd.DataFrame:
    """Load a dataset's CSV into a DataFrame, or 404 if the file vanished.

    This composes on top of get_dataset_or_404: FastAPI resolves the dataset
    first, then hands it here. Analysis routes depend on this directly and
    receive a ready-to-use DataFrame.
    """
    try:
        return storage.load_dataframe(dataset.storage_path)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset.id} has no stored file.",
        ) from exc
