"""The intake assessment eval: dataset soundness, scoring rules, gates and the mock run."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.inference.structured_extraction import ExtractedField
from evals.intake_assessment.cases import (
    AssessmentCase,
    DatasetError,
    load_suite,
    validate_case,
)
from evals.intake_assessment.runner import (
    Baseline,
    Thresholds,
    evaluate_gates,
    run_suite,
    summarise_case,
    summarise_suite,
)
from evals.intake_assessment.scoring import direction, score_case

CHATBOT = AssessmentCase(
    id="t-chatbot",
    description="A public chatbot on our website answering product questions with GPT-4o.",
    expected={
        "ai_system.uses_ai": True,
        "ai_system.gpai_model_used": True,
        "project.target_users": "public",
        "use_case.interacts_directly_with_people": True,
        "use_case.generates_synthetic_content": True,
        "ai_system.model_source": "third_party_api",
        "data.processes_personal_data": True,
        "controls.in_place": ["guardrails"],
    },
    absent=["project.lifecycle_stage"],
    inherent="high",
    residual="medium",
)


def fields(**values: object) -> list[ExtractedField]:
    return [
        ExtractedField(path=path, value=value, confidence=0.9) for path, value in values.items()
    ]


def test_dataset_loads_and_every_case_agrees_with_the_engine() -> None:
    cases = load_suite("facts")
    assert len(cases) >= 20
    assert all(validate_case(case) == [] for case in cases)
    tags = {tag for case in cases for tag in case.tags}
    assert {"trap", "planned-controls", "prohibited", "noai", "biometric"} <= tags


def test_validate_case_reports_tier_disagreement_and_unknown_fields() -> None:
    wrong = CHATBOT.model_copy(update={"inherent": "low", "absent": ["nope.field"]})
    problems = validate_case(wrong)
    assert any("engine says inherent" in p for p in problems)
    assert any("unknown field" in p for p in problems)
    with pytest.raises(DatasetError):
        load_suite("does-not-exist")


@pytest.mark.parametrize(
    ("field", "expected", "predicted", "where"),
    [
        ("data.biometric_identification", False, True, "riskier"),
        ("data.biometric_identification", True, False, "safer"),
        ("project.target_users", "internal", "public", "riskier"),
        ("ai_system.autonomy_level", "decides", "assistive", "safer"),
        ("use_case.domains", ["other"], ["hr_employment"], "riskier"),
        ("data.special_category_data", ["health"], [], "safer"),
        ("data.data_subjects", ["employees"], ["minors"], "riskier"),
        ("project.name", "a", "b", "different"),
        ("use_case.domains", ["other"], ["other"], "same"),
    ],
)
def test_direction(field: str, expected: object, predicted: object, where: str) -> None:
    assert direction(field, expected, predicted) == where


def test_perfect_extraction_passes() -> None:
    score = score_case(CHATBOT, fields(**CHATBOT.expected))
    assert score.passed
    assert score.correct_count == len(CHATBOT.expected)
    assert score.inherent.relation == "exact" and score.residual.relation == "exact"


def test_planned_control_is_a_control_false_positive() -> None:
    extracted = fields(
        **{**CHATBOT.expected, "controls.in_place": ["guardrails", "abuse_monitoring"]}
    )
    score = score_case(CHATBOT, extracted)
    assert score.control_false_positives == 1
    assert not score.passed
    unlisted = AssessmentCase(
        **{
            **CHATBOT.model_dump(),
            "expected": {k: v for k, v in CHATBOT.expected.items() if k != "controls.in_place"},
            "residual": "high",
        }
    )
    score = score_case(
        unlisted, fields(**{**unlisted.expected, "controls.in_place": ["guardrails"]})
    )
    assert score.control_false_positives == 1


def test_sensitive_false_positive_and_missed_risk() -> None:
    too_strict = fields(**{**CHATBOT.expected, "data.biometric_identification": True})
    score = score_case(CHATBOT, too_strict)
    assert score.risk_false_positives == 1 and score.inherent.relation != "under"
    unanswered = fields(
        **{
            k: v
            for k, v in CHATBOT.expected.items()
            if k != "use_case.interacts_directly_with_people"
        }
    )
    score = score_case(CHATBOT, unanswered)
    assert score.risks_unanswered == 1 and score.risks_missed == 0
    assert score.inherent.relation == "under"
    silent = fields(**{**CHATBOT.expected, "use_case.interacts_directly_with_people": False})
    score = score_case(CHATBOT, silent)
    assert score.risks_missed == 1 and score.risks_unanswered == 0 and not score.passed
    low_confidence = [
        ExtractedField(path="use_case.social_scoring", value=True, confidence=0.3),
        *fields(**CHATBOT.expected),
    ]
    assert score_case(CHATBOT, low_confidence).risk_false_positives == 0


def test_unsupported_values_and_invalid_fields_are_counted() -> None:
    extra = [
        ExtractedField(path="project.lifecycle_stage", value="production", confidence=0.9),
        ExtractedField(path="use_case.domains", value=["not-a-domain"], confidence=0.9),
        *fields(**CHATBOT.expected),
    ]
    score = score_case(CHATBOT, extra)
    assert score.unsupported == 1
    assert score.invalid_fields == ["use_case.domains"]
    assert not score.passed


def test_gates_and_regression() -> None:
    perfect = summarise_suite([score_case(CHATBOT, fields(**CHATBOT.expected))])
    baseline = Baseline(suite="t", accepted={"pass_rate": 1.0})
    assert all(g.passed for g in evaluate_gates(perfect, baseline))
    bad = summarise_suite(
        [
            score_case(
                CHATBOT,
                fields(
                    **{**CHATBOT.expected, "controls.in_place": ["guardrails", "incident_response"]}
                ),
            )
        ]
    )
    gates = {g.name: g for g in evaluate_gates(bad, baseline)}
    assert (
        not gates["control_false_positives"].passed
        and gates["control_false_positives"].kind == "hard"
    )
    assert not gates["pass_rate_vs_baseline"].passed
    assert Thresholds().control_false_positives_max == 0


@pytest.mark.asyncio
async def test_mock_run_writes_an_experiment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import settings as settings_module

    monkeypatch.setenv("MOCK_MODEL", "1")
    settings_module.get_settings.cache_clear()
    try:
        experiment = await run_suite(
            "facts",
            repeats=1,
            case_ids=["noai-dashboard-ai-in-name", "genai-internal-copilot"],
            out_dir=tmp_path,
        )
    finally:
        settings_module.get_settings.cache_clear()
    assert experiment.model_id == "mock" and experiment.summary.runs == 2
    assert (tmp_path / experiment.experiment_id / "summary.md").exists()
    assert len(experiment.cases) == 2


@pytest.mark.asyncio
async def test_repository_case_runs_through_the_fact_finder(tmp_path: Path) -> None:
    from tests.risk_review.scripted_llm import ScriptedLlm, call, text

    model = ScriptedLlm.with_script(
        [
            call(
                "record_facts",
                {
                    "status": "completed",
                    "facts": [
                        {
                            "field": "ai_system.uses_ai",
                            "value": True,
                            "confidence": 0.9,
                            "basis": "code",
                            "evidence": [
                                {"file": "requirements.txt", "line": 3, "quote": "openai==1.51.0"}
                            ],
                        }
                    ],
                },
            ),
            text("Done."),
        ]
    )
    experiment = await run_suite(
        "repos", repeats=1, case_ids=["repo-hr-screening"], out_dir=tmp_path, model=model
    )
    [score] = experiment.scores
    assert score.case_id == "repo-hr-screening"
    assert any(f.field == "ai_system.uses_ai" and f.outcome == "correct" for f in score.fields)
    assert score.inherent.relation == "under"  # one fact is not enough
    assert experiment.summary.runs == 1


def test_confident_risk_value_on_an_unlisted_field_is_reported_not_gated() -> None:
    unlisted = "data.trains_on_personal_data"
    assert unlisted not in CHATBOT.expected and unlisted not in CHATBOT.absent
    extra = [
        ExtractedField(path=unlisted, value=True, confidence=0.9),
        ExtractedField(path="data.cross_border_transfer", value=True, confidence=0.5),
        *fields(**CHATBOT.expected),
    ]
    score = score_case(CHATBOT, extra)
    reported = [f for f in score.fields if f.outcome == "unlisted"]
    assert [f.field for f in reported] == [unlisted]
    assert reported[0].direction == "riskier"
    assert score.risk_false_positives == 0
    assert score.correct_count == len(CHATBOT.expected)
    summary = summarise_case(CHATBOT, [score])
    assert f"{unlisted}: unlisted riskier" in summary.worst_fields
