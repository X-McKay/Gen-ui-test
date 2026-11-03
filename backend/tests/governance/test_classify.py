"""The aggregator: tiers, floors, deduplication, ordering and the two reference scenarios."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace

import pytest

from app.governance import classify as classify_module
from app.governance.classify import TIER_BY_CLASSIFICATION, classify, raise_tier, reclassify
from app.governance.eu_ai_act import ESCALATION_STEP, HIGH_RISK_OBLIGATIONS
from app.governance.frameworks import FrameworkResult
from app.intake.schema import (
    AutonomyLevel,
    DataSubject,
    Domain,
    EuAiActAssessment,
    EuAiActClassification,
    IntakeRecord,
    Obligation,
    RiskTier,
    SpecialCategory,
    TargetUsers,
)

RecordFactory = Callable[..., IntakeRecord]

EMPLOYMENT_CATEGORY = "Annex III 4 — Employment, workers management and access to self-employment"


# --- Tier mapping and floors --------------------------------------------------------------


@pytest.mark.parametrize(
    ("values", "classification", "tier"),
    [
        ({"use_case.social_scoring": True}, EuAiActClassification.PROHIBITED, RiskTier.CRITICAL),
        ({"use_case.domains": [Domain.EDUCATION]}, EuAiActClassification.HIGH_RISK, RiskTier.HIGH),
        (
            {"use_case.interacts_directly_with_people": True},
            EuAiActClassification.LIMITED_TRANSPARENCY,
            RiskTier.MEDIUM,
        ),
        ({}, EuAiActClassification.MINIMAL, RiskTier.LOW),
    ],
    ids=["prohibited", "high-risk", "limited", "minimal"],
)
def test_overall_tier_follows_classification(
    values: dict[str, object],
    classification: EuAiActClassification,
    tier: RiskTier,
    make_record: RecordFactory,
) -> None:
    assessment = classify(make_record(values))
    assert assessment.eu_ai_act.classification is classification
    assert assessment.overall_risk_tier is tier
    assert TIER_BY_CLASSIFICATION[classification] is tier


def test_tier_mapping_is_complete() -> None:
    assert set(TIER_BY_CLASSIFICATION) == set(EuAiActClassification)


@pytest.mark.parametrize(
    ("current", "floor", "expected"),
    [
        (RiskTier.LOW, None, RiskTier.LOW),
        (RiskTier.LOW, RiskTier.MEDIUM, RiskTier.MEDIUM),
        (RiskTier.MEDIUM, RiskTier.MEDIUM, RiskTier.MEDIUM),
        (RiskTier.HIGH, RiskTier.MEDIUM, RiskTier.HIGH),
        (RiskTier.CRITICAL, RiskTier.HIGH, RiskTier.CRITICAL),
    ],
)
def test_raise_tier(current: RiskTier, floor: RiskTier | None, expected: RiskTier) -> None:
    assert raise_tier(current, floor) is expected


def test_internal_policy_floor_raises_minimal_to_medium(make_record: RecordFactory) -> None:
    record = make_record(
        {"ai_system.uses_ai": True, "ai_system.autonomy_level": AutonomyLevel.DECIDES}
    )
    assessment = classify(record)
    assert assessment.eu_ai_act.classification is EuAiActClassification.MINIMAL
    assert assessment.overall_risk_tier is RiskTier.MEDIUM


def test_gdpr_floor_raises_minimal_to_medium(make_record: RecordFactory) -> None:
    record = make_record(
        {"data.processes_personal_data": True, "data.data_subjects": [DataSubject.MINORS]}
    )
    assert classify(record).overall_risk_tier is RiskTier.MEDIUM


def test_floor_never_lowers_a_high_tier(make_record: RecordFactory) -> None:
    record = make_record(
        {
            "use_case.domains": [Domain.CREDIT_INSURANCE],
            "data.processes_personal_data": True,
            "data.special_category_data": [SpecialCategory.HEALTH],
        }
    )
    assert classify(record).overall_risk_tier is RiskTier.HIGH


# --- Framework applicability and ordering ---------------------------------------------------


def test_blank_record_lists_eu_ai_act_and_internal_policy(make_record: RecordFactory) -> None:
    assessment = classify(make_record())
    assert assessment.applicable_frameworks == ["EU AI Act", "Internal AI policy"]
    assert assessment.overall_risk_tier is RiskTier.LOW
    assert assessment.open_questions == []


def test_all_frameworks_in_stable_order(make_record: RecordFactory) -> None:
    record = make_record(
        {
            "ai_system.uses_ai": True,
            "data.processes_personal_data": True,
            "project.lifecycle_stage": "production",
        }
    )
    assert classify(record).applicable_frameworks == [
        "EU AI Act",
        "GDPR",
        "NIST AI RMF",
        "ISO/IEC 42001",
        "Internal AI policy",
    ]


def test_obligations_start_with_eu_ai_act(make_record: RecordFactory) -> None:
    record = make_record({"use_case.domains": [Domain.HR_EMPLOYMENT], "ai_system.uses_ai": True})
    frameworks = [item.framework for item in classify(record).obligations]
    eu_count = frameworks.count("EU AI Act")
    assert eu_count == len(HIGH_RISK_OBLIGATIONS)
    assert frameworks[:eu_count] == ["EU AI Act"] * eu_count
    assert frameworks[eu_count:] == sorted(
        frameworks[eu_count:], key=["NIST AI RMF", "Internal AI policy"].index
    )


def test_escalation_is_the_first_next_step(make_record: RecordFactory) -> None:
    record = make_record(
        {
            "use_case.social_scoring": True,
            "data.processes_personal_data": True,
            "data.trains_on_personal_data": True,
        }
    )
    steps = classify(record).recommended_next_steps
    assert steps[0] == ESCALATION_STEP
    assert steps.count(ESCALATION_STEP) == 1
    assert len(steps) > 1


def test_dedup_across_modules(make_record: RecordFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """A module that repeats EU AI Act output and names is folded in, not doubled."""
    duplicate = HIGH_RISK_OBLIGATIONS[0]

    def evaluate(record: IntakeRecord, eu: EuAiActAssessment) -> FrameworkResult:
        return FrameworkResult(
            applies=True,
            obligations=[duplicate, Obligation(framework="Echo", text="extra")],
            next_steps=[ESCALATION_STEP, "Do the extra thing", "Do the extra thing"],
            tier_floor=RiskTier.CRITICAL,
            additional_frameworks=["EU AI Act", "Echo law"],
        )

    echo = SimpleNamespace(name="EU AI Act", evaluate=evaluate)
    monkeypatch.setattr(classify_module, "FRAMEWORK_MODULES", [echo])

    assessment = classify(make_record({"use_case.domains": [Domain.EDUCATION]}))
    assert assessment.applicable_frameworks == ["EU AI Act", "Echo law"]
    assert assessment.obligations.count(duplicate) == 1
    assert assessment.obligations[-1].framework == "Echo"
    assert assessment.recommended_next_steps[0] == ESCALATION_STEP
    assert assessment.recommended_next_steps.count("Do the extra thing") == 1
    assert assessment.overall_risk_tier is RiskTier.CRITICAL


def test_non_applicable_module_contributes_nothing(
    make_record: RecordFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    silent = SimpleNamespace(
        name="Silent",
        evaluate=lambda record, eu: FrameworkResult(
            applies=False, obligations=[Obligation(framework="Silent", text="ignored")]
        ),
    )
    monkeypatch.setattr(classify_module, "FRAMEWORK_MODULES", [silent])
    assessment = classify(make_record())
    assert assessment.applicable_frameworks == ["EU AI Act"]
    assert assessment.obligations == []


# --- Open questions and reclassify ------------------------------------------------------------


def test_open_questions_passthrough(make_record: RecordFactory) -> None:
    record = make_record(
        {
            "use_case.social_scoring": "unknown",
            "data.processes_personal_data": "unknown",
            "ai_system.uses_ai": True,
        }
    )
    assessment = classify(record)
    assert assessment.open_questions == [
        "data.processes_personal_data",
        "use_case.social_scoring",
    ]
    assert assessment.eu_ai_act.classification is EuAiActClassification.MINIMAL


def test_reclassify_sets_assessment_in_place(make_record: RecordFactory) -> None:
    record = make_record({"use_case.domains": [Domain.HR_EMPLOYMENT]})
    assert record.assessment.overall_risk_tier is RiskTier.LOW
    returned = reclassify(record)
    assert returned is record
    assert record.assessment.overall_risk_tier is RiskTier.HIGH
    assert record.assessment == classify(record)


def test_classify_does_not_mutate_the_record(make_record: RecordFactory) -> None:
    record = make_record({"use_case.domains": [Domain.HR_EMPLOYMENT]})
    before = record.model_dump()
    classify(record)
    assert record.model_dump() == before


# --- Scenarios ------------------------------------------------------------------------------


def test_scenario_hr_cv_screening(make_record: RecordFactory) -> None:
    record = make_record(
        {
            "use_case.domains": [Domain.HR_EMPLOYMENT],
            "data.processes_personal_data": True,
            "data.data_subjects": [DataSubject.EMPLOYEES],
            "ai_system.uses_ai": True,
            "ai_system.gpai_model_used": True,
            "project.target_users": TargetUsers.INTERNAL,
        }
    )
    assessment = classify(record)
    eu = assessment.eu_ai_act
    assert eu.classification is EuAiActClassification.HIGH_RISK
    assert EMPLOYMENT_CATEGORY in eu.annex_iii_categories
    assert any(entry.field == "use_case.domains" for entry in eu.rationale)
    assert any(entry.effect == "note" for entry in eu.rationale), "GPAI note is present"
    assert assessment.overall_risk_tier is RiskTier.HIGH
    assert assessment.applicable_frameworks == [
        "EU AI Act",
        "GDPR",
        "NIST AI RMF",
        "Internal AI policy",
    ]
    references = [item.reference or "" for item in assessment.obligations]
    assert any("Art. 53" in reference for reference in references)
    assert any("GDPR Art. 35" in reference for reference in references), "DPIA for high-risk"
    assert any("bias" in item.text for item in assessment.obligations)
    assert ESCALATION_STEP not in assessment.recommended_next_steps


def test_scenario_internal_log_search_assistant(make_record: RecordFactory) -> None:
    record = make_record(
        {
            "ai_system.uses_ai": True,
            "ai_system.gpai_model_used": True,
            "data.processes_personal_data": False,
            "use_case.domains": [Domain.OTHER],
            "use_case.interacts_directly_with_people": True,
            "use_case.generates_synthetic_content": True,
            "project.target_users": TargetUsers.INTERNAL,
            "use_case.affects_legal_or_significant_effects": False,
        }
    )
    assessment = classify(record)
    assert assessment.eu_ai_act.classification is EuAiActClassification.MINIMAL
    assert assessment.overall_risk_tier is RiskTier.LOW
    assert assessment.eu_ai_act.annex_iii_categories == []
    assert "GDPR" not in assessment.applicable_frameworks
    texts = [item.text for item in assessment.obligations]
    assert "Tell staff they are interacting with an AI system" in texts
    assert "Mark AI-generated content that leaves the team" in texts
    assert all(entry.effect == "note" for entry in assessment.eu_ai_act.rationale)
