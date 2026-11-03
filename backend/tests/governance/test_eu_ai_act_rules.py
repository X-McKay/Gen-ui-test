"""Table-driven tests for the EU AI Act rule table: one case per rule row."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import pytest

from app.governance import eu_ai_act
from app.governance.eu_ai_act import (
    ANNEX_III_1_BIOMETRICS,
    ANNEX_III_1A_REMOTE_BIOMETRICS,
    ANNEX_III_ENTRIES,
    EMOTION_RECOGNITION_REVIEW_STEP,
    ESCALATION_STEP,
    HIGH_RISK_OBLIGATIONS,
    NOTE_EFFECT,
    PROHIBITED_OBLIGATIONS,
    RULES,
    RULES_BY_NAME,
    SEVERITY,
    Rule,
    evaluate,
    evaluate_detailed,
)
from app.intake.schema import (
    Domain,
    EuAiActClassification,
    IntakeRecord,
    SpecialCategory,
    TargetUsers,
)

RecordFactory = Callable[..., IntakeRecord]

PROHIBITED = EuAiActClassification.PROHIBITED
HIGH_RISK = EuAiActClassification.HIGH_RISK
LIMITED = EuAiActClassification.LIMITED_TRANSPARENCY
MINIMAL = EuAiActClassification.MINIMAL

SOCIAL_SCORING = "use_case.social_scoring"
MANIPULATIVE = "use_case.manipulative_or_subliminal"
FACIAL_SCRAPING = "use_case.untargeted_facial_scraping"
REMOTE_BIOMETRIC = "use_case.remote_biometric_id_public_spaces"
EMOTION_RECOGNITION = "use_case.emotion_recognition"
BIOMETRIC_IDENTIFICATION = "data.biometric_identification"
SPECIAL_CATEGORY_DATA = "data.special_category_data"
DOMAINS = "use_case.domains"
INTERACTS = "use_case.interacts_directly_with_people"
SYNTHETIC = "use_case.generates_synthetic_content"
TARGET_USERS = "project.target_users"
GPAI = "ai_system.gpai_model_used"


@dataclass(frozen=True)
class RuleCase:
    """The minimal record that fires one rule row, and what the row must produce."""

    values: dict[str, object]
    classification: EuAiActClassification
    triggered_fields: tuple[str, ...]
    annex_iii_category: str | None = None
    next_steps: tuple[str, ...] = ()
    obligation_texts: tuple[str, ...] = ()
    extra: dict[str, object] = field(default_factory=dict)


def _annex_case(domain: Domain, category: str) -> RuleCase:
    return RuleCase(
        values={DOMAINS: [domain]},
        classification=HIGH_RISK,
        triggered_fields=(DOMAINS,),
        annex_iii_category=category,
    )


ANNEX_CATEGORY_BY_DOMAIN = {entry.domain: entry.category for entry in ANNEX_III_ENTRIES}

EXPECTED_BY_RULE: dict[str, RuleCase] = {
    "social_scoring_prohibited": RuleCase(
        {SOCIAL_SCORING: True}, PROHIBITED, (SOCIAL_SCORING,), next_steps=(ESCALATION_STEP,)
    ),
    "manipulative_or_subliminal_prohibited": RuleCase(
        {MANIPULATIVE: True}, PROHIBITED, (MANIPULATIVE,), next_steps=(ESCALATION_STEP,)
    ),
    "untargeted_facial_scraping_prohibited": RuleCase(
        {FACIAL_SCRAPING: True}, PROHIBITED, (FACIAL_SCRAPING,), next_steps=(ESCALATION_STEP,)
    ),
    "remote_biometric_identification_law_enforcement_prohibited": RuleCase(
        {REMOTE_BIOMETRIC: True, DOMAINS: [Domain.LAW_ENFORCEMENT]},
        PROHIBITED,
        (REMOTE_BIOMETRIC, DOMAINS),
        next_steps=(ESCALATION_STEP,),
    ),
    "emotion_recognition_workplace_education_prohibited": RuleCase(
        {EMOTION_RECOGNITION: True, DOMAINS: [Domain.HR_EMPLOYMENT, Domain.EDUCATION]},
        PROHIBITED,
        (EMOTION_RECOGNITION, DOMAINS, DOMAINS),
        next_steps=(ESCALATION_STEP,),
    ),
    "biometric_categorisation_prohibited": RuleCase(
        {
            BIOMETRIC_IDENTIFICATION: True,
            SPECIAL_CATEGORY_DATA: [SpecialCategory.HEALTH, SpecialCategory.ETHNICITY],
        },
        PROHIBITED,
        (BIOMETRIC_IDENTIFICATION, SPECIAL_CATEGORY_DATA),
        next_steps=(ESCALATION_STEP,),
    ),
    "remote_biometric_identification_high_risk": RuleCase(
        {REMOTE_BIOMETRIC: True, DOMAINS: [Domain.OTHER]},
        HIGH_RISK,
        (REMOTE_BIOMETRIC,),
        annex_iii_category=ANNEX_III_1A_REMOTE_BIOMETRICS,
    ),
    "biometric_identification_high_risk": RuleCase(
        {BIOMETRIC_IDENTIFICATION: True, SPECIAL_CATEGORY_DATA: [SpecialCategory.BIOMETRIC]},
        HIGH_RISK,
        (BIOMETRIC_IDENTIFICATION,),
        annex_iii_category=ANNEX_III_1_BIOMETRICS,
    ),
    **{
        f"annex_iii_{domain.value}": _annex_case(domain, category)
        for domain, category in ANNEX_CATEGORY_BY_DOMAIN.items()
    },
    "emotion_recognition_transparency": RuleCase(
        {EMOTION_RECOGNITION: True, DOMAINS: [Domain.OTHER]},
        LIMITED,
        (EMOTION_RECOGNITION,),
        next_steps=(EMOTION_RECOGNITION_REVIEW_STEP,),
        obligation_texts=(
            "Inform people exposed to the system that emotion recognition is in operation "
            "and process their personal data lawfully",
        ),
    ),
    "interaction_transparency": RuleCase(
        {INTERACTS: True, TARGET_USERS: TargetUsers.PUBLIC},
        LIMITED,
        (INTERACTS, TARGET_USERS),
        obligation_texts=(
            "Tell users at first contact that they are interacting with an AI system",
        ),
    ),
    "interaction_transparency_internal_users": RuleCase(
        {INTERACTS: True, TARGET_USERS: TargetUsers.INTERNAL},
        MINIMAL,
        (INTERACTS, TARGET_USERS),
        obligation_texts=("Tell staff they are interacting with an AI system",),
    ),
    "synthetic_content_transparency": RuleCase(
        {SYNTHETIC: True},
        LIMITED,
        (SYNTHETIC,),
        obligation_texts=(
            "Mark generated output as artificially generated or manipulated, in a "
            "machine-readable format where feasible",
        ),
    ),
    "synthetic_content_transparency_internal_users": RuleCase(
        {SYNTHETIC: True, TARGET_USERS: TargetUsers.INTERNAL},
        MINIMAL,
        (SYNTHETIC, TARGET_USERS),
        obligation_texts=("Mark AI-generated content that leaves the team",),
    ),
    "gpai_model_used_note": RuleCase(
        {GPAI: True},
        MINIMAL,
        (GPAI,),
        obligation_texts=tuple(item.text for item in eu_ai_act.GPAI_OBLIGATIONS),
    ),
}

rule_rows = pytest.mark.parametrize("rule", RULES, ids=[rule.name for rule in RULES])


def test_every_rule_row_has_a_case_and_every_case_a_row() -> None:
    assert set(EXPECTED_BY_RULE) == set(RULES_BY_NAME)
    assert len(RULES) == len(RULES_BY_NAME), "rule names must be unique"


@rule_rows
def test_rule_has_citation_and_rationale(rule: Rule) -> None:
    assert rule.article.startswith("EU AI Act Art.")
    assert rule.rationale.endswith(".")
    assert rule.effect_label == (NOTE_EFFECT if rule.effect is None else rule.effect.value)


@rule_rows
def test_rule_fires_on_its_case(rule: Rule, make_record: RecordFactory) -> None:
    case = EXPECTED_BY_RULE[rule.name]
    record = make_record(case.values)

    triggers = rule.predicate(record)
    assert [path for path, _ in triggers] == list(case.triggered_fields)

    result = evaluate_detailed(record)
    assert rule.name in result.fired_rules
    assert result.assessment.classification is case.classification

    own_entries = [entry for entry in result.assessment.rationale if entry.article == rule.article]
    assert [entry.field for entry in own_entries] == list(case.triggered_fields)
    assert all(entry.text == rule.rationale for entry in own_entries)
    assert all(entry.effect == rule.effect_label for entry in own_entries)
    for (path, value), entry in zip(triggers, own_entries, strict=True):
        assert entry.field == path
        assert entry.value == value

    if case.annex_iii_category is None:
        assert rule.annex_iii_category is None
    else:
        assert rule.annex_iii_category == case.annex_iii_category
        assert case.annex_iii_category in result.assessment.annex_iii_categories
    for step in case.next_steps:
        assert step in result.next_steps
    texts = [item.text for item in result.obligations]
    for text in case.obligation_texts:
        assert text in texts


@rule_rows
def test_rule_is_silent_on_a_blank_record(rule: Rule, make_record: RecordFactory) -> None:
    assert rule.predicate(make_record()) == []


@rule_rows
def test_unknown_is_not_true(rule: Rule, make_record: RecordFactory) -> None:
    """'unknown' in any positive condition silences the rule; all-unknown is minimal.

    ``project.target_users`` is not a positive condition: an unknown audience keeps the
    Art. 50 duty (covered by ``test_transparency_depends_on_target_users``).
    """
    case = EXPECTED_BY_RULE[rule.name]
    positive_fields = [path for path in case.triggered_fields if path != TARGET_USERS]
    assert positive_fields, "every row must rest on at least one positive answer"
    for path in positive_fields:
        values = {**case.values, path: "unknown"}
        assert rule.predicate(make_record(values)) == [], f"{rule.name} fired with {path}=unknown"
    all_unknown = dict.fromkeys(case.values, "unknown")
    assert evaluate(make_record(all_unknown)).classification is MINIMAL
    assert evaluate(make_record(all_unknown)).rationale == []


@rule_rows
def test_false_and_empty_are_not_true(rule: Rule, make_record: RecordFactory) -> None:
    case = EXPECTED_BY_RULE[rule.name]
    negated = {
        path: ([] if isinstance(value, list) else False if isinstance(value, bool) else value)
        for path, value in case.values.items()
    }
    if negated != case.values:
        assert rule.predicate(make_record(negated)) == []


def test_blank_record_is_minimal(make_record: RecordFactory) -> None:
    assessment = evaluate(make_record())
    assert assessment.classification is MINIMAL
    assert assessment.annex_iii_categories == []
    assert assessment.rationale == []
    detailed = evaluate_detailed(make_record())
    assert detailed.obligations == []
    assert detailed.next_steps == []


def test_evaluate_matches_detailed_assessment(make_record: RecordFactory) -> None:
    record = make_record({DOMAINS: [Domain.HR_EMPLOYMENT], GPAI: True})
    assert evaluate(record) == evaluate_detailed(record).assessment


# --- Severity ordering --------------------------------------------------------------------


def test_severity_is_total_order() -> None:
    assert SEVERITY[PROHIBITED] > SEVERITY[HIGH_RISK] > SEVERITY[LIMITED] > SEVERITY[MINIMAL]


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (
            {
                SOCIAL_SCORING: True,
                DOMAINS: [Domain.HR_EMPLOYMENT],
                INTERACTS: True,
                TARGET_USERS: TargetUsers.PUBLIC,
            },
            PROHIBITED,
        ),
        ({DOMAINS: [Domain.HR_EMPLOYMENT], INTERACTS: True, SYNTHETIC: True}, HIGH_RISK),
        ({INTERACTS: True, SYNTHETIC: True, GPAI: True}, LIMITED),
        ({GPAI: True, DOMAINS: [Domain.OTHER]}, MINIMAL),
    ],
    ids=["prohibited-wins", "high-risk-over-limited", "limited-over-note", "note-only"],
)
def test_most_severe_effect_wins(
    values: dict[str, object], expected: EuAiActClassification, make_record: RecordFactory
) -> None:
    assert evaluate(make_record(values)).classification is expected


def test_lower_severity_row_after_higher_does_not_lower_tier(make_record: RecordFactory) -> None:
    """A prohibited row fires first; the later high-risk and transparency rows must not win."""
    record = make_record({SOCIAL_SCORING: True, DOMAINS: [Domain.EDUCATION], SYNTHETIC: True})
    result = evaluate_detailed(record)
    assert result.fired_rules == [
        "social_scoring_prohibited",
        "annex_iii_education",
        "synthetic_content_transparency",
    ]
    assert result.assessment.classification is PROHIBITED


def test_note_rows_leave_the_tier_and_mark_rationale_as_note(make_record: RecordFactory) -> None:
    assessment = evaluate(make_record({GPAI: True}))
    assert assessment.classification is MINIMAL
    assert [entry.effect for entry in assessment.rationale] == [NOTE_EFFECT]


# --- Interaction and synthetic content: internal-user exemption -----------------------------


@pytest.mark.parametrize("path", [INTERACTS, SYNTHETIC], ids=["interacts", "synthetic"])
@pytest.mark.parametrize(
    ("target_users", "expected"),
    [
        (None, LIMITED),
        ("unknown", LIMITED),
        (TargetUsers.EXTERNAL, LIMITED),
        (TargetUsers.PUBLIC, LIMITED),
        (TargetUsers.INTERNAL, MINIMAL),
    ],
    ids=["unstated", "unknown", "external", "public", "internal"],
)
def test_transparency_depends_on_target_users(
    path: str,
    target_users: object,
    expected: EuAiActClassification,
    make_record: RecordFactory,
) -> None:
    values: dict[str, object] = {path: True}
    if target_users is not None:
        values[TARGET_USERS] = target_users
    result = evaluate_detailed(make_record(values))
    assert result.assessment.classification is expected
    assert result.obligations, "the notice obligation is owed either way"
    rationale_fields = [entry.field for entry in result.assessment.rationale]
    if target_users in (None, "unknown"):
        assert rationale_fields == [path]
    else:
        assert rationale_fields == [path, TARGET_USERS]


def test_internal_users_get_notice_obligations_without_tier_change(
    make_record: RecordFactory,
) -> None:
    record = make_record({INTERACTS: True, SYNTHETIC: True, TARGET_USERS: TargetUsers.INTERNAL})
    result = evaluate_detailed(record)
    assert result.assessment.classification is MINIMAL
    assert [item.text for item in result.obligations] == [
        "Tell staff they are interacting with an AI system",
        "Mark AI-generated content that leaves the team",
    ]
    assert all(entry.effect == NOTE_EFFECT for entry in result.assessment.rationale)
    assert result.next_steps == []


# --- Combined rows --------------------------------------------------------------------------


def test_remote_biometric_without_law_enforcement_is_high_risk_not_prohibited(
    make_record: RecordFactory,
) -> None:
    result = evaluate_detailed(make_record({REMOTE_BIOMETRIC: True}))
    assert result.assessment.classification is HIGH_RISK
    assert "remote_biometric_identification_law_enforcement_prohibited" not in result.fired_rules
    assert result.assessment.annex_iii_categories == [ANNEX_III_1A_REMOTE_BIOMETRICS]


def test_remote_biometric_with_law_enforcement_skips_high_risk_row(
    make_record: RecordFactory,
) -> None:
    record = make_record({REMOTE_BIOMETRIC: True, DOMAINS: [Domain.LAW_ENFORCEMENT]})
    result = evaluate_detailed(record)
    assert "remote_biometric_identification_high_risk" not in result.fired_rules
    assert result.assessment.classification is PROHIBITED


def test_emotion_recognition_outside_work_is_limited_with_review_step(
    make_record: RecordFactory,
) -> None:
    result = evaluate_detailed(make_record({EMOTION_RECOGNITION: True}))
    assert result.assessment.classification is LIMITED
    assert EMOTION_RECOGNITION_REVIEW_STEP in result.next_steps
    assert "emotion_recognition_workplace_education_prohibited" not in result.fired_rules


def test_emotion_recognition_at_work_is_prohibited_without_transparency_row(
    make_record: RecordFactory,
) -> None:
    record = make_record({EMOTION_RECOGNITION: True, DOMAINS: [Domain.HR_EMPLOYMENT]})
    result = evaluate_detailed(record)
    assert result.assessment.classification is PROHIBITED
    assert "emotion_recognition_transparency" not in result.fired_rules
    assert EMOTION_RECOGNITION_REVIEW_STEP not in result.next_steps


def test_biometric_categorisation_excludes_the_high_risk_biometrics_row(
    make_record: RecordFactory,
) -> None:
    record = make_record(
        {BIOMETRIC_IDENTIFICATION: True, SPECIAL_CATEGORY_DATA: [SpecialCategory.RELIGIOUS]}
    )
    result = evaluate_detailed(record)
    assert result.assessment.classification is PROHIBITED
    assert "biometric_identification_high_risk" not in result.fired_rules
    assert ANNEX_III_1_BIOMETRICS not in result.assessment.annex_iii_categories


def test_biometric_identification_with_health_data_only_is_high_risk(
    make_record: RecordFactory,
) -> None:
    record = make_record(
        {BIOMETRIC_IDENTIFICATION: True, SPECIAL_CATEGORY_DATA: [SpecialCategory.HEALTH]}
    )
    result = evaluate_detailed(record)
    assert result.assessment.classification is HIGH_RISK
    assert "biometric_categorisation_prohibited" not in result.fired_rules


def test_biometric_categorisation_needs_biometric_identification(
    make_record: RecordFactory,
) -> None:
    record = make_record({SPECIAL_CATEGORY_DATA: [SpecialCategory.ETHNICITY]})
    assert evaluate(record).classification is MINIMAL


def test_flag_with_domains_needs_both_parts(make_record: RecordFactory) -> None:
    rule = RULES_BY_NAME["remote_biometric_identification_law_enforcement_prohibited"]
    assert rule.predicate(make_record({REMOTE_BIOMETRIC: True, DOMAINS: [Domain.OTHER]})) == []
    assert rule.predicate(make_record({DOMAINS: [Domain.LAW_ENFORCEMENT]})) == []


# --- Obligations and next steps by classification ------------------------------------------


def test_high_risk_adds_provider_and_deployer_obligations(make_record: RecordFactory) -> None:
    result = evaluate_detailed(make_record({DOMAINS: [Domain.CREDIT_INSURANCE]}))
    assert result.assessment.classification is HIGH_RISK
    roles = {item.role for item in result.obligations}
    assert {"provider", "deployer", "both"} <= roles
    references = [item.reference for item in result.obligations]
    for article in ("Art. 9", "Art. 10", "Art. 13", "Art. 14", "Art. 26", "Art. 27", "Art. 49"):
        assert any(reference is not None and article in reference for reference in references)
    assert all(item in result.obligations for item in HIGH_RISK_OBLIGATIONS)
    assert result.next_steps == list(eu_ai_act.HIGH_RISK_NEXT_STEPS)


def test_prohibited_adds_stop_obligations_and_escalation_first(make_record: RecordFactory) -> None:
    record = make_record({SOCIAL_SCORING: True, MANIPULATIVE: True, DOMAINS: [Domain.EDUCATION]})
    result = evaluate_detailed(record)
    assert result.next_steps[0] == ESCALATION_STEP
    assert result.next_steps.count(ESCALATION_STEP) == 1
    assert all(item in result.obligations for item in PROHIBITED_OBLIGATIONS)
    assert not any(item in result.obligations for item in HIGH_RISK_OBLIGATIONS)


def test_limited_transparency_adds_notice_next_step(make_record: RecordFactory) -> None:
    result = evaluate_detailed(make_record({INTERACTS: True}))
    assert result.next_steps == list(eu_ai_act.LIMITED_TRANSPARENCY_NEXT_STEPS)


def test_repeated_domain_counts_once(make_record: RecordFactory) -> None:
    record = make_record({DOMAINS: [Domain.HR_EMPLOYMENT, Domain.HR_EMPLOYMENT]})
    assessment = evaluate(record)
    assert assessment.annex_iii_categories == [ANNEX_CATEGORY_BY_DOMAIN[Domain.HR_EMPLOYMENT]]
    assert len(assessment.rationale) == 1


def test_unique_keeps_first_occurrence_in_order() -> None:
    from app.governance.merge import identity, unique

    assert unique(["b", "a", "b", "c", "a"], key=identity) == ["b", "a", "c"]


def test_every_annex_iii_domain_from_question_bank_has_a_row() -> None:
    from app.intake.question_bank import ANNEX_III_DOMAINS

    assert {entry.domain for entry in ANNEX_III_ENTRIES} == set(ANNEX_III_DOMAINS)
