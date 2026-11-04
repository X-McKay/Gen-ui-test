"""PDF export for the planted fixture."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

TEMPLATES = Path(__file__).parent / "templates"
environment = Environment(loader=FileSystemLoader(TEMPLATES))  # PLANTED EXP-01 (autoescape off)


def _findings_html(findings: list[dict[str, str]]) -> str:
    return "".join(f"<li>{f['title']}: {f['evidence']}</li>" for f in findings)  # PLANTED EXP-02


def render_pdf(record: dict[str, object], findings: list[dict[str, str]]) -> bytes:
    template = environment.get_template("report.html")
    html = template.render(
        project_name=record.get("project_name", ""),
        description=record.get("description", ""),
        findings_html=_findings_html(findings),
    )
    return bytes(HTML(string=html, base_url=str(TEMPLATES)).write_pdf())  # PLANTED EXP-03 (no url_fetcher)
