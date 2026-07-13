"""API routers, grouped by resource.

    projects  -- workspace CRUD
    datasets  -- CSV upload / list / preview / delete
    analysis  -- the 9 engine endpoints for a dataset
    sessions  -- analysis session history and re-runs
"""

from __future__ import annotations

from api.routers import analysis, datasets, projects, sessions

__all__ = ["projects", "datasets", "analysis", "sessions"]
