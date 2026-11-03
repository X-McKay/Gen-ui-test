"""ISO/IEC 42001:2023 (AI management system) module.

Applies once a system that uses AI reaches pilot or production, when the management-system
controls become meaningful. Not legal advice.
"""

from __future__ import annotations

from app.governance.field_values import equals, is_true
from app.governance.frameworks.base import NOT_APPLICABLE, FrameworkResult
from app.intake.schema import (
    EuAiActAssessment,
    IntakeRecord,
    LifecycleStage,
    ModelSource,
    Obligation,
)

name = "ISO/IEC 42001"

USES_AI = "ai_system.uses_ai"
LIFECYCLE_STAGE = "project.lifecycle_stage"
MODEL_SOURCE = "ai_system.model_source"
FINE_TUNED_OR_TRAINED = "ai_system.fine_tuned_or_trained"

OPERATIONAL_STAGES: frozenset[LifecycleStage] = frozenset(
    {LifecycleStage.PILOT, LifecycleStage.PRODUCTION}
)


def _obligation(text: str, reference: str) -> Obligation:
    return Obligation(framework=name, text=text, reference=reference, role=None)


def evaluate(record: IntakeRecord, eu: EuAiActAssessment) -> FrameworkResult:
    operational = any(equals(record, LIFECYCLE_STAGE, stage) for stage in OPERATIONAL_STAGES)
    if not is_true(record, USES_AI) or not operational:
        return NOT_APPLICABLE

    obligations = [
        _obligation(
            "Complete an AI system impact assessment covering individuals, groups and society",
            "ISO/IEC 42001 Clause 6.1.4, Annex A.5",
        ),
    ]
    if equals(record, MODEL_SOURCE, ModelSource.THIRD_PARTY_API):
        obligations.append(
            _obligation(
                "Apply supplier controls to the model provider: contract terms, change notice "
                "and service-level monitoring",
                "ISO/IEC 42001 Annex A.10.3",
            )
        )
    if is_true(record, FINE_TUNED_OR_TRAINED):
        obligations.append(
            _obligation(
                "Document data provenance, preparation and quality controls for training data",
                "ISO/IEC 42001 Annex A.7.3, A.7.4",
            )
        )
    return FrameworkResult(applies=True, obligations=obligations)
