"""
Datasets router: upload CSVs into a project, list them, preview, and delete.

Uploading is the one endpoint that writes a file to disk (via the storage
service) *and* a row to the database. We do the file save first so that if the
CSV is unreadable we reject the request before creating any DB row.
"""

from __future__ import annotations

import re

import pandas as pd
from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_dataset_or_404, get_project_or_404
from api.schemas import (
    ApplyTransformRequest,
    ApplyTransformResult,
    DatasetOut,
    DatasetPreview,
    HealthSnapshot,
    Message,
)
from db import Dataset, Project, get_db
from engines.data_health import assess_health
from engines.feature_lab import TransformError, apply_transform
from services import storage
from services.serialization import to_jsonable

# NOTE: routes here are defined WITHOUT the "/api" prefix. Vercel strips "/api"
# before forwarding to this backend service (see vercel.json routePrefix), so
# the browser calls "/api/datasets/1" and the backend sees "/datasets/1".
router = APIRouter(tags=["datasets"])

# How many rows to include in a preview.
_PREVIEW_ROWS = 10


@router.post(
    "/projects/{project_id}/datasets",
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


def _next_version_name(source_name: str, existing_names: set[str]) -> str:
    """Pick the next 'name_vN.csv' that isn't already used in the project.

    'passengers.csv' -> 'passengers_v2.csv'; applying again -> '_v3', etc. We
    strip any existing '_vN' suffix first so versions of versions stay flat and
    readable instead of nesting ('passengers_v2_v2').
    """
    stem = source_name[:-4] if source_name.lower().endswith(".csv") else source_name
    base = re.sub(r"_v\d+$", "", stem)  # collapse an existing version suffix
    version = 2
    while f"{base}_v{version}.csv" in existing_names:
        version += 1
    return f"{base}_v{version}.csv"


@router.post(
    "/datasets/{dataset_id}/apply-transform",
    response_model=ApplyTransformResult,
    status_code=status.HTTP_201_CREATED,
)
def apply_transform_to_dataset(
    dataset: Dataset = Depends(get_dataset_or_404),
    body: ApplyTransformRequest = Body(...),
    db: Session = Depends(get_db),
) -> ApplyTransformResult:
    """Apply one Feature Lab recommendation, saving the result as a NEW version.

    Embodies DetaBeta's "recommend, don't force, never overwrite" rule: we read
    the source dataset, apply exactly one transform to a copy, and persist it as
    a new Dataset row. The raw evidence is preserved. We also measure the data
    health score before and after so the UI can show the improvement.
    """
    try:
        source_df = storage.load_dataframe(dataset.storage_path)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset.id} has no stored file.",
        ) from exc

    # Health BEFORE, so we can report the delta the transform produced.
    before = assess_health(source_df)

    try:
        new_df, changes = apply_transform(
            source_df, body.transform, body.columns, body.evidence
        )
    except TransformError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    after = assess_health(new_df)

    # Name the new version, avoiding collisions with existing datasets.
    existing = {
        n for (n,) in db.execute(
            select(Dataset.name).where(Dataset.project_id == dataset.project_id)
        ).all()
    }
    new_name = _next_version_name(dataset.name, existing)

    rel_path, n_rows, n_cols = storage.save_dataframe(
        dataset.project_id, new_name, new_df
    )
    new_dataset = Dataset(
        project_id=dataset.project_id,
        name=new_name,
        storage_path=rel_path,
        n_rows=n_rows,
        n_columns=n_cols,
    )
    db.add(new_dataset)
    db.commit()
    db.refresh(new_dataset)

    return ApplyTransformResult(
        dataset=DatasetOut.model_validate(new_dataset),
        changes=changes,
        health_before=HealthSnapshot(score=before.score, grade=before.grade),
        health_after=HealthSnapshot(score=after.score, grade=after.grade),
    )


@router.get("/projects/{project_id}/datasets", response_model=list[DatasetOut])
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


@router.get("/datasets/{dataset_id}", response_model=DatasetOut)
def get_dataset(dataset: Dataset = Depends(get_dataset_or_404)) -> DatasetOut:
    """Fetch a single dataset's metadata."""
    return DatasetOut.model_validate(dataset)


@router.get("/datasets/{dataset_id}/preview", response_model=DatasetPreview)
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


@router.delete("/datasets/{dataset_id}", response_model=Message)
def delete_dataset(
    dataset: Dataset = Depends(get_dataset_or_404), db: Session = Depends(get_db)
) -> Message:
    """Delete a dataset row and its stored file."""
    storage.delete_file(dataset.storage_path)
    db.delete(dataset)
    db.commit()
    return Message(message=f"Dataset {dataset.id} deleted.")
