"""DetaBeta API -- application entry point.

This file assembles the whole backend:
  * creates the FastAPI app (with metadata that powers the /docs page),
  * enables CORS so a browser frontend can call it,
  * registers rate-limiting middleware,
  * ensures the database tables exist on startup,
  * mounts the three routers (projects, datasets, analysis).

Run it in development with:
    uvicorn main:app --reload --port 8000
Then open http://localhost:8000/docs for the interactive API explorer.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load environment variables from .env file at startup
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from api.routers import analysis, datasets, projects, sessions
from db import get_db, init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hook. On startup we ensure the DB tables exist.

    This is the modern replacement for the deprecated @app.on_event('startup').
    Code before `yield` runs at startup; code after would run at shutdown.
    """
    # Integration tests replace get_db with an isolated temporary database.
    # Initializing the module-level engine in that case would unexpectedly touch
    # the configured development/production database before the test starts.
    if get_db not in _app.dependency_overrides:
        init_db()
    yield


# --- Rate limiting --------------------------------------------------------
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])

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

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# --- CORS -----------------------------------------------------------------
# Read allowed origins from the environment. Default to localhost:3000 for
# local development. Wildcard (*) is rejected to enforce explicit configuration.
_origins_env = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000")

if _origins_env.strip() == "*":
    logger.warning(
        "ALLOWED_ORIGINS='*' is insecure and rejected. "
        "Falling back to http://localhost:3000. "
        "Set explicit origins in production."
    )
    _allow_origins = ["http://localhost:3000"]
else:
    _allow_origins = [o.strip() for o in _origins_env.split(",") if o.strip()]

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
