"""Render the governance team's intake form as HTML (preview) and PDF (WeasyPrint).

The template receives a flat, display-ready context built here so it contains no
business logic. Only values are shown in the form body; confidence, source and
confirmation stay in the JSON export. The one place confirmation surfaces is the
residual-risk controls table, where "Confirmed" versus "Claimed, not confirmed" is the
assessment outcome the governance team needs, computed by the rules engine.
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
    ControlEffect,
    EuAiActClassification,
    IntakeMode,
    IntakeRecord,
    Obligation,
    RationaleEntry,
    RiskDriver,
    RiskLens,
    RiskProfile,
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

CONTROL_STATUS_LABELS: dict[str, str] = {
    "applied": "Confirmed",
    "unconfirmed": "Claimed, not confirmed",
    "absent": "Not in place",
    "unknown": "Not answered",
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


class DriverRow(TypedDict):
    field: str
    label: str
    value: str
    category: str
    points: int
    text: str


class ControlRow(TypedDict):
    field: str
    control: str
    label: str
    status: str
    status_label: str
    points: int
    text: str


class RiskProfileView(TypedDict):
    key: str
    label: str
    tier: str
    tier_label: str
    css_class: str
    score: int
    floor: str | None
    floor_reason: str | None


class RiskLensRow(TypedDict):
    lens: str
    label: str
    inherent: RiskProfileView
    residual: RiskProfileView
    drivers: str


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


def control_label(effect: ControlEffect) -> str:
    """Option label for a ``ControlKind``; the field label when the control is an answer
    (``ai_system.human_oversight`` → ``Human oversight``)."""
    if effect.control == effect.field:
        return field_label(effect.field)
    spec = QUESTIONS_BY_FIELD.get(effect.field)
    if spec is not None:
        for option in spec.options:
            if option.value == effect.control:
                return option.label
    return humanise_field(effect.control)


def driver_rows(drivers: list[RiskDriver]) -> list[DriverRow]:
    return [
        {
            "field": driver.field,
            "label": field_label(driver.field),
            "value": display_value(driver.field, driver.value),
            "category": driver.category.capitalize(),
            "points": driver.points,
            "text": driver.text,
        }
        for driver in drivers
    ]


def control_rows(controls: list[ControlEffect]) -> list[ControlRow]:
    return [
        {
            "field": effect.field,
            "control": effect.control,
            "label": control_label(effect),
            "status": effect.status,
            "status_label": CONTROL_STATUS_LABELS[effect.status],
            "points": effect.points,
            "text": effect.text,
        }
        for effect in controls
    ]


def risk_profile_view(key: str, label: str, profile: RiskProfile) -> RiskProfileView:
    tier = RiskTier(profile.tier)
    return {
        "key": key,
        "label": label,
        "tier": tier.value,
        "tier_label": tier.value.capitalize(),
        "css_class": RISK_TIER_CSS_CLASS[tier],
        "score": profile.score,
        "floor": RiskTier(profile.floor).value if profile.floor is not None else None,
        "floor_reason": profile.floor_reason,
    }


def risk_lens_rows(lenses: list[RiskLens]) -> list[RiskLensRow]:
    """One row per enterprise lens, in the engine's fixed order; the driver column is the
    texts of the drivers tagged with that lens, or an em dash when none applies."""
    return [
        {
            "lens": lens.lens,
            "label": lens.label,
            "inherent": risk_profile_view(f"{lens.lens}-inherent", "Inherent", lens.inherent),
            "residual": risk_profile_view(f"{lens.lens}-residual", "Residual", lens.residual),
            "drivers": "; ".join(driver.text for driver in lens.inherent.drivers) or "—",
        }
        for lens in lenses
    ]


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
        "inherent_risk": risk_profile_view("inherent", "Inherent risk", assessment.inherent_risk),
        "residual_risk": risk_profile_view("residual", "Residual risk", assessment.residual_risk),
        "risk_lenses": risk_lens_rows(assessment.risk_lenses),
        # The residual profile carries the same drivers as the inherent one; the drivers
        # table is shown once, the controls table comes from the residual profile.
        "risk_drivers": driver_rows(assessment.inherent_risk.drivers),
        "risk_controls": control_rows(assessment.residual_risk.controls),
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
