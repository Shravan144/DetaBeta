"""
Datasets router: upload CSVs into a project, list them, preview, and delete.

Uploading is the one endpoint that writes a file to disk (via the storage
service) *and* a row to the database. We do the file save first so that if the
CSV is unreadable we reject the request before creating any DB row.
"""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_dataset_or_404, get_project_or_404
from api.schemas import DatasetOut, DatasetPreview, Message
from db import Dataset, Project, get_db
from services import storage
from services.serialization import to_jsonable

router = APIRouter(tags=["datasets"])

# How many rows to include in a preview.
_PREVIEW_ROWS = 10


@router.post(
    "/api/projects/{project_id}/datasets",
    response_model=DatasetOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_dataset(
    project: Project = Depends(get_project_or_404),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DatasetOut:
    """Upload a CSV file into a project.

    Steps: read bytes -> save+validate as CSV (storage service) -> record a
    Dataset row with the parsed shape.
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty."
        )

    try:
        rel_path, n_rows, n_cols = storage.save_csv_bytes(
            project.id, file.filename or "dataset.csv", raw
        )
    except ValueError as exc:
        # Bad CSV -> 400 with the specific parse error.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    dataset = Dataset(
        project_id=project.id,
        name=file.filename or "dataset.csv",
        storage_path=rel_path,
        n_rows=n_rows,
        n_columns=n_cols,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return DatasetOut.model_validate(dataset)


@router.get("/api/projects/{project_id}/datasets", response_model=list[DatasetOut])
def list_datasets(
    project: Project = Depends(get_project_or_404), db: Session = Depends(get_db)
) -> list[DatasetOut]:
    """List all datasets in a project, newest first."""
    rows = db.scalars(
        select(Dataset)
        .where(Dataset.project_id == project.id)
        .order_by(Dataset.created_at.desc())
    ).all()
    return [DatasetOut.model_validate(d) for d in rows]


@router.get("/api/datasets/{dataset_id}", response_model=DatasetOut)
def get_dataset(dataset: Dataset = Depends(get_dataset_or_404)) -> DatasetOut:
    """Fetch a single dataset's metadata."""
    return DatasetOut.model_validate(dataset)


@router.get("/api/datasets/{dataset_id}/preview", response_model=DatasetPreview)
def preview_dataset(dataset: Dataset = Depends(get_dataset_or_404)) -> DatasetPreview:
    """Return the column names and first few rows for a UI table preview."""
    try:
        df = storage.load_dataframe(dataset.storage_path)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset.id} has no stored file.",
        ) from exc

    head = df.head(_PREVIEW_ROWS)
    # to_jsonable scrubs NaN/numpy so the preview is valid JSON.
    rows = to_jsonable(head.to_dict(orient="records"))
    return DatasetPreview(
        id=dataset.id,
        name=dataset.name,
        n_rows=int(df.shape[0]),
        n_columns=int(df.shape[1]),
        columns=[str(c) for c in df.columns],
        rows=rows,
    )


@router.delete("/api/datasets/{dataset_id}", response_model=Message)
def delete_dataset(
    dataset: Dataset = Depends(get_dataset_or_404), db: Session = Depends(get_db)
) -> Message:
    """Delete a dataset row and its stored file."""
    storage.delete_file(dataset.storage_path)
    db.delete(dataset)
    db.commit()
    return Message(message=f"Dataset {dataset.id} deleted.")
