"""Fact finder: value validation and grounding in record_facts, fact merging, the assessment
workflow on a scripted model, and the report renderer."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from risk_review.agents.fact_finder.factory import available_fact_lanes, build_fact_finder
from risk_review.agents.fact_finder.tools.record_facts import (
    LANE_KEY,
    OUTPUT_KEY,
    RecordFactsTool,
    check_value,
    field_catalogue,
)
from risk_review.agents.fact_finder.types import Fact, FactsOutput
from risk_review.observability.report import render_assessment_markdown
from risk_review.observability.trace import RunMetrics
from risk_review.settings import RiskReviewSettings
from risk_review.tools.repo.service import RepoService
from risk_review.workflows.assess import LaneFacts, build_record, merge_facts, run_assessment
from tests.risk_review.scripted_llm import ScriptedLlm, call, text

EVIDENCE = {"file": "backend/app/api.py", "line": 5, "quote": 'logger.info("intake.create'}


def _fact(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "field": "data.processes_personal_data",
        "value": True,
        "confidence": 0.9,
        "basis": "code",
        "evidence": [EVIDENCE],
    }
    base.update(overrides)
    return base


def _context(**state: Any) -> Any:
    return SimpleNamespace(state=dict(state))


def test_field_catalogue_lists_every_askable_field_with_its_values() -> None:
    catalogue = field_catalogue()
    assert "- data.processes_personal_data: boolean" in catalogue
    assert "- controls.in_place: list of guardrails, access_controls" in catalogue
    assert "- project.third_party_services: short text" in catalogue


@pytest.mark.parametrize(
    ("overrides", "problem"),
    [
        ({"field": "nope.field"}, "not a record field"),
        ({"value": "unknown"}, "never record unknown"),
        ({"field": "use_case.domains", "value": ["space"]}, "use_case.domains"),
        ({"basis": "absence", "confidence": 0.9}, "at most 0.7"),
    ],
)
def test_check_value_rejects_bad_facts(overrides: dict[str, Any], problem: str) -> None:
    message = check_value(Fact.model_validate(_fact(**overrides)))
    assert message is not None and problem in message


def test_check_value_coerces_like_the_product() -> None:
    assert check_value(Fact.model_validate(_fact(value="yes"))) is None
    assert (
        check_value(
            Fact.model_validate(_fact(field="use_case.domains", value="hr_employment,other"))
        )
        is None
    )
    assert (
        check_value(Fact.model_validate(_fact(basis="absence", confidence=0.6, value=False)))
        is None
    )


@pytest.mark.asyncio
async def test_record_facts_grounds_and_accumulates(tiny_repo: Path) -> None:
    tool = RecordFactsTool(RepoService(tiny_repo))
    context = _context(**{LANE_KEY: "data-and-privacy"})
    first = await tool.run_async(
        args={
            "status": "completed",
            "facts": [
                _fact(),
                _fact(
                    field="ai_system.uses_ai",
                    value=True,
                    evidence=[{**EVIDENCE, "quote": "not this line"}],
                ),
                _fact(field="project.lifecycle_stage", value="beta"),
            ],
            "files_examined": ["backend/app/api.py"],
        },
        tool_context=context,
    )
    assert first["ok"] and first["accepted"] == 1
    assert [r["field"] for r in first["rejected"]] == [
        "ai_system.uses_ai",
        "project.lifecycle_stage",
    ]
    second = await tool.run_async(
        args={
            "status": "completed",
            "facts": [_fact(value=False, confidence=0.7, basis="documented")],
        },
        tool_context=context,
    )
    assert second["total_recorded"] == 1
    output = FactsOutput.model_validate(context.state[OUTPUT_KEY])
    assert output.lane == "data-and-privacy"
    assert output.facts[0].value is False and output.files_examined == ["backend/app/api.py"]


def _lane(lane: str, *facts: dict[str, Any]) -> LaneFacts:
    return LaneFacts(
        lane=lane,
        status="completed",
        metrics=RunMetrics(
            run_id="r", agent="fact-finder", manifest_id="m", outcome="success", started_at="t"
        ),
        facts=[Fact.model_validate(_fact(**f)) for f in facts],
    )


def test_merge_prefers_confidence_and_keeps_conflicts() -> None:
    merged = merge_facts(
        [
            _lane("a", {"confidence": 0.8}, {"field": "ai_system.uses_ai", "value": True}),
            _lane("b", {"value": False, "confidence": 0.95, "basis": "documented"}),
        ]
    )
    by_field = {m.field: m for m in merged}
    assert by_field["data.processes_personal_data"].value is False
    assert by_field["data.processes_personal_data"].lane == "b"
    assert by_field["data.processes_personal_data"].conflicts == ["a: True (0.80)"]
    assert by_field["ai_system.uses_ai"].conflicts == []
    assert [m.field for m in merged] == ["ai_system.uses_ai", "data.processes_personal_data"]


def test_owning_lane_wins_whatever_the_confidence() -> None:
    merged = merge_facts(
        [
            _lane(
                "data-and-privacy",
                {"field": "controls.in_place", "value": ["pii_minimisation"], "confidence": 0.9},
            ),
            _lane(
                "controls-in-code",
                {
                    "field": "controls.in_place",
                    "value": ["none"],
                    "confidence": 0.7,
                    "basis": "absence",
                },
            ),
        ]
    )
    [controls] = merged
    assert controls.lane == "controls-in-code" and controls.value == ["none"]
    assert controls.conflicts == ["data-and-privacy: ['pii_minimisation'] (0.90)"]


def test_build_record_marks_provenance_and_rejects_bad_values() -> None:
    merged = merge_facts([_lane("a", {}, {"field": "ai_system.uses_ai", "value": True})])
    record, rejected = build_record(merged, confirmed=False)
    field = record.get_field("data.processes_personal_data")
    assert field.source == "repo:backend/app/api.py" and not field.confirmed
    assert rejected == []
    assert record.assessment.inherent_risk.score == 2


@pytest.mark.asyncio
async def test_assessment_workflow_on_a_scripted_model(tiny_repo: Path, tmp_path: Path) -> None:
    model = ScriptedLlm.with_script(
        [
            call(
                "record_facts",
                {
                    "status": "completed",
                    "facts": [
                        _fact(field="ai_system.uses_ai", value=True),
                        _fact(field="ai_system.gpai_model_used", value=True),
                        _fact(field="project.target_users", value="public"),
                        _fact(field="use_case.interacts_directly_with_people", value=True),
                        _fact(field="controls.in_place", value=["guardrails"]),
                    ],
                    "files_examined": ["backend/app/api.py"],
                },
            ),
            text("Done."),
        ]
    )
    settings = RiskReviewSettings(concurrency=2, step_timeout_s=60)
    report = await run_assessment(
        repository_root=tiny_repo,
        repository_label="tiny",
        lanes=["ai-usage"],
        settings=settings,
        trace_path=tmp_path / "trace.jsonl",
        model=model,
    )
    assert [lane.status for lane in report.lanes] == ["completed"]
    assert {f.field for f in report.facts} >= {"ai_system.uses_ai", "controls.in_place"}
    assert report.assessment.inherent_risk.tier.value == "medium"
    assert report.assessment.residual_risk.tier.value == "medium"  # guardrails unconfirmed
    assert report.residual_if_confirmed.value == "low"
    assert "data.processes_personal_data" in report.open_questions
    assert report.totals.model_requests == 2 and report.totals.tool_calls == 1
    markdown = render_assessment_markdown(report)
    assert "Residual risk if claimed controls are confirmed | **low**" in markdown
    assert "backend/app/api.py:5" in markdown and "## Open questions" in markdown


def test_factory_builds_every_lane(tiny_repo: Path) -> None:
    assert available_fact_lanes() == [
        "ai-usage",
        "controls-in-code",
        "data-and-privacy",
        "purpose-and-users",
        "third-party-services",
    ]
    built = build_fact_finder(lane="data-and-privacy", repository_root=tiny_repo)
    assert "record_facts" in built.manifest.tools and len(built.active_skills) == 2
