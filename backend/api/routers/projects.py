"""
Projects router: create, list, read, and delete workspaces.

A Project is just a named container for datasets. These endpoints are plain
database CRUD -- no engines involved.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_project_or_404
from api.schemas import Message, ProjectCreate, ProjectOut
from db import Project, get_db
from services import storage

# NOTE: no "/api" prefix here. In the deployed multi-service setup, Vercel
# routes "/api/*" to this backend and STRIPS the "/api" prefix before
# forwarding, so the backend must define routes without it. The browser still
# calls "/api/projects"; the backend sees "/projects".
router = APIRouter(prefix="/projects", tags=["projects"])


def _to_out(project: Project) -> ProjectOut:
    """Attach the dataset count, which the UI shows on project cards."""
    out = ProjectOut.model_validate(project)
    out.dataset_count = len(project.datasets)
    return out


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)) -> ProjectOut:
    """Create a new project."""
    project = Project(name=body.name, description=body.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return _to_out(project)


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)) -> list[ProjectOut]:
    """List all projects, newest first."""
    projects = db.scalars(select(Project).order_by(Project.created_at.desc())).all()
    return [_to_out(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project: Project = Depends(get_project_or_404)) -> ProjectOut:
    """Fetch a single project by id."""
    return _to_out(project)


@router.delete("/{project_id}", response_model=Message)
def delete_project(
    project: Project = Depends(get_project_or_404), db: Session = Depends(get_db)
) -> Message:
    """Delete a project, its dataset rows (via cascade), and their files."""
    # Remove the files from disk first; the DB cascade handles the rows.
    for dataset in project.datasets:
        storage.delete_file(dataset.storage_path)
    db.delete(project)
    db.commit()
    return Message(message=f"Project {project.id} deleted.")
