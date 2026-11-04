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
    assert ground_fields(fields, TEXT) == fields


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
