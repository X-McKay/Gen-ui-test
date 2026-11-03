"""The four tools drive a full interview against the mock extractor."""

from __future__ import annotations

from typing import Any, cast

import pytest
from google.adk.tools.tool_context import ToolContext

from app.agents.tools import (
    extract_intake_facts,
    finalize_intake,
    get_next_questions,
    update_intake_fields,
)
from app.agents.tools.context import RECORD_STATE_KEY, STEP_STATE_KEY
from app.intake.record_service import FieldUpdate, apply_updates, create_intake, get_record
from app.intake.schema import IntakeMode
from tests.agents.fake_tool_context import FakeToolContext

HR = (
    "An internal tool that drafts job-candidate summaries from CVs using an LLM via the "
    "OpenAI API. Recruiters read the summaries before deciding who to interview."
)
LOG = (
    "An internal log-search assistant. Engineers ask questions in natural language and it "
    "summarises matching log lines with a self-hosted LLM. It handles no personal data."
)


def _context(intake_id: str) -> ToolContext:
    return cast(ToolContext, FakeToolContext(intake_id))


def _answer(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for question in questions:
        control = question["control"]
        if control == "yes_no":
            fields.append({"path": question["field"], "value": False})
        elif control == "choice":
            fields.append({"path": question["field"], "value": question["options"][0]["value"]})
        elif control == "multi":
            fields.append({"path": question["field"], "value": [question["options"][0]["value"]]})
        else:
            fields.append({"path": question["field"], "value": "Sample"})
    return fields


async def _run_interview(description: str, *, not_sure: str | None = None) -> tuple[Any, int]:
    record = create_intake(IntakeMode.NEW, owner="al")
    apply_updates(
        record,
        [
            FieldUpdate(path="project.name", value="Probe"),
            FieldUpdate(path="project.description", value=description),
        ],
    )
    context = _context(record.meta.intake_id)
    extracted = await extract_intake_facts("", context)
    assert extracted["status"] == "ok"
    assert extracted["fields_filled"] > 5
    asked = 0
    for _ in range(10):
        step = get_next_questions(context)
        assert step["status"] == "ok"
        if step["done"]:
            break
        asked += len(step["questions"])
        fields = [{"path": chip["field"], "value": chip["value"]} for chip in step["assumptions"]]
        fields += _answer(step["questions"])
        if not_sure:
            fields = [f for f in fields if f["path"] != not_sure] + (
                [{"path": not_sure, "value": "unknown"}]
                if any(q["field"] == not_sure for q in step["questions"])
                else []
            )
        updated = update_intake_fields(fields, context)
        assert updated["status"] == "ok", updated
    final = finalize_intake(context)
    assert final["status"] == "ok"
    return get_record(record.meta.intake_id), asked


@pytest.mark.asyncio
async def test_hr_screening_reaches_high_risk_in_few_questions() -> None:
    record, asked = await _run_interview(HR, not_sure="ai_system.human_oversight")
    assert asked <= 8
    assert record.meta.question_count == asked
    assert record.assessment.eu_ai_act.classification == "high_risk"
    assert any(
        "Annex III 4" in category for category in record.assessment.eu_ai_act.annex_iii_categories
    )
    assert any(entry.field == "use_case.domains" for entry in record.assessment.eu_ai_act.rationale)
    assert "ai_system.human_oversight" in record.assessment.open_questions
    assert record.ai_system.human_oversight.value == "unknown"
    assert record.meta.status == "completed"


@pytest.mark.asyncio
async def test_log_search_is_minimal_in_four_questions_or_fewer() -> None:
    record, asked = await _run_interview(LOG)
    assert asked <= 4
    assert record.assessment.eu_ai_act.classification == "minimal"
    assert record.assessment.overall_risk_tier == "low"


@pytest.mark.asyncio
async def test_first_step_shows_chips_and_render_plan_targets_interview() -> None:
    record = create_intake(IntakeMode.NEW)
    apply_updates(record, [FieldUpdate(path="project.description", value=HR)])
    context = _context(record.meta.intake_id)
    await extract_intake_facts("", context)
    step = get_next_questions(context)
    assert step["assumptions"], "chips should precede questions"
    plan = step["render_plan"]
    assert plan["target"] == "interview"
    kinds = [next(k for k in op if k != "version") for op in plan["operations"]]
    assert kinds == ["createSurface", "updateComponents"]
    root = plan["operations"][0]["createSurface"]["components"][0]
    assert root["component"] == "InterviewStep"
    assert root["onSubmit"]["event"]["name"] == "submit_step"
    assert context.state[STEP_STATE_KEY]["surface_id"] == "step-1"
    assert context.state[RECORD_STATE_KEY]["meta"]["intake_id"] == record.meta.intake_id


@pytest.mark.asyncio
async def test_resume_replays_the_current_step_without_counting_again() -> None:
    record = create_intake(IntakeMode.NEW)
    apply_updates(record, [FieldUpdate(path="project.description", value=HR)])
    context = _context(record.meta.intake_id)
    await extract_intake_facts("", context)
    first = get_next_questions(context)
    count = get_record(record.meta.intake_id).meta.question_count
    resumed = get_next_questions(context, resume=True)
    assert resumed["surface_id"] == first["surface_id"]
    assert resumed["previous_surface_id"] is None
    assert [q["field"] for q in resumed["questions"]] == [q["field"] for q in first["questions"]]
    assert get_record(record.meta.intake_id).meta.question_count == count


def test_guardrail_fixture_adds_an_invalid_render_only_on_the_first_step() -> None:
    record = create_intake(IntakeMode.NEW)
    apply_updates(
        record,
        [FieldUpdate(path="project.description", value=f"{LOG} [[fixture:invalid-component]]")],
    )
    context = _context(record.meta.intake_id)
    step = get_next_questions(context)
    assert step["fixture"]["name"] == "invalid-component"
    invalid = step["fixture"]["operations"][0]["createSurface"]["components"][0]
    assert invalid["component"] == "Marquee"
    update_intake_fields(_answer(step["questions"]), context)
    assert "fixture" not in get_next_questions(context)


def test_inferred_prohibited_signal_is_a_chip_not_an_escalation() -> None:
    record = create_intake(IntakeMode.NEW)
    apply_updates(
        record,
        [
            FieldUpdate(
                path="ai_system.uses_ai",
                value=True,
                source="inferred",
                confidence=0.9,
                confirmed=False,
            ),
            FieldUpdate(
                path="use_case.social_scoring",
                value=True,
                source="inferred",
                confidence=0.8,
                confirmed=False,
            ),
        ],
        policy="inferred",
    )
    context = _context(record.meta.intake_id)
    step = get_next_questions(context)
    assert step["kind"] == "interview"
    assert "use_case.social_scoring" in {chip["field"] for chip in step["assumptions"]}
    update_intake_fields([{"path": "use_case.social_scoring", "value": True}], context)
    escalation = get_next_questions(context)
    assert escalation["kind"] == "escalation"
    root = escalation["render_plan"]["operations"][-1]["createSurface"]["components"][0]
    assert root["component"] == "EscalationNotice"
    assert get_record(record.meta.intake_id).meta.status == "escalated"


def test_tools_report_missing_intake_instead_of_raising() -> None:
    context = _context("does-not-exist")
    assert get_next_questions(context)["status"] == "error"
    assert (
        update_intake_fields([{"path": "ai_system.uses_ai", "value": True}], context)["status"]
        == "error"
    )
    assert finalize_intake(context)["status"] == "error"


def test_update_rejects_empty_input_and_coerces_not_sure() -> None:
    record = create_intake(IntakeMode.NEW)
    context = _context(record.meta.intake_id)
    assert update_intake_fields([], context)["status"] == "error"
    result = update_intake_fields([{"path": "ai_system.uses_ai", "value": None}], context)
    assert result["applied"] == ["ai_system.uses_ai"]
    assert get_record(record.meta.intake_id).ai_system.uses_ai.value == "unknown"
