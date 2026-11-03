"""Aggregates the EU AI Act table and the framework modules into ``record.assessment``.

Pure functions, no I/O. ``classify`` is recomputed on every change to the record (see
``app.intake.record_service``), so it must stay cheap and deterministic.
"""

from __future__ import annotations

from app.governance import eu_ai_act
from app.governance.frameworks import FRAMEWORK_MODULES
from app.governance.merge import identity, obligation_key, unique
from app.intake.gap_analysis import open_questions
from app.intake.schema import (
    Assessment,
    EuAiActClassification,
    IntakeRecord,
    Obligation,
    RiskTier,
)

TIER_BY_CLASSIFICATION: dict[EuAiActClassification, RiskTier] = {
    EuAiActClassification.PROHIBITED: RiskTier.CRITICAL,
    EuAiActClassification.HIGH_RISK: RiskTier.HIGH,
    EuAiActClassification.LIMITED_TRANSPARENCY: RiskTier.MEDIUM,
    EuAiActClassification.MINIMAL: RiskTier.LOW,
}

TIER_RANK: dict[RiskTier, int] = {
    RiskTier.LOW: 0,
    RiskTier.MEDIUM: 1,
    RiskTier.HIGH: 2,
    RiskTier.CRITICAL: 3,
}


def raise_tier(current: RiskTier, floor: RiskTier | None) -> RiskTier:
    """Return the higher of ``current`` and ``floor`` (``None`` leaves ``current`` alone)."""
    if floor is None or TIER_RANK[floor] <= TIER_RANK[current]:
        return current
    return floor


def _escalation_first(steps: list[str]) -> list[str]:
    if eu_ai_act.ESCALATION_STEP not in steps:
        return steps
    return [
        eu_ai_act.ESCALATION_STEP,
        *(step for step in steps if step != eu_ai_act.ESCALATION_STEP),
    ]


def classify(record: IntakeRecord) -> Assessment:
    """Run the EU AI Act table, then every framework module, and merge the results."""
    eu = eu_ai_act.evaluate_detailed(record)
    frameworks: list[str] = [eu_ai_act.FRAMEWORK_NAME]
    obligations: list[Obligation] = list(eu.obligations)
    next_steps: list[str] = list(eu.next_steps)
    tier = TIER_BY_CLASSIFICATION[eu.assessment.classification]

    for module in FRAMEWORK_MODULES:
        result = module.evaluate(record, eu.assessment)
        if not result.applies:
            continue
        frameworks.append(module.name)
        frameworks.extend(result.additional_frameworks)
        obligations.extend(result.obligations)
        next_steps.extend(result.next_steps)
        tier = raise_tier(tier, result.tier_floor)

    return Assessment(
        eu_ai_act=eu.assessment,
        overall_risk_tier=tier,
        applicable_frameworks=unique(frameworks, key=identity),
        obligations=unique(obligations, key=obligation_key),
        recommended_next_steps=_escalation_first(unique(next_steps, key=identity)),
        open_questions=open_questions(record),
    )


def reclassify(record: IntakeRecord) -> IntakeRecord:
    """Recompute ``assessment`` in place and return the record."""
    record.assessment = classify(record)
    return record
