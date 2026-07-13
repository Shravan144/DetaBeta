"""
DetaBeta API -- application entry point.

This file assembles the whole backend:
  * creates the FastAPI app (with metadata that powers the /docs page),
  * enables CORS so a browser frontend can call it,
  * ensures the database tables exist on startup,
  * mounts the three routers (projects, datasets, analysis).

Run it in development with:
    uvicorn main:app --reload --port 8000
Then open http://localhost:8000/docs for the interactive API explorer.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import analysis, datasets, projects, sessions
from db import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hook. On startup we ensure the DB tables exist.

    This is the modern replacement for the deprecated @app.on_event('startup').
    Code before `yield` runs at startup; code after would run at shutdown.
    """
    init_db()
    yield


app = FastAPI(
    title="DetaBeta API",
    version="0.1.0",
    description=(
        "Interactive data-science laboratory. Upload a CSV to a project, then "
        "run any of the 9 engines: understand, health, investigate, statistics, "
        "feature-lab, recommend, experiment, explain, and report."
    ),
    lifespan=lifespan,
)

# --- CORS -----------------------------------------------------------------
# During development we allow all origins so the Next.js dev server (whatever
# port it lands on) can call the API. Tighten this to specific origins in prod
# via the ALLOWED_ORIGINS env var (comma-separated).
_origins_env = os.environ.get("ALLOWED_ORIGINS", "*")
_allow_origins = ["*"] if _origins_env == "*" else [o.strip() for o in _origins_env.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["meta"])
def root() -> dict:
    """Health check / friendly landing response."""
    return {
        "name": "DetaBeta API",
        "status": "ok",
        "docs": "/docs",
        "engines": [
            "understand", "health", "investigate", "statistics", "feature-lab",
            "recommend", "experiment", "explain", "report",
        ],
    }


# --- Mount routers --------------------------------------------------------
app.include_router(projects.router)
app.include_router(datasets.router)
app.include_router(analysis.router)
app.include_router(sessions.router)
app.include_router(sessions.session_router)
