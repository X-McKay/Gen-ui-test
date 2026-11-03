"""EU AI Act (Regulation (EU) 2024/1689) rule table.

The classification is a *data table*: one :class:`Rule` row per legal trigger. Each row names
the article it rests on, the classification effect it has, a pure predicate over the
:class:`~app.intake.schema.IntakeRecord` that returns the ``(field path, value)`` pairs which
fired it, and plain-language rationale text for the review page.

``evaluate`` applies the table and keeps the most severe effect that fired
(prohibited > high_risk > limited_transparency > minimal). Rows with ``effect=None`` are notes:
they add obligations, next steps and a rationale entry with effect ``"note"`` without moving
the tier.

Field values are read through :mod:`app.governance.field_values`, so ``None`` and the literal
``"unknown"`` are never treated as ``True`` or ``False``.

This table is a *starting point for legal review*. It encodes a reading of the Regulation
that is deliberately conservative and simplified; it is not legal advice, and every
classification it produces must be confirmed by qualified counsel before it is relied on.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Literal

from app.governance.field_values import (
    contains_any,
    equals,
    is_asserted,
    is_true,
    matching_items,
)
from app.governance.merge import identity, obligation_key, unique
from app.intake.schema import (
    Domain,
    EuAiActAssessment,
    EuAiActClassification,
    IntakeRecord,
    Obligation,
    RationaleEntry,
    SpecialCategory,
    TargetUsers,
)

FRAMEWORK_NAME = "EU AI Act"
NOTE_EFFECT = "note"
ESCALATION_STEP = "Stop. Escalate to the AI governance team before any further work"
EMOTION_RECOGNITION_REVIEW_STEP = (
    "Legal review: emotion recognition may also be high-risk under Annex III 1(c), "
    "even outside the workplace and education"
)

SEVERITY: dict[EuAiActClassification, int] = {
    EuAiActClassification.MINIMAL: 0,
    EuAiActClassification.LIMITED_TRANSPARENCY: 1,
    EuAiActClassification.HIGH_RISK: 2,
    EuAiActClassification.PROHIBITED: 3,
}

Trigger = tuple[str, object]
Predicate = Callable[[IntakeRecord], list[Trigger]]

# Field paths used by the predicates, named once so a schema rename is a one-line change.
SOCIAL_SCORING = "use_case.social_scoring"
MANIPULATIVE = "use_case.manipulative_or_subliminal"
FACIAL_SCRAPING = "use_case.untargeted_facial_scraping"
REMOTE_BIOMETRIC = "use_case.remote_biometric_id_public_spaces"
EMOTION_RECOGNITION = "use_case.emotion_recognition"
BIOMETRIC_IDENTIFICATION = "data.biometric_identification"
SPECIAL_CATEGORY_DATA = "data.special_category_data"
DOMAINS = "use_case.domains"
INTERACTS_WITH_PEOPLE = "use_case.interacts_directly_with_people"
SYNTHETIC_CONTENT = "use_case.generates_synthetic_content"
TARGET_USERS = "project.target_users"
GPAI_MODEL_USED = "ai_system.gpai_model_used"

# Special categories whose inference from biometrics is prohibited biometric categorisation
# (Art. 5(1)(g)). Health and criminal data are special categories under the GDPR but are not
# listed in Art. 5(1)(g).
BIOMETRIC_CATEGORISATION_CATEGORIES: frozenset[SpecialCategory] = frozenset(
    {
        SpecialCategory.ETHNICITY,
        SpecialCategory.POLITICAL,
        SpecialCategory.RELIGIOUS,
        SpecialCategory.SEXUAL_ORIENTATION,
    }
)

# Art. 5(1)(f): emotion recognition in the workplace and in education institutions.
EMOTION_RECOGNITION_PROHIBITED_DOMAINS: frozenset[Domain] = frozenset(
    {Domain.HR_EMPLOYMENT, Domain.EDUCATION}
)


Role = Literal["provider", "deployer", "both"]


def obligation(text: str, reference: str, role: Role) -> Obligation:
    return Obligation(framework=FRAMEWORK_NAME, text=text, reference=reference, role=role)


@dataclass(frozen=True)
class Rule:
    """One row of the rule table."""

    name: str
    article: str
    effect: EuAiActClassification | None
    predicate: Predicate
    rationale: str
    annex_iii_category: str | None = None
    obligations: tuple[Obligation, ...] = ()
    next_steps: tuple[str, ...] = ()

    @property
    def effect_label(self) -> str:
        return NOTE_EFFECT if self.effect is None else self.effect.value


@dataclass(frozen=True)
class EuAiActResult:
    """The assessment plus the obligations and next steps the table produced."""

    assessment: EuAiActAssessment
    obligations: list[Obligation] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    fired_rules: list[str] = field(default_factory=list)


# --- Predicate helpers --------------------------------------------------------------------


def _flag(path: str) -> Predicate:
    """Fires when the boolean field at ``path`` is ``True``."""

    def predicate(record: IntakeRecord) -> list[Trigger]:
        return [(path, True)] if is_true(record, path) else []

    return predicate


def _flag_with_domains(path: str, domains: Iterable[Domain]) -> Predicate:
    """Fires when ``path`` is ``True`` and ``use_case.domains`` contains one of ``domains``."""
    wanted = frozenset(domains)

    def predicate(record: IntakeRecord) -> list[Trigger]:
        if not is_true(record, path):
            return []
        matched = matching_items(record, DOMAINS, wanted)
        return [(path, True), *((DOMAINS, domain) for domain in matched)] if matched else []

    return predicate


def _flag_without_domains(path: str, domains: Iterable[Domain]) -> Predicate:
    """Fires when ``path`` is ``True`` and none of ``domains`` is selected."""
    excluded = frozenset(domains)

    def predicate(record: IntakeRecord) -> list[Trigger]:
        if not is_true(record, path) or contains_any(record, DOMAINS, excluded):
            return []
        return [(path, True)]

    return predicate


def _domain(domain: Domain) -> Predicate:
    """Fires when ``use_case.domains`` contains ``domain``."""

    def predicate(record: IntakeRecord) -> list[Trigger]:
        return [(DOMAINS, domain)] if contains_any(record, DOMAINS, {domain}) else []

    return predicate


def _biometric_categorisation(record: IntakeRecord) -> list[Trigger]:
    if not is_true(record, BIOMETRIC_IDENTIFICATION):
        return []
    matched = matching_items(record, SPECIAL_CATEGORY_DATA, BIOMETRIC_CATEGORISATION_CATEGORIES)
    if not matched:
        return []
    return [(BIOMETRIC_IDENTIFICATION, True), *((SPECIAL_CATEGORY_DATA, item) for item in matched)]


def _biometric_identification_high_risk(record: IntakeRecord) -> list[Trigger]:
    """Biometric identification that is not already prohibited as categorisation."""
    if not is_true(record, BIOMETRIC_IDENTIFICATION) or _biometric_categorisation(record):
        return []
    return [(BIOMETRIC_IDENTIFICATION, True)]


def _internal_users(record: IntakeRecord) -> bool:
    return equals(record, TARGET_USERS, TargetUsers.INTERNAL)


def _transparency(path: str) -> Predicate:
    """Art. 50 duty: fires when ``path`` is True for external, public or unstated users."""

    def predicate(record: IntakeRecord) -> list[Trigger]:
        if not is_true(record, path) or _internal_users(record):
            return []
        triggers: list[Trigger] = [(path, True)]
        if is_asserted(record, TARGET_USERS):
            triggers.append((TARGET_USERS, record.value_of(TARGET_USERS)))
        return triggers

    return predicate


def _transparency_internal(path: str) -> Predicate:
    """Art. 50 note: fires when ``path`` is True and the users are internal staff."""

    def predicate(record: IntakeRecord) -> list[Trigger]:
        if not is_true(record, path) or not _internal_users(record):
            return []
        return [(path, True), (TARGET_USERS, TargetUsers.INTERNAL)]

    return predicate


# --- Annex III domain mapping -------------------------------------------------------------


@dataclass(frozen=True)
class AnnexIiiEntry:
    domain: Domain
    article: str
    category: str
    rationale: str


ANNEX_III_ENTRIES: tuple[AnnexIiiEntry, ...] = (
    AnnexIiiEntry(
        Domain.HR_EMPLOYMENT,
        "EU AI Act Art. 6(2), Annex III 4",
        "Annex III 4 — Employment, workers management and access to self-employment",
        "AI used for recruitment, selection, promotion, termination, task allocation or "
        "monitoring of workers is listed in Annex III and is high-risk.",
    ),
    AnnexIiiEntry(
        Domain.CREDIT_INSURANCE,
        "EU AI Act Art. 6(2), Annex III 5(b)/(c)",
        "Annex III 5(b)/(c) — Creditworthiness assessment and life and health insurance "
        "risk assessment and pricing",
        "AI that evaluates creditworthiness or prices life and health insurance for natural "
        "persons is listed in Annex III and is high-risk.",
    ),
    AnnexIiiEntry(
        Domain.EDUCATION,
        "EU AI Act Art. 6(2), Annex III 3",
        "Annex III 3 — Education and vocational training",
        "AI that decides access or admission, evaluates learning outcomes or proctors "
        "examinations is listed in Annex III and is high-risk.",
    ),
    AnnexIiiEntry(
        Domain.LAW_ENFORCEMENT,
        "EU AI Act Art. 6(2), Annex III 6",
        "Annex III 6 — Law enforcement",
        "AI used by or on behalf of law enforcement authorities is listed in Annex III "
        "and is high-risk.",
    ),
    AnnexIiiEntry(
        Domain.MIGRATION_BORDER,
        "EU AI Act Art. 6(2), Annex III 7",
        "Annex III 7 — Migration, asylum and border control management",
        "AI used in migration, asylum or border control is listed in Annex III and is high-risk.",
    ),
    AnnexIiiEntry(
        Domain.JUSTICE_DEMOCRATIC,
        "EU AI Act Art. 6(2), Annex III 8",
        "Annex III 8 — Administration of justice and democratic processes",
        "AI that assists judicial authorities or influences elections and referenda is "
        "listed in Annex III and is high-risk.",
    ),
    AnnexIiiEntry(
        Domain.CRITICAL_INFRASTRUCTURE,
        "EU AI Act Art. 6(2), Annex III 2",
        "Annex III 2 — Critical infrastructure",
        "AI used as a safety component in the management of critical digital, road, water, "
        "gas, heating or electricity infrastructure is listed in Annex III and is high-risk.",
    ),
    AnnexIiiEntry(
        Domain.ESSENTIAL_SERVICES,
        "EU AI Act Art. 6(2), Annex III 5",
        "Annex III 5 — Access to and enjoyment of essential private and public services",
        "AI that decides eligibility for public assistance, essential services or emergency "
        "response is listed in Annex III and is high-risk.",
    ),
    AnnexIiiEntry(
        Domain.MEDICAL_OR_SAFETY_COMPONENT,
        "EU AI Act Art. 6(1), Annex I",
        "Art. 6(1)/Annex I — Safety component of a product covered by Union harmonisation "
        "legislation (for example medical devices or machinery)",
        "AI that is a safety component of a regulated product, or is itself such a product, "
        "is high-risk under Art. 6(1) when that product needs third-party conformity "
        "assessment.",
    ),
)

ANNEX_III_1_BIOMETRICS = (
    "Annex III 1 — Biometrics (remote biometric identification, biometric categorisation, "
    "emotion recognition)"
)
ANNEX_III_1A_REMOTE_BIOMETRICS = "Annex III 1(a) — Remote biometric identification systems"


def _annex_iii_rule(entry: AnnexIiiEntry) -> Rule:
    return Rule(
        name=f"annex_iii_{entry.domain.value}",
        article=entry.article,
        effect=EuAiActClassification.HIGH_RISK,
        predicate=_domain(entry.domain),
        rationale=entry.rationale,
        annex_iii_category=entry.category,
    )


# --- Obligations by classification --------------------------------------------------------

PROHIBITED_OBLIGATIONS: tuple[Obligation, ...] = (
    obligation(
        "Do not place on the market, put into service or use a system that performs a "
        "prohibited practice; the ban has applied since 2 February 2025",
        "EU AI Act Art. 5",
        "both",
    ),
    obligation(
        "Record the decision to stop or redesign and keep the evidence that the prohibited "
        "capability has been removed",
        "EU AI Act Art. 5, Art. 99(3)",
        "both",
    ),
)

HIGH_RISK_OBLIGATIONS: tuple[Obligation, ...] = (
    obligation(
        "Run a documented risk management system across the whole lifecycle",
        "EU AI Act Art. 9",
        "provider",
    ),
    obligation(
        "Apply data governance to training, validation and test data, including bias "
        "examination and representativeness",
        "EU AI Act Art. 10",
        "provider",
    ),
    obligation(
        "Provide deployers with instructions for use that explain capabilities, limits, "
        "accuracy and oversight measures",
        "EU AI Act Art. 13",
        "provider",
    ),
    obligation(
        "Design for, and operate with, effective human oversight that can intervene or stop "
        "the system",
        "EU AI Act Art. 14",
        "both",
    ),
    obligation(
        "Use the system in line with the instructions, assign trained human overseers, "
        "monitor operation, keep logs and inform affected workers and persons",
        "EU AI Act Art. 26",
        "deployer",
    ),
    obligation(
        "Carry out a fundamental rights impact assessment before first use when deploying "
        "as a public body or in essential private services (credit, insurance)",
        "EU AI Act Art. 27",
        "deployer",
    ),
    obligation(
        "Register the system in the EU database before placing it on the market or putting "
        "it into service (public-body deployers register too)",
        "EU AI Act Art. 49",
        "both",
    ),
)

HIGH_RISK_NEXT_STEPS: tuple[str, ...] = (
    "Plan the conformity assessment and technical documentation before go-live "
    "(EU AI Act Art. 11, Art. 43)",
    "Assign a named human overseer and define how outputs can be overridden "
    "(EU AI Act Art. 14, Art. 26)",
)

LIMITED_TRANSPARENCY_NEXT_STEPS: tuple[str, ...] = (
    "Add the Art. 50 transparency notices to the user experience before launch",
)

GPAI_OBLIGATIONS: tuple[Obligation, ...] = (
    obligation(
        "Confirm the general-purpose model provider publishes technical documentation, a "
        "copyright policy and a training-content summary, and obtain its downstream "
        "information package",
        "EU AI Act Art. 53(1)",
        "provider",
    ),
    obligation(
        "As the downstream integrator, keep the model provider's documentation, respect its "
        "acceptable-use terms and check whether the model is designated as carrying "
        "systemic risk",
        "EU AI Act Art. 25, Art. 51, Art. 55",
        "deployer",
    ),
)


# --- The table ----------------------------------------------------------------------------

RULES: tuple[Rule, ...] = (
    # EU AI Act Art. 5(1)(c): social scoring.
    Rule(
        name="social_scoring_prohibited",
        article="EU AI Act Art. 5(1)(c)",
        effect=EuAiActClassification.PROHIBITED,
        predicate=_flag(SOCIAL_SCORING),
        rationale="Scoring people on social behaviour or personal traits to decide how they "
        "are treated is a prohibited AI practice.",
        next_steps=(ESCALATION_STEP,),
    ),
    # EU AI Act Art. 5(1)(a): subliminal, manipulative or deceptive techniques.
    Rule(
        name="manipulative_or_subliminal_prohibited",
        article="EU AI Act Art. 5(1)(a)",
        effect=EuAiActClassification.PROHIBITED,
        predicate=_flag(MANIPULATIVE),
        rationale="Subliminal, manipulative or deceptive techniques that distort behaviour and "
        "cause significant harm are a prohibited AI practice.",
        next_steps=(ESCALATION_STEP,),
    ),
    # EU AI Act Art. 5(1)(e): untargeted scraping of facial images.
    Rule(
        name="untargeted_facial_scraping_prohibited",
        article="EU AI Act Art. 5(1)(e)",
        effect=EuAiActClassification.PROHIBITED,
        predicate=_flag(FACIAL_SCRAPING),
        rationale="Building or expanding facial recognition databases by untargeted scraping of "
        "facial images from the internet or CCTV is a prohibited AI practice.",
        next_steps=(ESCALATION_STEP,),
    ),
    # EU AI Act Art. 5(1)(h): real-time remote biometric identification for law enforcement.
    Rule(
        name="remote_biometric_identification_law_enforcement_prohibited",
        article="EU AI Act Art. 5(1)(h)",
        effect=EuAiActClassification.PROHIBITED,
        predicate=_flag_with_domains(REMOTE_BIOMETRIC, {Domain.LAW_ENFORCEMENT}),
        rationale="Real-time remote biometric identification in publicly accessible spaces for "
        "law enforcement is prohibited outside narrow, judicially authorised exceptions.",
        next_steps=(ESCALATION_STEP,),
    ),
    # EU AI Act Art. 5(1)(f): emotion recognition at work and in education.
    Rule(
        name="emotion_recognition_workplace_education_prohibited",
        article="EU AI Act Art. 5(1)(f)",
        effect=EuAiActClassification.PROHIBITED,
        predicate=_flag_with_domains(EMOTION_RECOGNITION, EMOTION_RECOGNITION_PROHIBITED_DOMAINS),
        rationale="Inferring emotions of people in the workplace or in education institutions is "
        "a prohibited AI practice (except for medical or safety reasons).",
        next_steps=(ESCALATION_STEP,),
    ),
    # EU AI Act Art. 5(1)(g): biometric categorisation by protected characteristics.
    Rule(
        name="biometric_categorisation_prohibited",
        article="EU AI Act Art. 5(1)(g)",
        effect=EuAiActClassification.PROHIBITED,
        predicate=_biometric_categorisation,
        rationale="Using biometric data to infer race, political opinions, religious beliefs or "
        "sexual orientation is prohibited biometric categorisation.",
        next_steps=(ESCALATION_STEP,),
    ),
    # EU AI Act Art. 6(2), Annex III 1(a): remote biometric identification outside policing.
    Rule(
        name="remote_biometric_identification_high_risk",
        article="EU AI Act Art. 6(2), Annex III 1(a)",
        effect=EuAiActClassification.HIGH_RISK,
        predicate=_flag_without_domains(REMOTE_BIOMETRIC, {Domain.LAW_ENFORCEMENT}),
        rationale="Remote biometric identification of people in publicly accessible spaces is "
        "listed in Annex III and is high-risk.",
        annex_iii_category=ANNEX_III_1A_REMOTE_BIOMETRICS,
    ),
    # EU AI Act Art. 6(2), Annex III 1: biometric identification systems.
    Rule(
        name="biometric_identification_high_risk",
        article="EU AI Act Art. 6(2), Annex III 1",
        effect=EuAiActClassification.HIGH_RISK,
        predicate=_biometric_identification_high_risk,
        rationale="Identifying people from biometric data is listed in Annex III and is high-risk.",
        annex_iii_category=ANNEX_III_1_BIOMETRICS,
    ),
    # EU AI Act Art. 6(2), Annex III 2-8 and Art. 6(1)/Annex I, one row per domain.
    *(_annex_iii_rule(entry) for entry in ANNEX_III_ENTRIES),
    # EU AI Act Art. 50(3): emotion recognition outside work and education.
    Rule(
        name="emotion_recognition_transparency",
        article="EU AI Act Art. 50(3)",
        effect=EuAiActClassification.LIMITED_TRANSPARENCY,
        predicate=_flag_without_domains(
            EMOTION_RECOGNITION, EMOTION_RECOGNITION_PROHIBITED_DOMAINS
        ),
        rationale="People exposed to an emotion recognition system must be told that it is in "
        "operation; Annex III 1(c) may also make it high-risk.",
        obligations=(
            obligation(
                "Inform people exposed to the system that emotion recognition is in operation "
                "and process their personal data lawfully",
                "EU AI Act Art. 50(3)",
                "deployer",
            ),
        ),
        next_steps=(EMOTION_RECOGNITION_REVIEW_STEP,),
    ),
    # EU AI Act Art. 50(1): people interacting with an AI system must be told so. We read the
    # "obvious from the point of view of a reasonably well-informed person" carve-out as
    # satisfied for internal staff who have been told, so an internal-only tool keeps its tier
    # and gets a notice obligation instead (see the next row).
    Rule(
        name="interaction_transparency",
        article="EU AI Act Art. 50(1)",
        effect=EuAiActClassification.LIMITED_TRANSPARENCY,
        predicate=_transparency(INTERACTS_WITH_PEOPLE),
        rationale="People who interact directly with an AI system must be informed that they are "
        "doing so, unless it is obvious from the context.",
        obligations=(
            obligation(
                "Tell users at first contact that they are interacting with an AI system",
                "EU AI Act Art. 50(1)",
                "provider",
            ),
        ),
    ),
    Rule(
        name="interaction_transparency_internal_users",
        article="EU AI Act Art. 50(1)",
        effect=None,
        predicate=_transparency_internal(INTERACTS_WITH_PEOPLE),
        rationale="Internal staff are treated as aware from the context once told; no tier change, "
        "but the notice must still be given.",
        obligations=(
            obligation(
                "Tell staff they are interacting with an AI system",
                "EU AI Act Art. 50(1)",
                "deployer",
            ),
        ),
    ),
    # EU AI Act Art. 50(2): synthetic content must be marked as artificially generated. Same
    # internal-users reading as Art. 50(1): content that stays inside the team is not "output
    # placed before the public", so the tier holds and a marking obligation is noted instead.
    Rule(
        name="synthetic_content_transparency",
        article="EU AI Act Art. 50(2)",
        effect=EuAiActClassification.LIMITED_TRANSPARENCY,
        predicate=_transparency(SYNTHETIC_CONTENT),
        rationale="Generated text, image, audio or video must be marked as artificially generated "
        "in a machine-readable way.",
        obligations=(
            obligation(
                "Mark generated output as artificially generated or manipulated, in a "
                "machine-readable format where feasible",
                "EU AI Act Art. 50(2)",
                "provider",
            ),
        ),
    ),
    Rule(
        name="synthetic_content_transparency_internal_users",
        article="EU AI Act Art. 50(2)",
        effect=None,
        predicate=_transparency_internal(SYNTHETIC_CONTENT),
        rationale="Generated content used only inside the team does not change the tier, but "
        "anything that leaves the team must be marked.",
        obligations=(
            obligation(
                "Mark AI-generated content that leaves the team",
                "EU AI Act Art. 50(2)",
                "deployer",
            ),
        ),
    ),
    # EU AI Act Art. 53 and Chapter V: general-purpose AI models. Using one does not change
    # the system's tier; it adds provider duties upstream and integrator duties downstream.
    Rule(
        name="gpai_model_used_note",
        article="EU AI Act Art. 53, Chapter V",
        effect=None,
        predicate=_flag(GPAI_MODEL_USED),
        rationale="A general-purpose AI model is part of the system. Its provider owes "
        "documentation and copyright duties; the integrator must build on them.",
        obligations=GPAI_OBLIGATIONS,
    ),
)

RULES_BY_NAME: dict[str, Rule] = {rule.name: rule for rule in RULES}


# --- Evaluation ---------------------------------------------------------------------------


def evaluate_detailed(record: IntakeRecord) -> EuAiActResult:
    """Apply every row of :data:`RULES` and collect the full result."""
    classification = EuAiActClassification.MINIMAL
    annex_iii_categories: list[str] = []
    rationale: list[RationaleEntry] = []
    obligations: list[Obligation] = []
    next_steps: list[str] = []
    fired_rules: list[str] = []

    for rule in RULES:
        triggers = rule.predicate(record)
        if not triggers:
            continue
        fired_rules.append(rule.name)
        if rule.effect is not None and SEVERITY[rule.effect] > SEVERITY[classification]:
            classification = rule.effect
        if rule.annex_iii_category is not None:
            annex_iii_categories.append(rule.annex_iii_category)
        rationale.extend(
            RationaleEntry(
                field=path,
                value=value,
                article=rule.article,
                text=rule.rationale,
                effect=rule.effect_label,
            )
            for path, value in triggers
        )
        obligations.extend(rule.obligations)
        next_steps.extend(rule.next_steps)

    if classification is EuAiActClassification.PROHIBITED:
        obligations.extend(PROHIBITED_OBLIGATIONS)
    elif classification is EuAiActClassification.HIGH_RISK:
        obligations.extend(HIGH_RISK_OBLIGATIONS)
        next_steps.extend(HIGH_RISK_NEXT_STEPS)
    elif classification is EuAiActClassification.LIMITED_TRANSPARENCY:
        next_steps.extend(LIMITED_TRANSPARENCY_NEXT_STEPS)

    assessment = EuAiActAssessment(
        classification=classification,
        annex_iii_categories=unique(annex_iii_categories, key=identity),
        rationale=rationale,
    )
    return EuAiActResult(
        assessment=assessment,
        obligations=unique(obligations, key=obligation_key),
        next_steps=unique(next_steps, key=identity),
        fired_rules=fired_rules,
    )


def evaluate(record: IntakeRecord) -> EuAiActAssessment:
    """Classify ``record`` under the EU AI Act."""
    return evaluate_detailed(record).assessment
