"""Gap analysis: which fields still need the user, and in what order.

Pure functions over :class:`IntakeRecord` and the question bank. ``get_next_questions``
wraps :func:`next_questions` and adds surface bookkeeping.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.intake.question_bank import (
    CONDITIONAL_GATES,
    CONDITIONAL_MUST_CONFIRM,
    QUESTION_BANK,
    SECTION_LABELS,
    Control,
    Option,
    QuestionSpec,
    Section,
    display_value,
)
from app.intake.schema import UNKNOWN, FieldMeta, IntakeRecord

CONFIDENCE_THRESHOLD = 0.8
MAX_QUESTIONS_PER_SURFACE = 3


class FieldStatus(StrEnum):
    CONFIRMED = "confirmed"  # user confirmed (or user-entered)
    INFERRED_OK = "inferred_ok"  # inferred ≥ threshold and not must-confirm
    NEEDS_CONFIRMATION = "needs_confirmation"  # inferred, but must be confirmed
    LOW_CONFIDENCE = "low_confidence"  # inferred below threshold
    UNKNOWN = "unknown"  # user said "not sure"
    MISSING = "missing"  # nothing captured
    SKIPPED = "skipped"  # gate closed


class Assumption(BaseModel):
    """An inferred value shown as a chip for bulk confirmation."""

    model_config = ConfigDict(extra="forbid")

    field: str
    label: str
    value: object
    display_value: str
    confidence: float
    source: str
    must_confirm: bool = False
    section: Section
    control: Control = "text"
    options: list[Option] = Field(default_factory=list)


class SectionProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section: Section
    label: str
    total: int
    done: int
    active: bool = False


def must_confirm(record: IntakeRecord, spec: QuestionSpec) -> bool:
    if spec.field in CONDITIONAL_MUST_CONFIRM:
        return CONDITIONAL_MUST_CONFIRM[spec.field](record)
    return spec.must_confirm


def gate_open(record: IntakeRecord, spec: QuestionSpec) -> bool:
    """A closed or unanswered gate skips the dependent question."""
    conditional = CONDITIONAL_GATES.get(spec.field)
    if conditional is not None and not conditional(record):
        return False
    if spec.gate is None:
        return True
    gate_field = record.get_field(spec.gate.field)
    if gate_field.value is None or gate_field.value == UNKNOWN:
        return False
    return gate_field.value in spec.gate.values


def field_status(record: IntakeRecord, spec: QuestionSpec) -> FieldStatus:
    if not gate_open(record, spec):
        return FieldStatus.SKIPPED
    field: FieldMeta[object] = record.get_field(spec.field)
    if field.value is None:
        return FieldStatus.MISSING
    if field.value == UNKNOWN:
        return FieldStatus.UNKNOWN
    if field.confirmed or field.source == "user":
        return FieldStatus.CONFIRMED
    if must_confirm(record, spec):
        return FieldStatus.NEEDS_CONFIRMATION
    if field.confidence >= CONFIDENCE_THRESHOLD:
        return FieldStatus.INFERRED_OK
    return FieldStatus.LOW_CONFIDENCE


def _ordered_specs() -> list[QuestionSpec]:
    return sorted(QUESTION_BANK, key=lambda spec: spec.priority)


def assumptions(record: IntakeRecord) -> list[Assumption]:
    """Inferred, unconfirmed values worth showing as chips (any confidence for must-confirm)."""
    chips: list[Assumption] = []
    for spec in _ordered_specs():
        # Optional details stay as silent inferences (visible on the review page); chips are
        # for values that gate the interview or change the classification.
        if not spec.required and not spec.must_confirm:
            continue
        status = field_status(record, spec)
        if status not in {FieldStatus.INFERRED_OK, FieldStatus.NEEDS_CONFIRMATION}:
            continue
        field = record.get_field(spec.field)
        chips.append(
            Assumption(
                field=spec.field,
                label=spec.label,
                value=field.value,
                display_value=display_value(spec.field, field.value),
                confidence=field.confidence,
                source=field.source,
                must_confirm=status is FieldStatus.NEEDS_CONFIRMATION,
                section=spec.section,
                control=spec.control,
                options=spec.options,
            )
        )
    return chips


def open_gaps(record: IntakeRecord) -> list[QuestionSpec]:
    """Required specs that still need the user, gates first then by priority."""
    gaps: list[QuestionSpec] = []
    for spec in _ordered_specs():
        if not spec.required:
            continue
        status = field_status(record, spec)
        if status in {
            FieldStatus.MISSING,
            FieldStatus.LOW_CONFIDENCE,
            FieldStatus.NEEDS_CONFIRMATION,
        }:
            gaps.append(spec)
    return gaps


def next_questions(
    record: IntakeRecord, limit: int = MAX_QUESTIONS_PER_SURFACE
) -> list[QuestionSpec]:
    """At most ``limit`` related questions: all open gates first, else one section at a time."""
    shown_as_chips = {chip.field for chip in assumptions(record)}
    gaps = [spec for spec in open_gaps(record) if spec.field not in shown_as_chips]
    if not gaps:
        return []
    gates = [spec for spec in gaps if spec.is_gate]
    if gates:
        return gates[:limit]
    section = gaps[0].section
    return [spec for spec in gaps if spec.section == section][:limit]


def is_complete(record: IntakeRecord) -> bool:
    return not open_gaps(record)


def open_questions(record: IntakeRecord) -> list[str]:
    """Dotted paths of fields the user marked 'not sure'."""
    return [path for path, field in record.iter_fields() if field.value == UNKNOWN]


def section_progress(record: IntakeRecord, active: Section | None = None) -> list[SectionProgress]:
    rows: list[SectionProgress] = []
    for section in Section:
        specs = [spec for spec in QUESTION_BANK if spec.section == section and spec.required]
        done = 0
        for spec in specs:
            status = field_status(record, spec)
            if status is FieldStatus.SKIPPED:
                # Skipped behind an answered gate counts as done; behind an unanswered gate
                # it is still pending.
                gate_answered = spec.gate is not None and record.get_field(spec.gate.field).is_set
                conditional_closed = spec.field in CONDITIONAL_GATES and not CONDITIONAL_GATES[
                    spec.field
                ](record)
                done += 1 if gate_answered or conditional_closed else 0
            elif status in {FieldStatus.CONFIRMED, FieldStatus.INFERRED_OK, FieldStatus.UNKNOWN}:
                done += 1
        rows.append(
            SectionProgress(
                section=section,
                label=SECTION_LABELS[section],
                total=len(specs),
                done=done,
                active=section == active,
            )
        )
    return rows


def suggested_value(record: IntakeRecord, spec: QuestionSpec) -> object:
    """Pre-select a low-confidence inference so the user only has to confirm it."""
    field = record.get_field(spec.field)
    if field.value is None or field.value == UNKNOWN:
        return None
    return field.value
