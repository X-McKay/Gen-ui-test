"""Gap analysis and gate logic."""

from __future__ import annotations

import pytest

from app.intake.gap_analysis import (
    FieldStatus,
    assumptions,
    field_status,
    gate_open,
    is_complete,
    next_questions,
    open_questions,
    section_progress,
)
from app.intake.question_bank import QUESTION_BANK, QUESTIONS_BY_FIELD, spec_for
from app.intake.schema import new_record


def test_gates_are_asked_first_and_batched() -> None:
    record = new_record("t")
    fields = [spec.field for spec in next_questions(record)]
    assert fields == [
        "ai_system.uses_ai",
        "data.processes_personal_data",
        "use_case.domains",
    ]
    assert all(QUESTIONS_BY_FIELD[field].is_gate for field in fields)


def test_at_most_three_questions_from_one_section() -> None:
    record = new_record("t")
    for path, value in {
        "ai_system.uses_ai": True,
        "data.processes_personal_data": False,
        "use_case.domains": ["other"],
        "use_case.affects_legal_or_significant_effects": False,
    }.items():
        record.set_field(path, value, source="user", confidence=1.0, confirmed=True)
    specs = next_questions(record)
    assert 1 <= len(specs) <= 3
    assert len({spec.section for spec in specs}) == 1


def test_negative_personal_data_gate_skips_data_details() -> None:
    record = new_record("t")
    record.set_field(
        "data.processes_personal_data", False, source="user", confidence=1.0, confirmed=True
    )
    for field in (
        "data.special_category_data",
        "data.data_subjects",
        "data.biometric_identification",
        "data.trains_on_personal_data",
    ):
        assert not gate_open(record, spec_for(field))
        assert field_status(record, spec_for(field)) is FieldStatus.SKIPPED


def test_list_gates_open_on_any_selected_item() -> None:
    record = new_record("t")
    acts = spec_for("use_case.acts_on_the_world")
    exposure = spec_for("use_case.financial_exposure")
    assert not gate_open(record, acts) and not gate_open(record, exposure)
    record.set_field(
        "ai_system.autonomy_level", "assistive", source="user", confidence=1.0, confirmed=True
    )
    assert field_status(record, acts) is FieldStatus.SKIPPED
    record.set_field(
        "ai_system.autonomy_level", "recommends", source="user", confidence=1.0, confirmed=True
    )
    assert field_status(record, acts) is FieldStatus.MISSING
    record.set_field(
        "use_case.acts_on_the_world", ["none"], source="user", confidence=1.0, confirmed=True
    )
    assert field_status(record, exposure) is FieldStatus.SKIPPED
    record.set_field(
        "use_case.acts_on_the_world",
        ["physical_or_system_actions", "financial_transactions"],
        source="user",
        confidence=1.0,
        confirmed=True,
    )
    assert field_status(record, exposure) is FieldStatus.MISSING


def test_unknown_gate_closes_dependents() -> None:
    record = new_record("t")
    record.set_field(
        "data.processes_personal_data", "unknown", source="user", confidence=1.0, confirmed=True
    )
    assert not gate_open(record, spec_for("data.special_category_data"))
    assert "data.processes_personal_data" in open_questions(record)


@pytest.mark.parametrize(
    ("confidence", "confirmed", "expected"),
    [
        (0.95, False, FieldStatus.INFERRED_OK),
        (0.5, False, FieldStatus.LOW_CONFIDENCE),
        (0.5, True, FieldStatus.CONFIRMED),
    ],
)
def test_confidence_threshold(confidence: float, confirmed: bool, expected: FieldStatus) -> None:
    record = new_record("t")
    record.set_field(
        "project.lifecycle_stage",
        "pilot",
        source="inferred",
        confidence=confidence,
        confirmed=confirmed,
    )
    assert field_status(record, spec_for("project.lifecycle_stage")) is expected


def test_must_confirm_fields_need_confirmation_regardless_of_confidence() -> None:
    record = new_record("t")
    record.set_field(
        "data.processes_personal_data", True, source="user", confidence=1.0, confirmed=True
    )
    record.set_field(
        "data.biometric_identification", False, source="inferred", confidence=0.99, confirmed=False
    )
    assert (
        field_status(record, spec_for("data.biometric_identification"))
        is FieldStatus.NEEDS_CONFIRMATION
    )
    chips = {chip.field: chip for chip in assumptions(record)}
    assert chips["data.biometric_identification"].must_confirm is True
    # A chip is never also asked as a question in the same step.
    assert "data.biometric_identification" not in {spec.field for spec in next_questions(record)}


def test_conditional_must_confirm_for_annex_iii_domains_and_minors() -> None:
    record = new_record("t")
    record.set_field(
        "use_case.domains", ["other"], source="inferred", confidence=0.9, confirmed=False
    )
    assert field_status(record, spec_for("use_case.domains")) is FieldStatus.INFERRED_OK
    record.set_field(
        "use_case.domains", ["hr_employment"], source="inferred", confidence=0.9, confirmed=False
    )
    assert field_status(record, spec_for("use_case.domains")) is FieldStatus.NEEDS_CONFIRMATION
    record.set_field(
        "data.processes_personal_data", True, source="user", confidence=1.0, confirmed=True
    )
    record.set_field(
        "data.data_subjects", ["customers"], source="inferred", confidence=0.9, confirmed=False
    )
    assert field_status(record, spec_for("data.data_subjects")) is FieldStatus.INFERRED_OK
    record.set_field(
        "data.data_subjects", ["minors"], source="inferred", confidence=0.9, confirmed=False
    )
    assert field_status(record, spec_for("data.data_subjects")) is FieldStatus.NEEDS_CONFIRMATION


def test_optional_fields_never_become_chips_or_questions() -> None:
    record = new_record("t")
    record.set_field(
        "project.team", "Platform", source="inferred", confidence=0.95, confirmed=False
    )
    assert "project.team" not in {chip.field for chip in assumptions(record)}
    assert "project.team" not in {spec.field for spec in next_questions(record)}


def test_completion_rule_allows_unknown_and_confident_inferences() -> None:
    record = new_record("t")
    for spec in QUESTION_BANK:
        if not spec.required:
            continue
        if spec.must_confirm:
            record.set_field(spec.field, "unknown", source="user", confidence=1.0, confirmed=True)
        elif spec.control == "yes_no":
            record.set_field(spec.field, False, source="inferred", confidence=0.85, confirmed=False)
        elif spec.control == "choice":
            record.set_field(
                spec.field,
                spec.options[0].value,
                source="inferred",
                confidence=0.85,
                confirmed=False,
            )
        elif spec.control == "multi":
            record.set_field(
                spec.field,
                [spec.options[0].value],
                source="inferred",
                confidence=0.85,
                confirmed=False,
            )
        else:
            record.set_field(spec.field, "x", source="inferred", confidence=0.85, confirmed=False)
    assert is_complete(record)
    assert next_questions(record) == []
    assert set(open_questions(record)) >= {"use_case.domains", "data.special_category_data"}


def test_section_progress_marks_active_and_counts_required_only() -> None:
    record = new_record("t")
    rows = {
        row.section: row
        for row in section_progress(record, active=spec_for("project.name").section)
    }
    assert rows["project"].active is True
    assert rows["project"].total == sum(
        1 for s in QUESTION_BANK if s.section == "project" and s.required
    )
    assert rows["data"].done == 0
