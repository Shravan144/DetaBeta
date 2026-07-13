"""
Tests for the report export layer.

Two levels:
  * Pure builders in services.report_export (dict -> HTML / print-HTML / MD),
    including HTML escaping and tolerance of partial reports.
  * The HTTP export endpoint, exercised end-to-end through the API with an
    isolated temp DB + storage folder (same fixture style as test_sessions.py).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import main
from db import Base, get_db
from services import report_export, storage

_SAMPLE_CSV = Path(__file__).resolve().parent.parent / "sample_data" / "passengers.csv"


# ---------------------------------------------------------------------------
# Pure builder tests (no HTTP, no DB)
# ---------------------------------------------------------------------------

def _sample_report() -> dict:
    return {
        "title": "Data Story: demo",
        "dataset_name": "demo",
        "target": "survived",
        "executive_summary": ["A 100-row dataset that is trustworthy.", "Sex matters."],
        "sections": [
            {
                "key": "understanding",
                "title": "What is this data?",
                "headline": "100 rows, 5 columns.",
                "body": ["It has a mix of numeric and categorical columns."],
                "key_points": ["5 columns", "no id column"],
            }
        ],
        "trust_level": "Trustworthy (grade B)",
        "headline_finding": "Sex is strongly related to survival.",
        "model_verdict": "Random Forest: F1 0.81 (beats the simple baseline)",
        "caveats": ["Small sample; treat as tentative."],
        "next_steps": ["Collect more data.", "Validate on unseen data."],
    }


def test_to_html_is_self_contained_and_complete():
    html = report_export.to_html(_sample_report())
    assert html.startswith("<!doctype html>")
    assert "<style>" in html  # CSS is inlined, no external assets
    assert "http://" not in html and "https://" not in html  # nothing external
    # Key content is present.
    assert "Executive Summary" in html
    assert "What is this data?" in html
    assert "Random Forest" in html
    assert "Prioritized Next Steps" in html
    assert "Limitations" in html


def test_to_html_escapes_dangerous_text():
    report = _sample_report()
    report["title"] = "<script>alert('x')</script>"
    report["sections"][0]["body"] = ["1 < 2 & 3 > 2"]
    html = report_export.to_html(report)
    # The raw script tag must not survive; it should be escaped.
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "1 &lt; 2 &amp; 3 &gt; 2" in html


def test_print_html_autoprints():
    html = report_export.to_print_html(_sample_report())
    assert "window.print()" in html
    assert html.strip().endswith("</html>")


def test_to_markdown_structure():
    md = report_export.to_markdown(_sample_report())
    assert md.startswith("# Data Story: demo")
    assert "## Executive Summary" in md
    assert "## Chapter 01: What is this data?" in md
    assert "> 100 rows, 5 columns." in md  # headline as blockquote
    assert "1. Collect more data." in md   # ordered next steps
    assert "- Small sample" in md          # caveats bullet


def test_builders_tolerate_partial_report():
    # A report with almost nothing set should still export without raising.
    minimal = {"dataset_name": "x"}
    assert report_export.to_html(minimal).startswith("<!doctype html>")
    assert "#" in report_export.to_markdown(minimal)
    assert "window.print()" in report_export.to_print_html(minimal)


def test_safe_filename():
    # Each non-alphanumeric run maps to underscores ("!" and "." here).
    assert report_export.safe_filename("My Data!.csv", "html") == "detabeta_report_My_Data__csv.html"
    assert report_export.safe_filename("", "md") == "detabeta_report_report.md"


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    test_engine = create_engine(
        f"sqlite:///{db_file}", connect_args={"check_same_thread": False}, future=True
    )
    TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=test_engine)

    def _override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = _override_get_db
    monkeypatch.setattr(storage, "STORAGE_ROOT", tmp_path / "storage")

    with TestClient(main.app) as c:
        yield c

    main.app.dependency_overrides.clear()


@pytest.fixture()
def dataset_id(client) -> int:
    pid = client.post("projects", json={"name": "Titanic study"}).json()["id"]
    with open(_SAMPLE_CSV, "rb") as fh:
        resp = client.post(
            f"projects/{pid}/datasets",
            files={"file": ("passengers.csv", fh, "text/csv")},
        )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_export_html_downloads_attachment(client, dataset_id):
    r = client.get(f"datasets/{dataset_id}/analysis/report/export?target=survived&format=html")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/html")
    assert "attachment" in r.headers.get("content-disposition", "")
    assert ".html" in r.headers.get("content-disposition", "")
    assert r.text.startswith("<!doctype html>")


def test_export_markdown_downloads_attachment(client, dataset_id):
    r = client.get(f"datasets/{dataset_id}/analysis/report/export?target=survived&format=md")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/markdown")
    assert ".md" in r.headers.get("content-disposition", "")
    assert r.text.startswith("# ")


def test_export_print_is_inline_and_autoprints(client, dataset_id):
    r = client.get(f"datasets/{dataset_id}/analysis/report/export?format=print")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/html")
    # print view opens inline (no attachment), so the browser can render + print.
    assert "attachment" not in r.headers.get("content-disposition", "")
    assert "window.print()" in r.text


def test_export_defaults_to_html(client, dataset_id):
    r = client.get(f"datasets/{dataset_id}/analysis/report/export")
    assert r.status_code == 200
    assert r.text.startswith("<!doctype html>")


def test_export_rejects_unknown_format(client, dataset_id):
    r = client.get(f"datasets/{dataset_id}/analysis/report/export?format=xml")
    assert r.status_code == 400
    assert "Unknown export format" in r.json()["detail"]


def test_export_reuses_cached_report(client, dataset_id):
    # First compose the report (miss), then export twice; the export should be
    # reading the cached session report, so a fresh session is not created each
    # time. We assert the session count stays at 1 for the base (no-target) run.
    client.get(f"datasets/{dataset_id}/analysis/report")
    client.get(f"datasets/{dataset_id}/analysis/report/export?format=html")
    client.get(f"datasets/{dataset_id}/analysis/report/export?format=md")
    sessions = client.get(f"datasets/{dataset_id}/sessions").json()
    base_sessions = [s for s in sessions if s["target"] is None]
    assert len(base_sessions) == 1
