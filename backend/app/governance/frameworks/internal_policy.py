"""Internal AI policy module.

Always applies: every project is registered, owned and reviewed for oversight and vendor
exposure. Replace the texts with the organisation's own policy references.
"""

from __future__ import annotations

from app.governance.field_values import equals, is_asserted, is_false
from app.governance.frameworks.base import FrameworkResult
from app.intake.schema import (
    AutonomyLevel,
    EuAiActAssessment,
    IntakeRecord,
    ModelSource,
    Obligation,
    RiskTier,
)

name = "Internal AI policy"

OWNER = "project.owner"
AUTONOMY_LEVEL = "ai_system.autonomy_level"
HUMAN_OVERSIGHT = "ai_system.human_oversight"
MODEL_SOURCE = "ai_system.model_source"


def _obligation(text: str, reference: str) -> Obligation:
    return Obligation(framework=name, text=text, reference=reference, role=None)


def _owner_missing(record: IntakeRecord) -> bool:
    return not is_asserted(record, OWNER) or not str(record.value_of(OWNER)).strip()


def evaluate(record: IntakeRecord, eu: EuAiActAssessment) -> FrameworkResult:
    obligations = [
        _obligation("Register the system in the AI inventory", "Internal AI policy §1"),
    ]
    next_steps: list[str] = []
    if _owner_missing(record):
        obligations.append(
            _obligation(
                "Name an accountable owner before the project proceeds", "Internal AI policy §2"
            )
        )
        next_steps.append("Record a named owner for the project")

    decides = equals(record, AUTONOMY_LEVEL, AutonomyLevel.DECIDES)
    if decides or is_false(record, HUMAN_OVERSIGHT):
        obligations.append(
            _obligation(
                "Submit for human-oversight review: the system decides without review or its "
                "outputs cannot be overridden",
                "Internal AI policy §4",
            )
        )
    if equals(record, MODEL_SOURCE, ModelSource.THIRD_PARTY_API):
        obligations.append(
            _obligation(
                "Complete the vendor review for the third-party model provider",
                "Internal AI policy §5",
            )
        )
    return FrameworkResult(
        applies=True,
        obligations=obligations,
        next_steps=next_steps,
        tier_floor=RiskTier.MEDIUM if decides else None,
    )
