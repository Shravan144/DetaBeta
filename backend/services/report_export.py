"""
Report export: turn a DataStory (Engine 9's output) into downloadable files.

Engine 9 produces a `DataStory` that the API serializes to a plain dict. This
module converts that dict into three human-facing document formats:

    * to_html(report)        -- a self-contained, nicely styled HTML document
                                (all CSS inlined; opens/prints/shares anywhere).
    * to_print_html(report)  -- the same document, tuned for the browser's
                                "Save as PDF": it auto-triggers window.print()
                                on load. This is how we make a PDF with zero
                                extra dependencies and no fragile system
                                libraries -- perfect for the free serverless tier.
    * to_markdown(report)    -- a clean Markdown version for GitHub / sharing.

Design notes
------------
* These are PURE functions: dict in, string out. No I/O, no DB, easy to test.
* We defensively `.get(...)` every field so a partial report (e.g. one with no
  modelling half) still exports cleanly.
* All user/engine text is HTML-escaped before being placed in HTML.
"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _as_list(value) -> list:
    """Coerce a field to a list of items (tolerates None / a bare string)."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _generated_stamp() -> str:
    """A readable UTC timestamp for the document footer/header."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def safe_filename(name: str, extension: str) -> str:
    """Build a filesystem/HTTP-safe download filename from a dataset name."""
    base = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in (name or "report"))
    base = base.strip("_") or "report"
    return f"detabeta_report_{base}.{extension}"


# ---------------------------------------------------------------------------
# HTML export
# ---------------------------------------------------------------------------

# A light, print-friendly stylesheet. Kept intentionally simple and inlined so
# the exported file is fully self-contained (no external fonts or CSS).
_CSS = """
:root { --ink:#18181b; --muted:#52525b; --line:#e4e4e7; --accent:#047857; --accent-soft:#ecfdf5; --rose:#be123c; }
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
       color: var(--ink); line-height: 1.6; margin: 0; background: #fff; }
.page { max-width: 820px; margin: 0 auto; padding: 48px 32px 64px; }
.eyebrow { text-transform: uppercase; letter-spacing: .12em; font-size: 11px; font-weight: 700; color: var(--accent); }
h1 { font-size: 28px; line-height: 1.2; margin: 8px 0 4px; letter-spacing: -0.01em; }
.meta { font-size: 12px; color: var(--muted); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.verdicts { display: flex; flex-wrap: wrap; gap: 12px; margin: 24px 0; }
.verdict { flex: 1 1 180px; border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; }
.verdict .label { font-size: 10px; text-transform: uppercase; letter-spacing: .1em; color: var(--muted); font-weight: 700; }
.verdict .value { font-size: 14px; margin-top: 4px; font-weight: 600; }
.summary { background: var(--accent-soft); border: 1px solid #a7f3d0; border-radius: 10px; padding: 18px 20px; margin: 24px 0; }
.summary h2 { font-size: 12px; text-transform: uppercase; letter-spacing: .1em; color: var(--accent); margin: 0 0 8px; }
.summary p { margin: 0 0 8px; font-size: 14px; }
section.chapter { border-top: 1px solid var(--line); padding-top: 24px; margin-top: 28px; }
.chapter-head { display: flex; align-items: center; gap: 10px; }
.chip { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px; font-weight: 700;
        color: var(--muted); border: 1px solid var(--line); border-radius: 6px; padding: 2px 8px; }
.chapter h3 { font-size: 17px; margin: 0; }
blockquote { border-left: 3px solid var(--accent); margin: 14px 0; padding: 2px 0 2px 14px;
             font-style: italic; color: #3f3f46; }
.chapter p { font-size: 14px; color: #3f3f46; }
ul.points { list-style: none; padding: 0; margin: 12px 0 0; }
ul.points li { position: relative; padding-left: 18px; font-size: 13px; color: #3f3f46; margin: 6px 0; }
ul.points li::before { content: "•"; color: var(--accent); font-weight: 700; position: absolute; left: 0; }
.two-col { display: flex; flex-wrap: wrap; gap: 16px; margin-top: 32px; }
.box { flex: 1 1 300px; border: 1px solid var(--line); border-radius: 10px; padding: 16px 18px; }
.box h4 { font-size: 11px; text-transform: uppercase; letter-spacing: .1em; margin: 0 0 10px; }
.box.caveats h4 { color: var(--rose); }
.box.steps h4 { color: var(--accent); }
.box ol, .box ul { margin: 0; padding-left: 18px; }
.box li { font-size: 13px; color: #3f3f46; margin: 6px 0; }
footer { margin-top: 40px; border-top: 1px solid var(--line); padding-top: 16px;
         font-size: 11px; color: var(--muted); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
@media print {
  .page { max-width: none; padding: 0 12px; }
  section.chapter { break-inside: avoid; }
  .verdict, .box { break-inside: avoid; }
  a[href]::after { content: ""; }
}
"""


def _html_section(index: int, section: dict) -> str:
    title = escape(str(section.get("title", "")))
    headline = escape(str(section.get("headline", "")))
    body = "".join(f"<p>{escape(str(p))}</p>" for p in _as_list(section.get("body")))
    points = "".join(f"<li>{escape(str(pt))}</li>" for pt in _as_list(section.get("key_points")))
    points_html = f'<ul class="points">{points}</ul>' if points else ""
    blockquote = f"<blockquote>{headline}</blockquote>" if headline else ""
    return (
        f'<section class="chapter">'
        f'<div class="chapter-head"><span class="chip">Chapter {index:02d}</span>'
        f"<h3>{title}</h3></div>"
        f"{blockquote}{body}{points_html}"
        f"</section>"
    )


def _html_verdicts(report: dict) -> str:
    items = [
        ("Trust level", report.get("trust_level")),
        ("Headline finding", report.get("headline_finding")),
        ("Model verdict", report.get("model_verdict")),
    ]
    cells = "".join(
        f'<div class="verdict"><div class="label">{escape(label)}</div>'
        f'<div class="value">{escape(str(value))}</div></div>'
        for label, value in items
        if value
    )
    return f'<div class="verdicts">{cells}</div>' if cells else ""


def _html_box(css_class: str, heading: str, items: list, ordered: bool) -> str:
    if not items:
        return ""
    tag = "ol" if ordered else "ul"
    lis = "".join(f"<li>{escape(str(i))}</li>" for i in items)
    return (
        f'<div class="box {css_class}"><h4>{escape(heading)}</h4>'
        f"<{tag}>{lis}</{tag}></div>"
    )


def _render_body(report: dict) -> str:
    """Shared inner HTML used by both the standalone and print documents."""
    title = escape(str(report.get("title") or "Data Story"))
    dataset_name = escape(str(report.get("dataset_name") or "dataset"))
    target = report.get("target")
    target_line = f" · Target: {escape(str(target))}" if target else ""

    summary_paras = "".join(
        f"<p>{escape(str(p))}</p>" for p in _as_list(report.get("executive_summary"))
    )
    summary_html = (
        f'<div class="summary"><h2>Executive Summary</h2>{summary_paras}</div>'
        if summary_paras
        else ""
    )

    chapters = "".join(
        _html_section(i + 1, s) for i, s in enumerate(_as_list(report.get("sections")))
    )

    caveats = _html_box("caveats", "Limitations", _as_list(report.get("caveats")), ordered=False)
    steps = _html_box("steps", "Prioritized Next Steps", _as_list(report.get("next_steps")), ordered=True)
    two_col = f'<div class="two-col">{caveats}{steps}</div>' if (caveats or steps) else ""

    return (
        f'<div class="page">'
        f'<div class="eyebrow">DetaBeta Research Report</div>'
        f"<h1>{title}</h1>"
        f'<div class="meta">Dataset: {dataset_name}{target_line} · Generated: {_generated_stamp()}</div>'
        f"{_html_verdicts(report)}"
        f"{summary_html}"
        f"{chapters}"
        f"{two_col}"
        f"<footer>Generated by DetaBeta — the interactive data science laboratory.</footer>"
        f"</div>"
    )


def to_html(report: dict) -> str:
    """Render a complete, self-contained HTML document for the report."""
    title = escape(str(report.get("title") or "DetaBeta Report"))
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{title}</title><style>{_CSS}</style></head>"
        f"<body>{_render_body(report)}</body></html>"
    )


def to_print_html(report: dict) -> str:
    """Same document, but auto-invokes the browser print dialog on load.

    Opening this page in a new tab and letting the user pick "Save as PDF" gives
    a high-quality PDF with no server-side PDF library. The onload handler waits
    a tick so layout/fonts settle before printing.
    """
    doc = to_html(report)
    script = (
        "<script>window.addEventListener('load',function(){"
        "setTimeout(function(){window.print();},300);});</script>"
    )
    return doc.replace("</body>", f"{script}</body>")


# ---------------------------------------------------------------------------
# Markdown export
# ---------------------------------------------------------------------------

def to_markdown(report: dict) -> str:
    """Render the report as clean Markdown (great for GitHub / sharing)."""
    lines: list[str] = []
    title = str(report.get("title") or "Data Story")
    lines.append(f"# {title}")
    lines.append("")

    dataset_name = str(report.get("dataset_name") or "dataset")
    target = report.get("target")
    meta = f"**Dataset:** {dataset_name}"
    if target:
        meta += f" · **Target:** {target}"
    meta += f" · **Generated:** {_generated_stamp()}"
    lines.append(meta)
    lines.append("")

    # Verdicts
    verdicts = [
        ("Trust level", report.get("trust_level")),
        ("Headline finding", report.get("headline_finding")),
        ("Model verdict", report.get("model_verdict")),
    ]
    verdict_lines = [f"- **{label}:** {value}" for label, value in verdicts if value]
    if verdict_lines:
        lines.extend(verdict_lines)
        lines.append("")

    # Executive summary
    summary = _as_list(report.get("executive_summary"))
    if summary:
        lines.append("## Executive Summary")
        lines.append("")
        lines.extend(summary)
        lines.append("")

    # Chapters
    for i, section in enumerate(_as_list(report.get("sections")), start=1):
        lines.append(f"## Chapter {i:02d}: {section.get('title', '')}")
        lines.append("")
        headline = section.get("headline")
        if headline:
            lines.append(f"> {headline}")
            lines.append("")
        for para in _as_list(section.get("body")):
            lines.append(str(para))
            lines.append("")
        points = _as_list(section.get("key_points"))
        if points:
            for pt in points:
                lines.append(f"- {pt}")
            lines.append("")

    # Caveats
    caveats = _as_list(report.get("caveats"))
    if caveats:
        lines.append("## Limitations")
        lines.append("")
        for c in caveats:
            lines.append(f"- {c}")
        lines.append("")

    # Next steps
    steps = _as_list(report.get("next_steps"))
    if steps:
        lines.append("## Prioritized Next Steps")
        lines.append("")
        for i, s in enumerate(steps, start=1):
            lines.append(f"{i}. {s}")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by DetaBeta — the interactive data science laboratory.*")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Format dispatch (used by the router)
# ---------------------------------------------------------------------------

# format key -> (builder, media type, file extension, as_attachment)
FORMATS: dict[str, tuple] = {
    "html": (to_html, "text/html; charset=utf-8", "html", True),
    "print": (to_print_html, "text/html; charset=utf-8", "html", False),
    "md": (to_markdown, "text/markdown; charset=utf-8", "md", True),
}
