"""Risk-raising extraction values must be grounded in the text or they are demoted/dropped."""

from __future__ import annotations

import pytest

from app.inference.structured_extraction import (
    UNGROUNDED_CONFIDENCE,
    ExtractedField,
    evidence_in_text,
    ground_fields,
    parse_tool_arguments,
)

TEXT = (
    "Facial recognition at the turnstiles of our office buildings: a camera matches each "
    "employee's face against the enrolled badge photo before the gate opens. Security staff "
    "can override at the desk."
)


@pytest.mark.parametrize(
    ("evidence", "expected"),
    [
        ("matches each employee's face", True),
        ("Facial recognition... before the gate opens", True),
        ("FACIAL  recognition at the turnstiles", True),
        ("No mention of training on personal data.", False),
        ("System controls access, does not score social behavior.", False),
        (None, False),
        ("", False),
        ("...", False),
    ],
)
def test_evidence_in_text(evidence: str | None, expected: bool) -> None:
    assert evidence_in_text(evidence, TEXT) is expected


def test_grounded_and_negative_values_pass_through() -> None:
    fields = [
        ExtractedField(
            path="data.biometric_identification",
            value=True,
            confidence=0.95,
            evidence="matches each employee's face",
        ),
        ExtractedField(
            path="use_case.social_scoring",
            value=False,
            confidence=0.95,
            evidence="System controls access, not scoring.",
        ),
        ExtractedField(
            path="use_case.domains", value=["other"], confidence=0.9, evidence="whatever"
        ),
        ExtractedField(path="controls.in_place", value=["none"], confidence=0.9, evidence=None),
        ExtractedField(path="project.name", value="Turnstiles", confidence=0.9, evidence=None),
    ]
    grounded = ground_fields(fields, TEXT)
    assert grounded[: len(fields)] == fields
    # The only addition is the definitional one: identification implies biometric data.
    assert [f.path for f in grounded[len(fields) :]] == ["data.special_category_data"]


def test_ungrounded_risk_values_are_capped_or_dropped() -> None:
    fields = [
        ExtractedField(
            path="use_case.affects_legal_or_significant_effects",
            value=True,
            confidence=0.9,
            evidence="Access decisions affect employees.",
        ),
        ExtractedField(
            path="data.special_category_data",
            value=["biometric"],
            confidence=0.9,
            evidence="Faces are biometric data.",
        ),
        ExtractedField(
            path="use_case.domains",
            value=["critical_infrastructure"],
            confidence=0.85,
            evidence="Office buildings are infrastructure.",
        ),
        ExtractedField(
            path="controls.in_place",
            value=["access_controls"],
            confidence=0.9,
            evidence="Internal employees only.",
        ),
    ]
    grounded = {f.path: f for f in ground_fields(fields, TEXT)}
    assert (
        grounded["use_case.affects_legal_or_significant_effects"].confidence
        == UNGROUNDED_CONFIDENCE
    )
    assert grounded["data.special_category_data"].confidence == UNGROUNDED_CONFIDENCE
    assert "use_case.domains" not in grounded
    assert "controls.in_place" not in grounded


def test_junk_placeholder_values_are_dropped() -> None:
    fields = parse_tool_arguments(
        {
            "data__retention_policy": {"value": "undefined", "confidence": 0.5},
            "project__name": {"value": "Turnstiles", "confidence": 0.9},
            "data__processes_personal_data": {"value": True, "confidence": 0.9},
        }
    )
    assert [f.path for f in fields] == ["project.name", "data.processes_personal_data"]


def test_controls_need_their_vocabulary_in_the_text() -> None:
    from app.inference.structured_extraction import supported_controls

    text = "Internal tool for recruiters. Access is through company SSO and answers are redacted."
    assert supported_controls(["access_controls", "pii_minimisation", "guardrails"], text) == [
        "access_controls",
        "pii_minimisation",
    ]
    assert supported_controls(["none"], text) == ["none"]
    fields = [
        ExtractedField(
            path="controls.in_place", value=["guardrails"], confidence=0.9, evidence="Internal tool"
        )
    ]
    assert ground_fields(fields, text) == []
    fields = [
        ExtractedField(
            path="controls.in_place",
            value=["access_controls", "guardrails"],
            confidence=0.9,
            evidence="Access is through company SSO",
        )
    ]
    assert ground_fields(fields, text)[0].value == ["access_controls"]


def test_domains_and_effects_need_their_vocabulary_in_the_evidence() -> None:
    from app.inference.structured_extraction import vocabulary_supported

    assert vocabulary_supported("use_case.domains", ["other"], "a shop")
    assert vocabulary_supported(
        "use_case.domains", ["critical_infrastructure"], "sheds load at a substation"
    )
    assert not vocabulary_supported(
        "use_case.domains", ["critical_infrastructure"], "blocks network addresses"
    )
    assert not vocabulary_supported(
        "use_case.domains", ["credit_insurance"], "motor-insurance claims model"
    )
    assert vocabulary_supported(
        "use_case.domains", ["credit_insurance"], "prices health-insurance premiums"
    )
    assert vocabulary_supported(
        "use_case.affects_legal_or_significant_effects", True, "claims are paid"
    )
    assert not vocabulary_supported(
        "use_case.affects_legal_or_significant_effects", True, "a weekly summary"
    )
    assert vocabulary_supported("use_case.affects_legal_or_significant_effects", False, None)
    text = "A fraud model blocks card transactions for our retail banking customers."
    fields = [
        ExtractedField(
            path="use_case.domains",
            value=["credit_insurance"],
            confidence=1.0,
            evidence="blocks card transactions for our retail banking customers",
        ),
        ExtractedField(
            path="use_case.affects_legal_or_significant_effects",
            value=True,
            confidence=0.9,
            evidence="blocks card transactions",
        ),
    ]
    grounded = {f.path: f for f in ground_fields(fields, text)}
    assert grounded["use_case.domains"].value == ["credit_insurance"]
    assert grounded["use_case.domains"].confidence == UNGROUNDED_CONFIDENCE
    assert grounded["use_case.affects_legal_or_significant_effects"].confidence == 0.9


def test_actions_and_exposure_need_their_vocabulary_in_the_evidence() -> None:
    from app.inference.structured_extraction import vocabulary_supported

    acts = "use_case.acts_on_the_world"
    exposure = "use_case.financial_exposure"
    assert vocabulary_supported(acts, ["none"], "ranks stocks each morning")
    assert vocabulary_supported(acts, ["financial_transactions"], "places and cancels orders")
    assert not vocabulary_supported(acts, ["financial_transactions"], "decided automatically")
    assert vocabulary_supported(acts, ["physical_or_system_actions"], "sheds load on feeders")
    assert not vocabulary_supported(acts, ["physical_or_system_actions"], "nobody approves")
    assert vocabulary_supported(acts, ["legal_commitments"], "signs on behalf of the firm")
    assert vocabulary_supported(exposure, "under_10k", "small refunds")
    assert vocabulary_supported(exposure, "over_1m", "position limits of up to 5 million euros")
    assert not vocabulary_supported(exposure, "over_1m", "a large book")
    text = (
        "A purchasing bot places purchase orders with suppliers as long as the order is under "
        "5,000 euros. Nobody approves an order first."
    )
    fields = [
        ExtractedField(
            path=acts,
            value=["financial_transactions"],
            confidence=0.95,
            evidence="places purchase orders with suppliers",
        ),
        ExtractedField(
            path=exposure, value="over_1m", confidence=0.9, evidence="Nobody approves an order"
        ),
        ExtractedField(path=exposure, value="under_10k", confidence=0.9, evidence="not in text"),
        ExtractedField(
            path="controls.in_place", value=["hard_limits"], confidence=0.9, evidence="under 5,000"
        ),
    ]
    grounded = ground_fields(fields, text)
    by_path: dict[str, list[ExtractedField]] = {}
    for field in grounded:
        by_path.setdefault(field.path, []).append(field)
    assert by_path[acts][0].confidence == 0.95
    [capped, kept] = by_path[exposure]
    assert capped.value == "over_1m" and capped.confidence == UNGROUNDED_CONFIDENCE
    assert kept.value == "under_10k" and kept.confidence == 0.9  # safe values pass ungrounded
    assert by_path["controls.in_place"][0].value == ["hard_limits"]
    assert not ground_fields(
        [ExtractedField(path=acts, value=["financial_transactions"], confidence=0.9)], text
    )


def test_biometric_identification_implies_biometric_special_category() -> None:
    from app.inference.structured_extraction import reconcile_fields

    text = "A camera matches each employee's face against the enrolled badge photo."
    fields = [
        ExtractedField(
            path="data.biometric_identification",
            value=True,
            confidence=0.9,
            evidence="matches each employee's face against the enrolled badge photo",
        ),
        ExtractedField(path="data.special_category_data", value=[], confidence=0.85),
    ]
    grounded = {f.path: f for f in ground_fields(fields, text)}
    assert grounded["data.special_category_data"].value == ["biometric"]
    assert reconcile_fields(fields[:1])[-1].path == "data.special_category_data"
    assert reconcile_fields(fields[:1])[-1].confidence == 0.9
    untouched = [ExtractedField(path="data.biometric_identification", value=False, confidence=0.9)]
    assert reconcile_fields(untouched) == untouched
