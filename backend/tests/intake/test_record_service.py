"""Record service: coercion, policies, persistence and classification refresh."""

from __future__ import annotations

from app.intake.record_service import (
    FieldUpdate,
    apply_updates,
    coerce_value,
    create_intake,
    get_record,
    mark_completed,
)
from app.intake.schema import UNKNOWN, IntakeMode


def test_coerce_values_from_the_ui() -> None:
    assert coerce_value("data.processes_personal_data", "yes") is True
    assert coerce_value("data.processes_personal_data", "No") is False
    assert coerce_value("data.processes_personal_data", "not sure") == UNKNOWN
    assert coerce_value("use_case.domains", "hr_employment, other") == ["hr_employment", "other"]
    assert coerce_value("project.lifecycle_stage", ["pilot"]) == "pilot"
    assert coerce_value("project.name", "Intake") == "Intake"


def test_inferred_updates_never_overwrite_user_values() -> None:
    record = create_intake(IntakeMode.NEW, owner="al")
    record, applied, _ = apply_updates(
        record, [FieldUpdate(path="ai_system.uses_ai", value=True)], policy="user"
    )
    assert applied == ["ai_system.uses_ai"]
    record, applied, _ = apply_updates(
        record,
        [
            FieldUpdate(
                path="ai_system.uses_ai",
                value=False,
                source="inferred",
                confidence=0.9,
                confirmed=False,
            )
        ],
        policy="inferred",
    )
    assert applied == []
    assert record.ai_system.uses_ai.value is True
    assert record.ai_system.uses_ai.source == "user"


def test_invalid_values_are_rejected_without_losing_the_rest() -> None:
    record = create_intake()
    record, applied, rejected = apply_updates(
        record,
        [
            FieldUpdate(path="project.lifecycle_stage", value="galactic"),
            FieldUpdate(path="nope.field", value=1),
            FieldUpdate(path="project.target_users", value="internal"),
        ],
    )
    assert applied == ["project.target_users"]
    assert len(rejected) == 2
    assert get_record(record.meta.intake_id).project.target_users.value == "internal"


def test_updates_reclassify_and_persist() -> None:
    record = create_intake()
    record, _, _ = apply_updates(
        record,
        [
            FieldUpdate(path="ai_system.uses_ai", value=True),
            FieldUpdate(path="use_case.domains", value=["hr_employment"]),
        ],
    )
    stored = get_record(record.meta.intake_id)
    assert stored.assessment.eu_ai_act.classification == "high_risk"
    assert stored.assessment.open_questions == []
    completed = mark_completed(stored)
    assert completed.meta.completed_at is not None
    assert completed.meta.status == "completed"


def test_unknown_is_stored_distinct_from_false() -> None:
    record = create_intake()
    record, _, _ = apply_updates(
        record, [FieldUpdate(path="ai_system.human_oversight", value=None)]
    )
    assert record.ai_system.human_oversight.value is None  # None means "not captured"
    record, _, _ = apply_updates(
        record, [FieldUpdate(path="ai_system.human_oversight", value=UNKNOWN)]
    )
    assert record.ai_system.human_oversight.value == UNKNOWN
    assert record.ai_system.human_oversight.value is not False
    assert "ai_system.human_oversight" in record.assessment.open_questions
