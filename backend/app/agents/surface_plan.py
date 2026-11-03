"""Builds interview steps and the A2UI operations that render them.

The server decides *what* a step contains (gap analysis); the model decides how to phrase
the intro and may adjust copy, but it renders through the catalog only. Every operation
here is A2UI 1.0 and targets the ``interview`` surface of the page.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.intake.gap_analysis import (
    Assumption,
    SectionProgress,
    assumptions,
    is_complete,
    next_questions,
    section_progress,
    suggested_value,
)
from app.intake.question_bank import SECTION_LABELS, QuestionSpec, Section
from app.intake.schema import EuAiActClassification, IntakeRecord

TARGET_ID = "interview"
CATALOG_ID = "intake/interview@1"
SUBMIT_EVENT = "submit_step"
ACKNOWLEDGE_EVENT = "acknowledge_escalation"

StepKind = Literal["interview", "findings", "escalation", "done"]


class QuestionView(BaseModel):
    """A question spec as the model and the UI see it (``suggested`` added)."""

    model_config = ConfigDict(extra="forbid")

    field: str
    section: Section
    label: str
    prompt: str
    control: Literal["choice", "multi", "yes_no", "text"]
    options: list[dict[str, str | None]] = Field(default_factory=list)
    required: bool = True
    must_confirm: bool = False
    is_gate: bool = False
    why_asked: str | None = None
    sensitive: bool = False
    placeholder: str | None = None
    suggested: object = None


class Finding(BaseModel):
    model_config = ConfigDict(extra="ignore")

    field: str
    label: str
    value: object
    display_value: str
    confidence: float
    evidence_path: str
    snippet: str


class Step(BaseModel):
    """One interview step. Persisted as ``current_step`` so a reload can restore it."""

    model_config = ConfigDict(extra="forbid")

    step_number: int
    surface_id: str
    previous_surface_id: str | None = None
    kind: StepKind
    intro: str = ""
    section: Section | None = None
    assumptions: list[Assumption] = Field(default_factory=list)
    questions: list[QuestionView] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    progress: list[SectionProgress] = Field(default_factory=list)
    escalation_reasons: list[str] = Field(default_factory=list)


def question_view(record: IntakeRecord, spec: QuestionSpec) -> QuestionView:
    return QuestionView(
        field=spec.field,
        section=spec.section,
        label=spec.label,
        prompt=spec.prompt,
        control=spec.control,
        options=[option.model_dump() for option in spec.options],
        required=spec.required,
        must_confirm=spec.must_confirm,
        is_gate=spec.is_gate,
        why_asked=spec.why_asked,
        sensitive=spec.sensitive,
        placeholder=spec.placeholder,
        suggested=suggested_value(record, spec),
    )


def default_intro(step: Step) -> str:
    if step.kind == "findings":
        return "Here is what the repository told us. Confirm what is right and correct the rest."
    if step.kind == "escalation":
        return "This project describes a practice the EU AI Act prohibits."
    if step.kind == "done":
        return "That is everything we need."
    if step.assumptions and step.questions:
        return "Here is what we understood. Confirm it, then answer the questions below."
    if step.assumptions:
        return "Here is what we understood. Confirm it to continue."
    if step.section is not None:
        return f"A few questions about the {SECTION_LABELS[step.section].lower()}."
    return "A few more questions."


def confirmed_prohibited(record: IntakeRecord) -> bool:
    """Escalate only when the user confirmed every signal behind a prohibited finding.

    An inferred signal is shown as a must-confirm chip first; the user may correct it.
    """
    if record.assessment.eu_ai_act.classification != EuAiActClassification.PROHIBITED:
        return False
    triggers = [e for e in record.assessment.eu_ai_act.rationale if e.effect == "prohibited"]
    if not triggers:
        return False
    for entry in triggers:
        try:
            field = record.get_field(entry.field)
        except KeyError:
            continue
        if not (field.confirmed or field.source == "user"):
            return False
    return True


def build_step(
    record: IntakeRecord,
    *,
    step_number: int,
    previous_surface_id: str | None,
    findings: list[Finding] | None = None,
    include_assumptions: bool = True,
) -> Step:
    """Decide the next step from the record. Pure apart from reading the record."""
    surface_id = f"step-{step_number}"
    if confirmed_prohibited(record):
        reasons = [
            entry.text
            for entry in record.assessment.eu_ai_act.rationale
            if entry.effect == "prohibited"
        ]
        step = Step(
            step_number=step_number,
            surface_id=surface_id,
            previous_surface_id=previous_surface_id,
            kind="escalation",
            escalation_reasons=reasons,
            progress=section_progress(record),
        )
        step.intro = default_intro(step)
        return step
    if findings:
        step = Step(
            step_number=step_number,
            surface_id=surface_id,
            previous_surface_id=previous_surface_id,
            kind="findings",
            findings=findings,
            progress=section_progress(record),
        )
        step.intro = default_intro(step)
        return step
    chips = assumptions(record) if include_assumptions else []
    specs = next_questions(record)
    if not specs and not chips:
        kind: StepKind = "done" if is_complete(record) else "interview"
        step = Step(
            step_number=step_number,
            surface_id=surface_id,
            previous_surface_id=previous_surface_id,
            kind=kind,
            progress=section_progress(record),
        )
        step.intro = default_intro(step)
        return step
    section = specs[0].section if specs else (chips[0].section if chips else None)
    step = Step(
        step_number=step_number,
        surface_id=surface_id,
        previous_surface_id=previous_surface_id,
        kind="interview",
        section=section,
        assumptions=chips,
        questions=[question_view(record, spec) for spec in specs],
        progress=section_progress(record, active=section),
    )
    step.intro = default_intro(step)
    return step


# --- A2UI operations ----------------------------------------------------------------------


def _operation(kind: str, body: dict[str, Any]) -> dict[str, Any]:
    return {"version": "1.0", kind: body}


def _submit_action(step: Step) -> dict[str, Any]:
    return {"event": {"name": SUBMIT_EVENT, "userMessage": f"Submitted step {step.step_number}"}}


def _question_component(index: int, question: QuestionView) -> dict[str, Any]:
    component = {
        "choice": "ChoiceQuestion",
        "multi": "MultiSelectQuestion",
        "yes_no": "YesNoQuestion",
        "text": "ShortTextQuestion",
    }[question.control]
    node: dict[str, Any] = {
        "id": f"question-{index}",
        "component": component,
        "field": question.field,
        "prompt": question.prompt,
    }
    if question.control in {"choice", "multi"}:
        node["options"] = [
            {"value": option["value"], "label": option["label"]} for option in question.options
        ]
    if question.why_asked:
        node["whyAsked"] = question.why_asked
    if question.control == "text":
        if question.placeholder:
            node["placeholder"] = question.placeholder
        node["checks"] = {"required": question.required, "maxLength": 500}
    if question.suggested is not None:
        if question.control == "yes_no":
            node["suggested"] = "yes" if question.suggested is True else "no"
        elif question.control == "multi":
            node["suggested"] = (
                [str(item) for item in question.suggested]
                if isinstance(question.suggested, list)
                else []
            )
        else:
            node["suggested"] = str(question.suggested)
    return node


def build_operations(step: Step) -> list[dict[str, Any]]:
    """The operations for ``render_ui``: delete the previous step, create and fill the new one."""
    operations: list[dict[str, Any]] = []
    if step.previous_surface_id:
        operations.append(_operation("deleteSurface", {"surfaceId": step.previous_surface_id}))
    if step.kind == "done":
        return operations
    root: dict[str, Any]
    children: list[dict[str, Any]] = []
    if step.kind == "escalation":
        root = {
            "id": "root",
            "component": "EscalationNotice",
            "title": "Stop: this needs the governance team",
            "reasons": step.escalation_reasons or ["A prohibited practice was identified."],
            "contact": "Contact the AI governance team before any further work.",
            "onAcknowledge": {
                "event": {"name": ACKNOWLEDGE_EVENT, "userMessage": "Acknowledged the escalation"}
            },
        }
    else:
        root = {
            "id": "root",
            "component": "InterviewStep",
            "intro": step.intro,
            "section": step.section.value if step.section else "summary",
            "confirmLabel": "Confirm and continue",
            "questions": [],
            "onSubmit": _submit_action(step),
        }
        if step.kind == "findings":
            root["findings"] = "findings"
            children.append(
                {
                    "id": "findings",
                    "component": "FindingsReview",
                    "title": "What we found in the repository",
                    "findings": [
                        {
                            "field": finding.field,
                            "label": finding.label,
                            "value": finding.value,
                            "displayValue": finding.display_value,
                            "confidence": round(finding.confidence, 2),
                            "evidencePath": finding.evidence_path,
                            "snippet": finding.snippet,
                        }
                        for finding in step.findings
                    ],
                }
            )
        if step.assumptions:
            root["assumptions"] = "assumptions"
            children.append(
                {
                    "id": "assumptions",
                    "component": "AssumptionReview",
                    "title": "What we understood",
                    "assumptions": [
                        {
                            "field": chip.field,
                            "label": chip.label,
                            "value": chip.value,
                            "displayValue": chip.display_value,
                            "confidence": round(chip.confidence, 2),
                            "source": chip.source,
                            "mustConfirm": chip.must_confirm,
                        }
                        for chip in step.assumptions
                    ],
                }
            )
        root["questions"] = [f"question-{index}" for index in range(len(step.questions))]
        children.extend(
            _question_component(index, question) for index, question in enumerate(step.questions)
        )
    operations.append(
        _operation(
            "createSurface",
            {"surfaceId": step.surface_id, "catalogId": CATALOG_ID, "components": [root]},
        )
    )
    if children:
        operations.append(
            _operation("updateComponents", {"surfaceId": step.surface_id, "components": children})
        )
    return operations


def invalid_operations_fixture(step: Step) -> list[dict[str, Any]]:
    """A deliberately invalid render used by the guardrail test: a component outside the catalog."""
    return [
        _operation(
            "createSurface",
            {
                "surfaceId": f"{step.surface_id}-invalid",
                "catalogId": CATALOG_ID,
                "components": [
                    {"id": "root", "component": "Marquee", "text": "<script>alert(1)</script>"}
                ],
            },
        )
    ]
