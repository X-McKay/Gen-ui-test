"""Inherent and residual risk: the point table, bands, floors and the confirmed-only rule."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from app.governance import risk_profile
from app.governance.classify import classify
from app.governance.risk_profile import (
    CONTROLS_IN_PLACE,
    HUMAN_OVERSIGHT,
    MITIGATION_CONTROLS,
    MITIGATIONS,
    Mitigation,
    apply_floor,
    control_status,
    inherent,
    residual,
    tier_for_score,
)
from app.intake.schema import (
    AutonomyLevel,
    ControlKind,
    DataSubject,
    Domain,
    EuAiActClassification,
    IntakeRecord,
    ModelSource,
    RiskTier,
    SpecialCategory,
    TargetUsers,
    new_record,
)

RecordFactory = Callable[..., IntakeRecord]


def make_record(
    values: dict[str, object], *, confirmed: bool = True, source: str = "user"
) -> IntakeRecord:
    record = new_record("risk")
    for path, value in values.items():
        record.set_field(path, value, source=source, confidence=0.9, confirmed=confirmed)
    return record


EXTERNAL_CHATBOT: dict[str, object] = {
    "ai_system.uses_ai": True,
    "project.target_users": TargetUsers.PUBLIC,
    "use_case.interacts_directly_with_people": True,
    "use_case.generates_synthetic_content": True,
    "ai_system.model_source": ModelSource.THIRD_PARTY_API,
    "ai_system.autonomy_level": AutonomyLevel.ASSISTIVE,
    "data.processes_personal_data": True,
}

ALL_CONTROLS = [kind for kind in ControlKind if kind is not ControlKind.NONE]
CONTROLS_ALL_ON: dict[str, object] = {
    "ai_system.human_oversight": True,
    "controls.in_place": ALL_CONTROLS,
}


# --- Bands and floors --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("score", "tier"),
    [
        (0, RiskTier.LOW),
        (3, RiskTier.LOW),
        (4, RiskTier.MEDIUM),
        (7, RiskTier.MEDIUM),
        (8, RiskTier.HIGH),
        (13, RiskTier.HIGH),
        (14, RiskTier.CRITICAL),
        (40, RiskTier.CRITICAL),
    ],
)
def test_tier_bands(score: int, tier: RiskTier) -> None:
    assert tier_for_score(score) is tier


def test_apply_floor_raises_only_upwards() -> None:
    assert apply_floor(RiskTier.LOW, (RiskTier.HIGH, "why")) == (
        RiskTier.HIGH,
        RiskTier.HIGH,
        "why",
    )
    assert apply_floor(RiskTier.CRITICAL, (RiskTier.HIGH, "why")) == (RiskTier.CRITICAL, None, None)
    assert apply_floor(RiskTier.LOW, None) == (RiskTier.LOW, None, None)


# --- Inherent drivers --------------------------------------------------------------------


def test_empty_record_has_no_drivers_and_is_low() -> None:
    profile = inherent(new_record("empty"), EuAiActClassification.MINIMAL)
    assert profile.score == 0 and profile.tier is RiskTier.LOW and profile.drivers == []


def test_unknown_answers_add_nothing() -> None:
    record = make_record(
        {
            path: "unknown"
            for path in (
                "project.target_users",
                "use_case.interacts_directly_with_people",
                "ai_system.autonomy_level",
                "ai_system.human_oversight",
                "data.processes_personal_data",
                "data.special_category_data",
                "data.biometric_identification",
                "data.data_subjects",
                "use_case.affects_legal_or_significant_effects",
                "use_case.domains",
            )
        }
    )
    assert inherent(record, EuAiActClassification.MINIMAL).score == 0


@pytest.mark.parametrize(
    ("values", "field", "points"),
    [
        ({"project.target_users": TargetUsers.PUBLIC}, "project.target_users", 3),
        ({"project.target_users": TargetUsers.EXTERNAL}, "project.target_users", 2),
        (
            {"use_case.interacts_directly_with_people": True},
            "use_case.interacts_directly_with_people",
            2,
        ),
        ({"use_case.generates_synthetic_content": True}, "use_case.generates_synthetic_content", 1),
        ({"ai_system.model_source": ModelSource.THIRD_PARTY_API}, "ai_system.model_source", 1),
        ({"ai_system.autonomy_level": AutonomyLevel.DECIDES}, "ai_system.autonomy_level", 3),
        ({"ai_system.autonomy_level": AutonomyLevel.RECOMMENDS}, "ai_system.autonomy_level", 1),
        ({"ai_system.human_oversight": False}, "ai_system.human_oversight", 1),
        ({"data.processes_personal_data": True}, "data.processes_personal_data", 2),
        ({"data.special_category_data": [SpecialCategory.HEALTH]}, "data.special_category_data", 3),
        ({"data.biometric_identification": True}, "data.biometric_identification", 3),
        ({"data.data_subjects": [DataSubject.MINORS]}, "data.data_subjects", 2),
        ({"data.trains_on_personal_data": True}, "data.trains_on_personal_data", 1),
        ({"data.cross_border_transfer": True}, "data.cross_border_transfer", 1),
        (
            {"use_case.affects_legal_or_significant_effects": True},
            "use_case.affects_legal_or_significant_effects",
            3,
        ),
        ({"use_case.domains": [Domain.HR_EMPLOYMENT]}, "use_case.domains", 2),
        ({"use_case.emotion_recognition": True}, "use_case.emotion_recognition", 2),
    ],
)
def test_each_driver_scores_once(values: dict[str, object], field: str, points: int) -> None:
    profile = inherent(make_record(values), EuAiActClassification.MINIMAL)
    assert [(d.field, d.points) for d in profile.drivers] == [(field, points)]
    assert profile.drivers[0].value == values[field]


@pytest.mark.parametrize(
    ("values", "field"),
    [
        ({"project.target_users": TargetUsers.INTERNAL}, "project.target_users"),
        ({"ai_system.autonomy_level": AutonomyLevel.ASSISTIVE}, "ai_system.autonomy_level"),
        ({"ai_system.human_oversight": True}, "ai_system.human_oversight"),
        ({"data.special_category_data": []}, "data.special_category_data"),
        ({"data.data_subjects": [DataSubject.EMPLOYEES]}, "data.data_subjects"),
        ({"use_case.domains": [Domain.OTHER]}, "use_case.domains"),
        (
            {"use_case.affects_legal_or_significant_effects": False},
            "use_case.affects_legal_or_significant_effects",
        ),
    ],
)
def test_safe_answers_add_nothing(values: dict[str, object], field: str) -> None:
    assert inherent(make_record(values), EuAiActClassification.MINIMAL).drivers == []


@pytest.mark.parametrize(
    ("classification", "floor"),
    [
        (EuAiActClassification.PROHIBITED, RiskTier.CRITICAL),
        (EuAiActClassification.HIGH_RISK, RiskTier.HIGH),
        (EuAiActClassification.LIMITED_TRANSPARENCY, RiskTier.MEDIUM),
    ],
)
def test_inherent_floor_follows_the_classification(
    classification: EuAiActClassification, floor: RiskTier
) -> None:
    profile = inherent(new_record("floor"), classification)
    assert profile.tier is floor and profile.floor is floor and profile.floor_reason


# --- Residual: confirmed controls only ---------------------------------------------------


def test_external_chatbot_is_high_inherent_and_low_residual_once_controls_are_confirmed() -> None:
    record = make_record({**EXTERNAL_CHATBOT, **CONTROLS_ALL_ON})
    assessment = classify(record)
    assert assessment.inherent_risk.tier is RiskTier.HIGH
    assert assessment.inherent_risk.score == 9
    assert assessment.residual_risk.tier is RiskTier.LOW
    applied = [c.control for c in assessment.residual_risk.controls if c.status == "applied"]
    assert set(applied) == set(MITIGATION_CONTROLS)


def test_inferred_controls_do_not_lower_residual_until_confirmed() -> None:
    record = make_record(EXTERNAL_CHATBOT)
    for path, value in CONTROLS_ALL_ON.items():
        record.set_field(path, value, source="inferred", confidence=0.95, confirmed=False)
    assessment = classify(record)
    assert assessment.residual_risk.tier is assessment.inherent_risk.tier
    assert assessment.residual_risk.score == assessment.inherent_risk.score
    assert {c.status for c in assessment.residual_risk.controls} == {"unconfirmed"}


def test_user_entered_controls_count_without_the_confirmed_flag() -> None:
    record = make_record(EXTERNAL_CHATBOT)
    record.set_field(
        CONTROLS_IN_PLACE, [ControlKind.GUARDRAILS], source="user", confidence=1.0, confirmed=False
    )
    profile = residual(
        record, EuAiActClassification.MINIMAL, inherent(record, EuAiActClassification.MINIMAL)
    )
    guardrails = next(c for c in profile.controls if c.control == ControlKind.GUARDRAILS)
    assert guardrails.status == "applied" and guardrails.points == 2
    assert profile.score == 7


def test_a_control_never_removes_more_than_its_category_holds() -> None:
    record = make_record(
        {"data.processes_personal_data": True, CONTROLS_IN_PLACE: [ControlKind.PII_MINIMISATION]}
    )
    profile = residual(
        record, EuAiActClassification.MINIMAL, inherent(record, EuAiActClassification.MINIMAL)
    )
    pii = next(c for c in profile.controls if c.control == ControlKind.PII_MINIMISATION)
    assert pii.points == 2 and profile.score == 0
    record = make_record(
        {
            "use_case.interacts_directly_with_people": True,
            CONTROLS_IN_PLACE: [ControlKind.GUARDRAILS],
        }
    )
    profile = residual(
        record, EuAiActClassification.MINIMAL, inherent(record, EuAiActClassification.MINIMAL)
    )
    assert profile.score == 0
    guardrails = next(c for c in profile.controls if c.control == ControlKind.GUARDRAILS)
    assert guardrails.points == 2


GUARDRAILS = next(m for m in MITIGATIONS if m.control == ControlKind.GUARDRAILS)
OVERSIGHT = next(m for m in MITIGATIONS if m.field == HUMAN_OVERSIGHT)


@pytest.mark.parametrize(
    ("value", "confirmed", "source", "status"),
    [
        (None, False, "inferred", "unknown"),
        ("unknown", True, "user", "unknown"),
        ([], True, "user", "absent"),
        ([ControlKind.NONE], True, "user", "absent"),
        ([ControlKind.ACCESS_CONTROLS], True, "user", "absent"),
        ([ControlKind.GUARDRAILS], True, "inferred", "applied"),
        ([ControlKind.GUARDRAILS], False, "user", "applied"),
        ([ControlKind.GUARDRAILS], False, "inferred", "unconfirmed"),
    ],
)
def test_control_status(value: object, confirmed: bool, source: str, status: str) -> None:
    record = new_record("status")
    if value is not None:
        record.set_field(
            CONTROLS_IN_PLACE, value, source=source, confidence=0.9, confirmed=confirmed
        )
    assert control_status(record, GUARDRAILS) == status


@pytest.mark.parametrize(
    ("value", "status"),
    [(None, "unknown"), ("unknown", "unknown"), (False, "absent"), (True, "applied")],
)
def test_human_oversight_status(value: object, status: str) -> None:
    record = new_record("oversight")
    if value is not None:
        record.set_field(HUMAN_OVERSIGHT, value, source="user", confidence=1.0, confirmed=True)
    assert control_status(record, OVERSIGHT) == status


def test_residual_floor_keeps_annex_iii_at_medium_and_prohibited_at_critical() -> None:
    hr = make_record(
        {
            "ai_system.uses_ai": True,
            "use_case.domains": [Domain.HR_EMPLOYMENT],
            "data.processes_personal_data": True,
            "use_case.affects_legal_or_significant_effects": True,
            **CONTROLS_ALL_ON,
        }
    )
    assessment = classify(hr)
    assert assessment.eu_ai_act.classification is EuAiActClassification.HIGH_RISK
    assert assessment.residual_risk.tier is RiskTier.MEDIUM
    assert assessment.residual_risk.floor is RiskTier.MEDIUM
    prohibited = make_record(
        {"ai_system.uses_ai": True, "use_case.social_scoring": True, **CONTROLS_ALL_ON}
    )
    assessment = classify(prohibited)
    assert assessment.inherent_risk.tier is RiskTier.CRITICAL
    assert assessment.residual_risk.tier is RiskTier.CRITICAL


def test_residual_without_floor_can_reach_low() -> None:
    record = make_record(
        {
            "use_case.interacts_directly_with_people": True,
            CONTROLS_IN_PLACE: [ControlKind.USER_DISCLOSURE],
        }
    )
    profile = residual(
        record,
        EuAiActClassification.LIMITED_TRANSPARENCY,
        inherent(record, EuAiActClassification.LIMITED_TRANSPARENCY),
    )
    assert profile.tier is RiskTier.LOW and profile.floor is None


def test_mitigation_table_is_well_formed() -> None:
    assert all(m.points > 0 and m.category in risk_profile.CATEGORIES for m in MITIGATIONS)
    record = new_record("fields")
    for mitigation in MITIGATIONS:
        assert isinstance(mitigation, Mitigation)
        record.get_field(mitigation.field)  # every mitigation names a real field
        if mitigation.field == CONTROLS_IN_PLACE:
            assert ControlKind(mitigation.control) is not ControlKind.NONE
    assert ControlKind.NONE not in MITIGATION_CONTROLS
