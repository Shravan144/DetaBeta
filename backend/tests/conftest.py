"""Global safeguards for the backend test suite."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_external_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must never read from or write to configured cloud storage."""
    monkeypatch.setenv("STORAGE_BACKEND", "local")
