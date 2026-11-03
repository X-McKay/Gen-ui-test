"""Load, change and persist intake records. Every change re-runs classification."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.governance.classify import reclassify
from app.intake import intake_store
from app.intake.question_bank import QUESTIONS_BY_FIELD
from app.intake.schema import (
    UNKNOWN,
    FieldMeta,
    IntakeMode,
    IntakeRecord,
    IntakeStatus,
    new_record,
)


class FieldUpdate(BaseModel):
    """One change to the record, from the user, the extractor or the repository analyser."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(description="Dotted path, e.g. 'data.processes_personal_data'")
    value: object = Field(description="New value; 'unknown' means the user is not sure")
    source: str = Field(default="user", description="user | inferred | repo:<path>")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    confirmed: bool = True


class IntakeNotFoundError(LookupError):
    pass


def create_intake(
    mode: IntakeMode = IntakeMode.NEW,
    *,
    owner: str | None = None,
    repo_url: str | None = None,
    intake_id: str | None = None,
) -> IntakeRecord:
    record = new_record(intake_id or uuid.uuid4().hex[:12], mode)
    record.meta.repo_url = repo_url
    if owner:
        record.set_field("project.owner", owner, source="inferred", confidence=0.9, confirmed=False)
    reclassify(record)
    intake_store.save_record(record)
    return record


def get_record(intake_id: str) -> IntakeRecord:
    record = intake_store.load_record(intake_id)
    if record is None:
        raise IntakeNotFoundError(intake_id)
    return record


def coerce_value(path: str, value: object) -> object:
    """Normalise values coming from the UI or the model before validation."""
    if value == UNKNOWN or value is None:
        return value
    spec = QUESTIONS_BY_FIELD.get(path)
    if spec is None:
        return value
    if spec.control == "yes_no":
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"yes", "true", "y"}:
                return True
            if lowered in {"no", "false", "n"}:
                return False
            if lowered in {"not sure", "not_sure", "unsure", "unknown"}:
                return UNKNOWN
        return value
    if spec.control == "multi":
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value
    if spec.control == "choice" and isinstance(value, list) and len(value) == 1:
        return value[0]
    return value


def apply_updates(
    record: IntakeRecord,
    updates: list[FieldUpdate],
    *,
    policy: Literal["user", "inferred"] = "user",
) -> tuple[IntakeRecord, list[str], list[str]]:
    """Apply updates. Returns ``(record, applied_paths, rejected_messages)``.

    ``policy="inferred"`` never overwrites a user-confirmed value; ``policy="user"`` always wins.
    """
    applied: list[str] = []
    rejected: list[str] = []
    for update in updates:
        try:
            current: FieldMeta[object] = record.get_field(update.path)
        except KeyError:
            rejected.append(f"{update.path}: unknown field")
            continue
        if policy == "inferred" and (current.confirmed or current.source == "user"):
            continue
        try:
            record.set_field(
                update.path,
                coerce_value(update.path, update.value),
                source=update.source,
                confidence=update.confidence,
                confirmed=update.confirmed,
            )
        except ValueError as error:
            rejected.append(f"{update.path}: {str(error).splitlines()[0]}")
            continue
        applied.append(update.path)
    reclassify(record)
    intake_store.save_record(record)
    return record, applied, rejected


def mark_completed(record: IntakeRecord) -> IntakeRecord:
    record.meta.completed_at = datetime.now(UTC)
    if record.meta.status == IntakeStatus.IN_PROGRESS:
        record.meta.status = IntakeStatus.COMPLETED
    reclassify(record)
    intake_store.save_record(record, current_step=None)
    return record


def mark_submitted(record: IntakeRecord) -> IntakeRecord:
    record.meta.submitted_at = datetime.now(UTC)
    record.meta.status = IntakeStatus.SUBMITTED
    intake_store.save_record(record)
    return record


def set_progress(record: IntakeRecord, text: str | None) -> IntakeRecord:
    record.meta.analysis_progress = text
    intake_store.save_record(record)
    return record
