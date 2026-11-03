"""NIST AI Risk Management Framework 1.0 module (Govern, Map, Measure, Manage).

Applies to every project that uses AI; the depth of the obligations grows with the EU AI Act
tier and with the signals that call for bias testing and monitoring. Not legal advice.
"""

from __future__ import annotations

from app.governance.field_values import equals, is_true
from app.governance.frameworks.base import NOT_APPLICABLE, FrameworkResult
from app.intake.question_bank import annex_iii_domain_present
from app.intake.schema import (
    EuAiActAssessment,
    EuAiActClassification,
    IntakeRecord,
    LifecycleStage,
    Obligation,
)

name = "NIST AI RMF"

USES_AI = "ai_system.uses_ai"
AFFECTS_SIGNIFICANT_EFFECTS = "use_case.affects_legal_or_significant_effects"
LIFECYCLE_STAGE = "project.lifecycle_stage"

ELEVATED_CLASSIFICATIONS: frozenset[EuAiActClassification] = frozenset(
    {EuAiActClassification.HIGH_RISK, EuAiActClassification.PROHIBITED}
)


def _obligation(text: str, reference: str) -> Obligation:
    return Obligation(framework=name, text=text, reference=reference, role=None)


def _in_operation(record: IntakeRecord) -> bool:
    return equals(record, LIFECYCLE_STAGE, LifecycleStage.PILOT) or equals(
        record, LIFECYCLE_STAGE, LifecycleStage.PRODUCTION
    )


def evaluate(record: IntakeRecord, eu: EuAiActAssessment) -> FrameworkResult:
    if not is_true(record, USES_AI):
        return NOT_APPLICABLE

    obligations = [
        _obligation(
            "Govern: add the system to the AI inventory and name an accountable owner",
            "NIST AI RMF GOVERN 1.6, GOVERN 2.1",
        ),
        _obligation(
            "Map: document the intended use, the deployment context and who is affected",
            "NIST AI RMF MAP 1.1, MAP 3.1",
        ),
        _obligation(
            "Measure: write an evaluation plan with accuracy and robustness metrics",
            "NIST AI RMF MEASURE 2.5, MEASURE 2.6",
        ),
        _obligation(
            "Manage: define how incidents and harmful outputs are reported and handled",
            "NIST AI RMF MANAGE 4.1, MANAGE 4.3",
        ),
    ]
    if is_true(record, AFFECTS_SIGNIFICANT_EFFECTS) or annex_iii_domain_present(record):
        obligations.append(
            _obligation(
                "Measure: test for bias and disparate impact across affected groups before "
                "and after deployment",
                "NIST AI RMF MEASURE 2.11",
            )
        )
    if _in_operation(record):
        obligations.append(
            _obligation(
                "Manage: monitor performance and drift in operation and review on a schedule",
                "NIST AI RMF MANAGE 2.2, MEASURE 2.4",
            )
        )
    if eu.classification in ELEVATED_CLASSIFICATIONS:
        obligations.append(
            _obligation(
                "Manage: document residual risks and obtain the accountable owner's sign-off "
                "before deployment",
                "NIST AI RMF MANAGE 1.2, MANAGE 1.3",
            )
        )
    return FrameworkResult(applies=True, obligations=obligations)
