"""Render the governance team's intake form as HTML (preview) and PDF (WeasyPrint).

The template receives a flat, display-ready context built here so it contains no
business logic. Only values are shown in the form body; confidence, source and
confirmation stay in the JSON export.
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.intake.gap_analysis import open_questions
from app.intake.question_bank import (
    QUESTION_BANK,
    QUESTIONS_BY_FIELD,
    SECTION_LABELS,
    Section,
    display_value,
)
from app.intake.schema import (
    EuAiActClassification,
    IntakeMode,
    IntakeRecord,
    Obligation,
    RationaleEntry,
    RiskTier,
)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
FORM_TEMPLATE = "intake_form.html"


class TierInfo(TypedDict):
    key: str
    css_class: str
    label: str
    explanation: str


TIER_INFO: dict[EuAiActClassification, TierInfo] = {
    EuAiActClassification.PROHIBITED: {
        "key": "prohibited",
        "css_class": "tier-prohibited",
        "label": "Prohibited",
        "explanation": (
            "The described practice falls under Article 5 of the EU AI Act. It may not be "
            "placed on the market, put into service or used in the EU. Escalate to the "
            "governance team before any further work."
        ),
    },
    EuAiActClassification.HIGH_RISK: {
        "key": "high_risk",
        "css_class": "tier-high-risk",
        "label": "High risk",
        "explanation": (
            "The system is listed in Annex III or is a safety component of a regulated "
            "product. Risk management, data governance, technical documentation, logging, "
            "human oversight and a conformity assessment are required before deployment."
        ),
    },
    EuAiActClassification.LIMITED_TRANSPARENCY: {
        "key": "limited_transparency",
        "css_class": "tier-limited",
        "label": "Limited risk (transparency)",
        "explanation": (
            "Not high risk, but Article 50 transparency duties apply: people must be told "
            "they are interacting with an AI system and generated content must be marked."
        ),
    },
    EuAiActClassification.MINIMAL: {
        "key": "minimal",
        "css_class": "tier-minimal",
        "label": "Minimal risk",
        "explanation": (
            "No specific EU AI Act obligations beyond voluntary codes of conduct. Other "
            "law, such as the GDPR, still applies where personal data is involved."
        ),
    },
}

RISK_TIER_CSS_CLASS: dict[RiskTier, str] = {
    RiskTier.LOW: "tier-minimal",
    RiskTier.MEDIUM: "tier-limited",
    RiskTier.HIGH: "tier-high-risk",
    RiskTier.CRITICAL: "tier-prohibited",
}

MODE_LABELS: dict[IntakeMode, str] = {
    IntakeMode.NEW: "New project",
    IntakeMode.EXISTING: "Existing project",
}


class FormRow(TypedDict):
    field: str
    label: str
    value: str


class FormSection(TypedDict):
    key: str
    label: str
    rows: list[FormRow]


class OpenQuestion(TypedDict):
    field: str
    label: str
    prompt: str


class ObligationGroup(TypedDict):
    framework: str
    obligations: list[Obligation]


def format_datetime(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%-d %b %Y, %H:%M UTC")


def humanise_field(path: str) -> str:
    """Fallback label for a field without a spec (``pii_categories`` → ``Pii categories``)."""
    return path.rsplit(".", 1)[-1].replace("_", " ").capitalize()


def field_label(path: str) -> str:
    spec = QUESTIONS_BY_FIELD.get(path)
    return spec.label if spec else humanise_field(path)


def form_sections(record: IntakeRecord) -> list[FormSection]:
    """One table per askable section, question-bank order, values only, ``None`` skipped."""
    sections: list[FormSection] = []
    for section in Section:
        specs = sorted(
            (spec for spec in QUESTION_BANK if spec.section == section),
            key=lambda spec: spec.priority,
        )
        rows: list[FormRow] = []
        for spec in specs:
            value = record.value_of(spec.field)
            if value is None:
                continue
            rows.append(
                {
                    "field": spec.field,
                    "label": spec.label,
                    "value": display_value(spec.field, value),
                }
            )
        sections.append({"key": section.value, "label": SECTION_LABELS[section], "rows": rows})
    return sections


def unanswered_questions(record: IntakeRecord) -> list[OpenQuestion]:
    questions: list[OpenQuestion] = []
    for path in open_questions(record):
        spec = QUESTIONS_BY_FIELD.get(path)
        questions.append(
            {
                "field": path,
                "label": spec.label if spec else humanise_field(path),
                "prompt": spec.prompt if spec else "No question text available.",
            }
        )
    return questions


def group_obligations(obligations: list[Obligation]) -> list[ObligationGroup]:
    groups: dict[str, list[Obligation]] = {}
    for obligation in obligations:
        groups.setdefault(obligation.framework, []).append(obligation)
    return [{"framework": framework, "obligations": items} for framework, items in groups.items()]


def rationale_value(entry: RationaleEntry) -> str:
    return display_value(entry.field, entry.value)


def build_form_context(record: IntakeRecord) -> dict[str, object]:
    assessment = record.assessment
    classification = EuAiActClassification(assessment.eu_ai_act.classification)
    risk_tier = RiskTier(assessment.overall_risk_tier)
    tier = TIER_INFO[classification]
    project_name = record.value_of("project.name")
    title = str(project_name) if isinstance(project_name, str) and project_name != "unknown" else ""
    return {
        "record": record,
        "meta": record.meta,
        "project_name": title or "Untitled project",
        "mode_label": MODE_LABELS[IntakeMode(record.meta.mode)],
        "status_label": str(record.meta.status).replace("_", " ").capitalize(),
        "created_at": format_datetime(record.meta.created_at),
        "completed_at": format_datetime(record.meta.completed_at),
        "generated_at": format_datetime(datetime.now(UTC)),
        "tier": tier,
        "annex_iii_categories": assessment.eu_ai_act.annex_iii_categories,
        "risk_tier": risk_tier.value,
        "risk_tier_label": risk_tier.value.capitalize(),
        "risk_tier_css_class": RISK_TIER_CSS_CLASS[risk_tier],
        "frameworks": assessment.applicable_frameworks,
        "sections": form_sections(record),
        "rationale": [
            {
                "label": field_label(entry.field),
                "value": rationale_value(entry),
                "article": entry.article,
                "text": entry.text,
            }
            for entry in assessment.eu_ai_act.rationale
        ],
        "obligation_groups": group_obligations(assessment.obligations),
        "next_steps": assessment.recommended_next_steps,
        "open_questions": unanswered_questions(record),
    }


@lru_cache(maxsize=1)
def template_environment() -> Environment:
    environment = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(default=True, default_for_string=True),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    environment.filters["display"] = display_value
    environment.filters["datetime"] = format_datetime
    return environment


def render_form_html(record: IntakeRecord) -> str:
    template = template_environment().get_template(FORM_TEMPLATE)
    return template.render(**build_form_context(record))


def export_pdf_bytes(record: IntakeRecord) -> bytes:
    from weasyprint import HTML  # imported lazily: loads pango/cairo

    html = render_form_html(record)
    document = HTML(string=html, base_url=str(TEMPLATES_DIR))  # type: ignore[no-untyped-call]
    pdf: bytes = document.write_pdf()  # type: ignore[no-untyped-call]
    return pdf
