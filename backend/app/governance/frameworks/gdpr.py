"""GDPR (Regulation (EU) 2016/679) module.

Applies whenever personal data is processed or special categories are present. A local
privacy law can ride on this module: set its name with :func:`set_local_privacy_law_name`
and it is listed as an additional applicable framework. Not legal advice.
"""

from __future__ import annotations

from app.governance.field_values import contains_any, equals, is_true, list_value
from app.governance.frameworks.base import NOT_APPLICABLE, FrameworkResult
from app.intake.schema import (
    DataSubject,
    EuAiActAssessment,
    EuAiActClassification,
    IntakeRecord,
    Obligation,
    RiskTier,
)

name = "GDPR"

LOCAL_PRIVACY_LAW_PLACEHOLDER = "[LOCAL PRIVACY LAW]"
# Replace through set_local_privacy_law_name(); the placeholder is never listed as applicable.
LOCAL_PRIVACY_LAW_NAME = LOCAL_PRIVACY_LAW_PLACEHOLDER

PROCESSES_PERSONAL_DATA = "data.processes_personal_data"
SPECIAL_CATEGORY_DATA = "data.special_category_data"
DATA_SUBJECTS = "data.data_subjects"
TRAINS_ON_PERSONAL_DATA = "data.trains_on_personal_data"
CROSS_BORDER_TRANSFER = "data.cross_border_transfer"
RETENTION_POLICY = "data.retention_policy"
RETENTION_UNDEFINED = "undefined"


def set_local_privacy_law_name(law_name: str | None) -> None:
    """Name the local privacy law to list alongside the GDPR; ``None`` restores the placeholder."""
    global LOCAL_PRIVACY_LAW_NAME
    LOCAL_PRIVACY_LAW_NAME = LOCAL_PRIVACY_LAW_PLACEHOLDER if law_name is None else law_name


def local_privacy_law_configured() -> bool:
    return bool(LOCAL_PRIVACY_LAW_NAME) and LOCAL_PRIVACY_LAW_NAME != LOCAL_PRIVACY_LAW_PLACEHOLDER


def _obligation(text: str, reference: str) -> Obligation:
    return Obligation(framework=name, text=text, reference=reference, role=None)


def evaluate(record: IntakeRecord, eu: EuAiActAssessment) -> FrameworkResult:
    special_categories = list_value(record, SPECIAL_CATEGORY_DATA)
    if not is_true(record, PROCESSES_PERSONAL_DATA) and not special_categories:
        return NOT_APPLICABLE

    minors_present = contains_any(record, DATA_SUBJECTS, {DataSubject.MINORS})
    obligations = [
        _obligation(
            "Identify a lawful basis for each processing purpose and publish a privacy notice",
            "GDPR Art. 6, Art. 13, Art. 14",
        ),
        _obligation("Add the processing to the records of processing activities", "GDPR Art. 30"),
    ]
    next_steps: list[str] = []

    dpia_reasons: list[str] = []
    if eu.classification is EuAiActClassification.HIGH_RISK:
        dpia_reasons.append("the system is high-risk under the EU AI Act")
    if special_categories:
        dpia_reasons.append("special-category data is processed")
    if minors_present:
        dpia_reasons.append("data about minors is processed")
    if is_true(record, TRAINS_ON_PERSONAL_DATA):
        dpia_reasons.append("personal data is used for training")
    if dpia_reasons:
        obligations.append(
            _obligation(
                "Carry out a data protection impact assessment because " + "; ".join(dpia_reasons),
                "GDPR Art. 35",
            )
        )
        next_steps.append("Book a DPIA with the data protection officer before go-live")

    if special_categories:
        obligations.append(
            _obligation(
                "Document the Art. 9(2) condition that permits processing special-category data",
                "GDPR Art. 9",
            )
        )
    if is_true(record, CROSS_BORDER_TRANSFER):
        obligations.append(
            _obligation(
                "Put a transfer mechanism in place for data leaving the region (adequacy "
                "decision or standard contractual clauses with a transfer impact assessment)",
                "GDPR Chapter V, Art. 44-46",
            )
        )
    if equals(record, RETENTION_POLICY, RETENTION_UNDEFINED):
        obligations.append(
            _obligation(
                "Define and enforce a retention period for the personal data",
                "GDPR Art. 5(1)(e)",
            )
        )

    additional_frameworks: list[str] = []
    if local_privacy_law_configured():
        additional_frameworks.append(LOCAL_PRIVACY_LAW_NAME)
        obligations.append(
            Obligation(
                framework=LOCAL_PRIVACY_LAW_NAME,
                text=f"Check the additional requirements of {LOCAL_PRIVACY_LAW_NAME}",
                reference=None,
                role=None,
            )
        )

    tier_floor = RiskTier.MEDIUM if special_categories or minors_present else None
    return FrameworkResult(
        applies=True,
        obligations=obligations,
        next_steps=next_steps,
        tier_floor=tier_floor,
        additional_frameworks=additional_frameworks,
    )
