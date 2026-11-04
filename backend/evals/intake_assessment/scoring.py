"""Score one extraction against a case.

The headline numbers are the ones a governance reviewer cares about:

* **risk false positive**: the extraction asserts a risk-increasing fact the text does not
  support (biometrics, special-category data, a prohibited practice, public users, ...).
  It makes the assessment too strict and erodes trust.
* **control false positive**: the extraction credits a control the text does not describe
  as in place (a plan, an intention). It makes the residual risk too low.
* **missed risk**: a risk-increasing fact the text states was recorded as absent, with enough
  confidence that the product would not ask. It silently makes the assessment too lenient.
* **unanswered risk**: a risk-increasing fact the text states was not recorded at all, or
  only at low confidence. The product asks the owner, so it costs a question, not accuracy.

Everything else (plain accuracy, confident accuracy, unsupported values, tier agreement,
latency, tokens) is reported alongside.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.governance.classify import reclassify
from app.inference.structured_extraction import ExtractedField
from app.intake.question_bank import ANNEX_III_DOMAINS
from app.intake.record_service import coerce_value
from app.intake.schema import (
    ControlKind,
    DataSubject,
    IntakeRecord,
    RiskTier,
    SpecialCategory,
    new_record,
)
from evals.intake_assessment.cases import AssessmentCase, record_from_values

CONFIDENT = 0.8
CONTROLS = "controls.in_place"

# Boolean facts where ``True`` raises the risk. Predicting ``True`` for one of these against
# the case's expectation (or, for the sensitive practices below, when the case does not list
# them) is a risk false positive.
RISK_BOOLEANS: frozenset[str] = frozenset(
    {
        "ai_system.uses_ai",
        "ai_system.gpai_model_used",
        "ai_system.fine_tuned_or_trained",
        "data.processes_personal_data",
        "data.biometric_identification",
        "data.trains_on_personal_data",
        "data.cross_border_transfer",
        "use_case.affects_legal_or_significant_effects",
        "use_case.emotion_recognition",
        "use_case.social_scoring",
        "use_case.remote_biometric_id_public_spaces",
        "use_case.manipulative_or_subliminal",
        "use_case.untargeted_facial_scraping",
        "use_case.interacts_directly_with_people",
        "use_case.generates_synthetic_content",
    }
)
# Sensitive practices: a case lists every one that applies, so an unlisted one is absent.
SENSITIVE_PRACTICES: frozenset[str] = frozenset(
    {
        "data.biometric_identification",
        "use_case.emotion_recognition",
        "use_case.social_scoring",
        "use_case.remote_biometric_id_public_spaces",
        "use_case.manipulative_or_subliminal",
        "use_case.untargeted_facial_scraping",
    }
)
# Ordered choices: a higher rank is riskier.
RISK_RANKS: dict[str, tuple[str, ...]] = {
    "project.target_users": ("internal", "external", "public"),
    "ai_system.autonomy_level": ("assistive", "recommends", "decides"),
}
# Lists where some members raise the risk.
RISK_LIST_MEMBERS: dict[str, frozenset[str]] = {
    "data.special_category_data": frozenset(c.value for c in SpecialCategory),
    "data.data_subjects": frozenset({DataSubject.MINORS.value}),
    "use_case.domains": frozenset(d.value for d in ANNEX_III_DOMAINS),
}

# ``unlisted``: a confident risk-raising value on a field the case neither expects nor lists as
# absent. It is not a gate (the gold is silent) but it is reported, so a reviewer can decide
# whether the case needs the field or the model over-reads the text.
Outcome = Literal["correct", "wrong", "missing", "unsupported", "implicit_ok", "unlisted"]
Direction = Literal["riskier", "safer", "same", "different"]


class FieldOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    expected: object = None
    predicted: object = None
    confidence: float | None = None
    outcome: Outcome
    direction: Direction = "same"
    risk_false_positive: bool = False
    control_false_positives: list[str] = Field(default_factory=list)
    risk_missed: bool = False
    risk_unanswered: bool = False


class TierOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected: RiskTier
    predicted: RiskTier
    relation: Literal["exact", "over", "under"]


class CaseScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    fields: list[FieldOutcome]
    inherent: TierOutcome
    residual: TierOutcome
    invalid_fields: list[str] = Field(default_factory=list)
    latency_ms: int = 0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

    @property
    def expected_count(self) -> int:
        return sum(1 for f in self.fields if f.expected is not None or f.outcome == "missing")

    @property
    def correct_count(self) -> int:
        return sum(1 for f in self.fields if f.outcome == "correct")

    @property
    def confident_correct_count(self) -> int:
        return sum(
            1
            for f in self.fields
            if f.outcome == "correct" and f.confidence is not None and f.confidence >= CONFIDENT
        )

    @property
    def risk_false_positives(self) -> int:
        return sum(1 for f in self.fields if f.risk_false_positive)

    @property
    def control_false_positives(self) -> int:
        return sum(len(f.control_false_positives) for f in self.fields)

    @property
    def risks_missed(self) -> int:
        return sum(1 for f in self.fields if f.risk_missed)

    @property
    def risks_unanswered(self) -> int:
        return sum(1 for f in self.fields if f.risk_unanswered)

    @property
    def unsupported(self) -> int:
        return sum(1 for f in self.fields if f.outcome == "unsupported")

    @property
    def passed(self) -> bool:
        return (
            self.risk_false_positives == 0
            and self.control_false_positives == 0
            and self.risks_missed == 0
            and not self.invalid_fields
            and self.inherent.relation == "exact"
            and self.residual.relation == "exact"
        )


def _normalise(value: object) -> object:
    if isinstance(value, list):
        return sorted(str(item) for item in value)
    if isinstance(value, bool) or value is None:
        return value
    return str(value)


def _rank(field: str, value: object) -> int | None:
    order = RISK_RANKS.get(field)
    if order is None or not isinstance(value, str) or value not in order:
        return None
    return order.index(value)


def direction(field: str, expected: object, predicted: object) -> Direction:
    """Is the prediction riskier or safer than the expectation?

    List fields compare on the members that change the risk: ``minors`` among data subjects,
    Annex III areas among domains, every special category. ``["other"]`` against ``[]`` or
    ``["customers"]`` against ``["public"]`` is the same assessment.
    """
    if field == CONTROLS:
        return "same" if _control_kinds(expected) == _control_kinds(predicted) else "different"
    members = RISK_LIST_MEMBERS.get(field)
    if members is not None:
        expected_risk = (
            {str(v) for v in expected} & members if isinstance(expected, list) else set()
        )
        predicted_risk = (
            {str(v) for v in predicted} & members if isinstance(predicted, list) else set()
        )
        if predicted_risk == expected_risk:
            return "same"
        if predicted_risk > expected_risk:
            return "riskier"
        if predicted_risk < expected_risk:
            return "safer"
        return "different"
    if _normalise(expected) == _normalise(predicted):
        return "same"
    if field in RISK_BOOLEANS and isinstance(predicted, bool) and isinstance(expected, bool):
        return "riskier" if predicted else "safer"
    expected_rank, predicted_rank = _rank(field, expected), _rank(field, predicted)
    if expected_rank is not None and predicted_rank is not None:
        return "riskier" if predicted_rank > expected_rank else "safer"
    return "different"


def _implicit_expectation(field: str) -> object:
    if field in SENSITIVE_PRACTICES:
        return False
    if field in RISK_LIST_MEMBERS or field == CONTROLS:
        return []
    return None


def _missing_is_a_missed_risk(field: str, expected: object) -> bool:
    """An expected risk-raising fact that was not recorded at all."""
    if field in RISK_BOOLEANS:
        return expected is True
    if field in RISK_RANKS:
        return (_rank(field, expected) or 0) > 0
    if field in RISK_LIST_MEMBERS and isinstance(expected, list):
        return bool({str(v) for v in expected} & RISK_LIST_MEMBERS[field])
    return False


def _raises_risk(field: str, value: object) -> bool:
    """True when ``value`` would add inherent-risk points or a legal effect on ``field``."""
    if field in RISK_BOOLEANS:
        return value is True
    if field in RISK_RANKS:
        return isinstance(value, str) and value in RISK_RANKS[field][1:]
    members = RISK_LIST_MEMBERS.get(field)
    if members is not None and isinstance(value, list):
        return any(str(item) in members for item in value)
    return False


def _control_kinds(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(v) for v in value if str(v) != ControlKind.NONE.value}


def score_fields(case: AssessmentCase, extracted: list[ExtractedField]) -> list[FieldOutcome]:
    predicted = {f.path: f for f in extracted}
    outcomes: list[FieldOutcome] = []
    seen: set[str] = set()

    for field, expected in case.expected.items():
        seen.add(field)
        item = predicted.get(field)
        if item is None:
            outcomes.append(
                FieldOutcome(
                    field=field,
                    expected=expected,
                    outcome="missing",
                    risk_unanswered=_missing_is_a_missed_risk(field, expected),
                )
            )
            continue
        value = coerce_value(field, item.value)
        where = direction(field, expected, value)
        outcome: Outcome = "correct" if where == "same" else "wrong"
        control_fps = (
            sorted(_control_kinds(value) - _control_kinds(expected)) if field == CONTROLS else []
        )
        outcomes.append(
            FieldOutcome(
                field=field,
                expected=expected,
                predicted=value,
                confidence=item.confidence,
                outcome=outcome,
                direction=where,
                risk_false_positive=where == "riskier" and item.confidence >= CONFIDENT,
                control_false_positives=control_fps,
                risk_missed=where == "safer" and item.confidence >= CONFIDENT,
                risk_unanswered=where == "safer" and item.confidence < CONFIDENT,
            )
        )

    for field in case.absent:
        seen.add(field)
        item = predicted.get(field)
        if item is None or item.confidence < CONFIDENT:
            outcomes.append(FieldOutcome(field=field, outcome="implicit_ok"))
            continue
        value = coerce_value(field, item.value)
        if field == CONTROLS and not _control_kinds(value):
            outcomes.append(
                FieldOutcome(
                    field=field, predicted=value, confidence=item.confidence, outcome="implicit_ok"
                )
            )
            continue
        where = direction(field, _implicit_expectation(field), value)
        outcomes.append(
            FieldOutcome(
                field=field,
                predicted=value,
                confidence=item.confidence,
                outcome="unsupported",
                direction=where,
                risk_false_positive=where == "riskier",
                control_false_positives=sorted(_control_kinds(value)) if field == CONTROLS else [],
            )
        )

    for field, item in predicted.items():
        if field in seen:
            continue
        implicit = _implicit_expectation(field)
        if implicit is None:
            # Neither listed nor a sensitive practice: not scored, but a confident risk-raising
            # value is reported so the gold or the hints can be reviewed.
            value = coerce_value(field, item.value)
            if item.confidence >= CONFIDENT and _raises_risk(field, value):
                outcomes.append(
                    FieldOutcome(
                        field=field,
                        predicted=value,
                        confidence=item.confidence,
                        outcome="unlisted",
                        direction="riskier",
                    )
                )
            continue
        value = coerce_value(field, item.value)
        where = direction(field, implicit, value)
        control_fps = sorted(_control_kinds(value)) if field == CONTROLS else []
        if where == "same" or (
            where == "riskier" and item.confidence < CONFIDENT and not control_fps
        ):
            outcomes.append(
                FieldOutcome(
                    field=field, predicted=value, confidence=item.confidence, outcome="implicit_ok"
                )
            )
            continue
        outcomes.append(
            FieldOutcome(
                field=field,
                expected=implicit,
                predicted=value,
                confidence=item.confidence,
                outcome="wrong",
                direction=where,
                risk_false_positive=where == "riskier",
                control_false_positives=control_fps,
            )
        )
    return outcomes


def predicted_record(
    extracted: list[ExtractedField], *, confirmed: bool
) -> tuple[IntakeRecord, list[str]]:
    """Apply the extraction to a fresh record the way the product does; return rejected paths."""
    record = new_record("predicted")
    rejected: list[str] = []
    for item in extracted:
        try:
            record.set_field(
                item.path,
                coerce_value(item.path, item.value),
                source="user" if confirmed else "inferred",
                confidence=1.0 if confirmed else item.confidence,
                confirmed=confirmed,
            )
        except (KeyError, ValueError):
            rejected.append(item.path)
    return reclassify(record), rejected


def _relation(expected: RiskTier, predicted: RiskTier) -> Literal["exact", "over", "under"]:
    order = [RiskTier.LOW, RiskTier.MEDIUM, RiskTier.HIGH, RiskTier.CRITICAL]
    if expected is predicted:
        return "exact"
    return "over" if order.index(predicted) > order.index(expected) else "under"


def score_case(
    case: AssessmentCase,
    extracted: list[ExtractedField],
    *,
    latency_ms: int = 0,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
) -> CaseScore:
    inferred, rejected = predicted_record(extracted, confirmed=False)
    confirmed, _ = predicted_record(extracted, confirmed=True)
    gold = record_from_values(case.expected, confirmed=True)
    assert gold.assessment.inherent_risk.tier is case.inherent
    return CaseScore(
        case_id=case.id,
        fields=score_fields(case, extracted),
        inherent=TierOutcome(
            expected=case.inherent,
            predicted=inferred.assessment.inherent_risk.tier,
            relation=_relation(case.inherent, inferred.assessment.inherent_risk.tier),
        ),
        residual=TierOutcome(
            expected=case.residual,
            predicted=confirmed.assessment.residual_risk.tier,
            relation=_relation(case.residual, confirmed.assessment.residual_risk.tier),
        ),
        invalid_fields=rejected,
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
