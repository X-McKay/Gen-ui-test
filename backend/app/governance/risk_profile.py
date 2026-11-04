"""Inherent and residual risk, overall and per enterprise lens.

*Inherent* risk scores the use case as described: who is exposed, how autonomous the system
is, what data it touches and what its outputs can do to people. *Residual* risk is what is
left after the controls the owner has **confirmed**; a control the model merely inferred from
the description never lowers the score, so an optimistic write-up cannot talk the risk down.

Every driver and every mitigation is tagged with the enterprise **lenses** it counts towards
(data privacy, information security, operational, financial, reputational, regulatory), so
the same facts yield one profile per lens next to the overall one. The tables are plain data,
deterministic, and every driver and control effect is listed on the record. The legal
classification sets a floor that no control removes (a prohibited practice stays critical;
an Annex III system keeps its statutory obligations and stays at least medium).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.governance.field_values import equals, is_false, is_true, list_value
from app.intake.question_bank import ANNEX_III_DOMAINS
from app.intake.schema import (
    AutonomyLevel,
    ControlEffect,
    ControlKind,
    DataSubject,
    Domain,
    EuAiActClassification,
    IntakeRecord,
    ModelSource,
    RiskDriver,
    RiskLens,
    RiskProfile,
    RiskTier,
    TargetUsers,
)

EXPOSURE = "exposure"
AUTONOMY = "autonomy"
DATA = "data"
IMPACT = "impact"
CATEGORIES: tuple[str, ...] = (EXPOSURE, AUTONOMY, DATA, IMPACT)

PRIVACY = "data_privacy"
SECURITY = "information_security"
OPERATIONAL = "operational"
FINANCIAL = "financial"
REPUTATIONAL = "reputational"
REGULATORY = "regulatory"
LENSES: tuple[tuple[str, str], ...] = (
    (PRIVACY, "Data and privacy"),
    (SECURITY, "Information security"),
    (OPERATIONAL, "Operational"),
    (FINANCIAL, "Financial"),
    (REPUTATIONAL, "Reputational"),
    (REGULATORY, "Regulatory"),
)
LENS_NAMES: tuple[str, ...] = tuple(name for name, _ in LENSES)

# Score bands. The top of each band is inclusive.
TIER_BANDS: tuple[tuple[int, RiskTier], ...] = (
    (3, RiskTier.LOW),
    (7, RiskTier.MEDIUM),
    (13, RiskTier.HIGH),
)

TIER_RANK: dict[RiskTier, int] = {
    RiskTier.LOW: 0,
    RiskTier.MEDIUM: 1,
    RiskTier.HIGH: 2,
    RiskTier.CRITICAL: 3,
}

Floor = tuple[RiskTier, str] | None

INHERENT_FLOOR: dict[EuAiActClassification, Floor] = {
    EuAiActClassification.PROHIBITED: (RiskTier.CRITICAL, "A prohibited practice is critical"),
    EuAiActClassification.HIGH_RISK: (RiskTier.HIGH, "An Annex III system is at least high"),
    EuAiActClassification.LIMITED_TRANSPARENCY: (
        RiskTier.MEDIUM,
        "A system with transparency duties is at least medium",
    ),
    EuAiActClassification.MINIMAL: None,
}

RESIDUAL_FLOOR: dict[EuAiActClassification, Floor] = {
    EuAiActClassification.PROHIBITED: (
        RiskTier.CRITICAL,
        "No control makes a prohibited practice acceptable",
    ),
    EuAiActClassification.HIGH_RISK: (
        RiskTier.MEDIUM,
        "Annex III obligations remain whatever controls are in place",
    ),
    EuAiActClassification.LIMITED_TRANSPARENCY: None,
    EuAiActClassification.MINIMAL: None,
}

# The legal floors apply to the overall profile and to the regulatory lens only.
FLOORED_LENSES: frozenset[str] = frozenset({REGULATORY})


@dataclass(frozen=True)
class Driver:
    field: str
    category: str
    points: int
    text: str
    lenses: tuple[str, ...]
    applies: Callable[[IntakeRecord], bool]


def _is(path: str, value: object) -> Callable[[IntakeRecord], bool]:
    return lambda record: equals(record, path, value)


def _true(path: str) -> Callable[[IntakeRecord], bool]:
    return lambda record: is_true(record, path)


def _false(path: str) -> Callable[[IntakeRecord], bool]:
    return lambda record: is_false(record, path)


def _nonempty(path: str) -> Callable[[IntakeRecord], bool]:
    return lambda record: bool(list_value(record, path))


def _contains(path: str, member: object) -> Callable[[IntakeRecord], bool]:
    return lambda record: member in list_value(record, path)


def _annex_iii(record: IntakeRecord) -> bool:
    return any(domain in ANNEX_III_DOMAINS for domain in list_value(record, "use_case.domains"))


# The point table. Unknown and missing answers add nothing; they are open questions. Rows
# for one field are tried in order and only the first that applies counts.
DRIVERS: tuple[Driver, ...] = (
    Driver(
        "project.target_users",
        EXPOSURE,
        3,
        "Anyone can use it",
        (SECURITY, REPUTATIONAL, OPERATIONAL),
        _is("project.target_users", TargetUsers.PUBLIC),
    ),
    Driver(
        "project.target_users",
        EXPOSURE,
        2,
        "Customers or partners use it",
        (SECURITY, REPUTATIONAL),
        _is("project.target_users", TargetUsers.EXTERNAL),
    ),
    Driver(
        "use_case.interacts_directly_with_people",
        EXPOSURE,
        2,
        "It talks to people directly",
        (SECURITY, REPUTATIONAL),
        _true("use_case.interacts_directly_with_people"),
    ),
    Driver(
        "use_case.generates_synthetic_content",
        EXPOSURE,
        1,
        "It generates content",
        (REPUTATIONAL, REGULATORY),
        _true("use_case.generates_synthetic_content"),
    ),
    Driver(
        "ai_system.model_source",
        EXPOSURE,
        1,
        "Data leaves for a third-party model API",
        (SECURITY, PRIVACY, OPERATIONAL),
        _is("ai_system.model_source", ModelSource.THIRD_PARTY_API),
    ),
    Driver(
        "ai_system.autonomy_level",
        AUTONOMY,
        3,
        "It acts without review",
        (OPERATIONAL, FINANCIAL, REGULATORY),
        _is("ai_system.autonomy_level", AutonomyLevel.DECIDES),
    ),
    Driver(
        "ai_system.autonomy_level",
        AUTONOMY,
        1,
        "It recommends; a person decides",
        (OPERATIONAL, REGULATORY),
        _is("ai_system.autonomy_level", AutonomyLevel.RECOMMENDS),
    ),
    Driver(
        "ai_system.human_oversight",
        AUTONOMY,
        1,
        "Nobody reviews or can override outputs",
        (OPERATIONAL, REGULATORY),
        _false("ai_system.human_oversight"),
    ),
    Driver(
        "data.processes_personal_data",
        DATA,
        2,
        "It processes personal data",
        (PRIVACY, REGULATORY),
        _true("data.processes_personal_data"),
    ),
    Driver(
        "data.special_category_data",
        DATA,
        3,
        "It touches special-category data",
        (PRIVACY, REGULATORY, REPUTATIONAL),
        _nonempty("data.special_category_data"),
    ),
    Driver(
        "data.biometric_identification",
        DATA,
        3,
        "It identifies people biometrically",
        (PRIVACY, REGULATORY, REPUTATIONAL),
        _true("data.biometric_identification"),
    ),
    Driver(
        "data.data_subjects",
        DATA,
        2,
        "Minors are among the data subjects",
        (PRIVACY, REPUTATIONAL, REGULATORY),
        _contains("data.data_subjects", DataSubject.MINORS),
    ),
    Driver(
        "data.trains_on_personal_data",
        DATA,
        1,
        "Personal data is used for training",
        (PRIVACY,),
        _true("data.trains_on_personal_data"),
    ),
    Driver(
        "data.cross_border_transfer",
        DATA,
        1,
        "Data crosses borders",
        (PRIVACY, REGULATORY),
        _true("data.cross_border_transfer"),
    ),
    Driver(
        "use_case.affects_legal_or_significant_effects",
        IMPACT,
        3,
        "Outputs affect rights, access or significant decisions",
        (REGULATORY, REPUTATIONAL, FINANCIAL),
        _true("use_case.affects_legal_or_significant_effects"),
    ),
    Driver(
        "use_case.domains",
        IMPACT,
        2,
        "It operates in an Annex III area",
        (REGULATORY, REPUTATIONAL),
        _annex_iii,
    ),
    Driver(
        "use_case.domains",
        IMPACT,
        0,
        "Credit or insurance decisions carry financial exposure",
        (FINANCIAL,),
        _contains("use_case.domains", Domain.CREDIT_INSURANCE),
    ),
    Driver(
        "use_case.emotion_recognition",
        IMPACT,
        2,
        "It infers emotions or intentions",
        (REGULATORY, REPUTATIONAL),
        _true("use_case.emotion_recognition"),
    ),
)


@dataclass(frozen=True)
class Mitigation:
    field: str
    control: str
    category: str
    points: int
    text: str
    lenses: tuple[str, ...]


HUMAN_OVERSIGHT = "ai_system.human_oversight"
CONTROLS_IN_PLACE = "controls.in_place"


def _control(
    kind: ControlKind, category: str, points: int, text: str, lenses: tuple[str, ...]
) -> Mitigation:
    return Mitigation(CONTROLS_IN_PLACE, kind.value, category, points, text, lenses)


# Each mitigation removes points from one category only, and never more than that category
# holds. ``ai_system.human_oversight`` is an answer, not a controls option, but it is the
# strongest mitigation there is, so it is listed here and treated like a control.
MITIGATIONS: tuple[Mitigation, ...] = (
    Mitigation(
        HUMAN_OVERSIGHT,
        HUMAN_OVERSIGHT,
        AUTONOMY,
        2,
        "A person reviews or can override outputs",
        (OPERATIONAL, FINANCIAL, REGULATORY),
    ),
    Mitigation(
        HUMAN_OVERSIGHT,
        HUMAN_OVERSIGHT,
        IMPACT,
        1,
        "Human review limits the effect of errors",
        (REGULATORY, REPUTATIONAL, FINANCIAL),
    ),
    _control(
        ControlKind.GUARDRAILS,
        EXPOSURE,
        2,
        "Input and output guardrails are in place",
        (SECURITY, REPUTATIONAL),
    ),
    _control(
        ControlKind.PII_MINIMISATION,
        DATA,
        2,
        "Personal data is minimised before the model",
        (PRIVACY, REGULATORY),
    ),
    _control(
        ControlKind.ACCESS_CONTROLS,
        EXPOSURE,
        1,
        "Access is authenticated and authorised",
        (SECURITY, PRIVACY),
    ),
    _control(
        ControlKind.ABUSE_MONITORING,
        EXPOSURE,
        1,
        "Rate limits and misuse monitoring",
        (SECURITY, FINANCIAL, OPERATIONAL),
    ),
    _control(
        ControlKind.PRE_RELEASE_EVALUATION,
        IMPACT,
        1,
        "Evaluated or red-teamed before release",
        (OPERATIONAL, REPUTATIONAL),
    ),
    _control(
        ControlKind.PRE_RELEASE_EVALUATION,
        AUTONOMY,
        1,
        "Ongoing evaluation of outputs",
        (OPERATIONAL,),
    ),
    _control(
        ControlKind.VENDOR_DATA_PROTECTIONS,
        DATA,
        1,
        "Provider may not train on the data",
        (PRIVACY, SECURITY),
    ),
    _control(
        ControlKind.INCIDENT_RESPONSE,
        AUTONOMY,
        1,
        "Rollback, kill switch and incident process",
        (OPERATIONAL, FINANCIAL),
    ),
    _control(
        ControlKind.USER_DISCLOSURE,
        EXPOSURE,
        1,
        "Users are told they interact with AI",
        (REPUTATIONAL, REGULATORY),
    ),
)

MITIGATION_CONTROLS: tuple[str, ...] = tuple(dict.fromkeys(m.control for m in MITIGATIONS))


def tier_for_score(score: int) -> RiskTier:
    for upper, tier in TIER_BANDS:
        if score <= upper:
            return tier
    return RiskTier.CRITICAL


def apply_floor(tier: RiskTier, floor: Floor) -> tuple[RiskTier, RiskTier | None, str | None]:
    if floor is None or TIER_RANK[floor[0]] <= TIER_RANK[tier]:
        return tier, None, None
    return floor[0], floor[0], floor[1]


def inherent_drivers(record: IntakeRecord) -> list[RiskDriver]:
    """The drivers that apply, one row per field at most."""
    drivers: list[RiskDriver] = []
    seen: set[tuple[str, str]] = set()
    for driver in DRIVERS:
        key = (driver.field, driver.category)
        if key in seen or not driver.applies(record):
            continue
        seen.add(key)
        drivers.append(
            RiskDriver(
                field=driver.field,
                value=record.value_of(driver.field),
                category=driver.category,
                points=driver.points,
                text=driver.text,
                lenses=list(driver.lenses),
            )
        )
    return drivers


def category_points(drivers: list[RiskDriver]) -> dict[str, int]:
    points = dict.fromkeys(CATEGORIES, 0)
    for driver in drivers:
        points[driver.category] += driver.points
    return points


def control_status(record: IntakeRecord, mitigation: Mitigation) -> str:
    """``applied`` needs a confirmed (or user-entered) answer that includes the control; an
    inferred answer is only a claim until the owner confirms it."""
    meta = record.get_field(mitigation.field)
    if meta.value is None or meta.is_unknown:
        return "unknown"
    present = (
        meta.value is True
        if mitigation.field == HUMAN_OVERSIGHT
        else isinstance(meta.value, list) and mitigation.control in meta.value
    )
    if not present:
        return "absent"
    if meta.confirmed or meta.source == "user":
        return "applied"
    return "unconfirmed"


def _profile(
    drivers: list[RiskDriver],
    *,
    record: IntakeRecord,
    classification: EuAiActClassification,
    lens: str | None,
    with_controls: bool,
) -> RiskProfile:
    """Score ``drivers`` (already filtered to the lens), optionally removing the mitigations
    of the lens that are applied, then apply the floor where it belongs."""
    remaining = category_points(drivers)
    effects: dict[str, ControlEffect] = {}
    if with_controls:
        for mitigation in MITIGATIONS:
            if lens is not None and lens not in mitigation.lenses:
                continue
            status = control_status(record, mitigation)
            removed = 0
            if status == "applied":
                removed = min(mitigation.points, remaining[mitigation.category])
                remaining[mitigation.category] -= removed
            effect = effects.get(mitigation.control)
            if effect is None:
                effects[mitigation.control] = ControlEffect(
                    field=mitigation.field,
                    control=mitigation.control,
                    status=status,
                    points=removed,
                    text=mitigation.text,
                )
            else:
                effect.points += removed
    score = sum(remaining.values())
    floors = RESIDUAL_FLOOR if with_controls else INHERENT_FLOOR
    floor = floors[classification] if lens is None or lens in FLOORED_LENSES else None
    tier, floor_tier, reason = apply_floor(tier_for_score(score), floor)
    return RiskProfile(
        lens=lens,
        tier=tier,
        score=score,
        drivers=drivers,
        controls=list(effects.values()),
        floor=floor_tier,
        floor_reason=reason,
    )


def inherent(record: IntakeRecord, classification: EuAiActClassification) -> RiskProfile:
    return _profile(
        inherent_drivers(record),
        record=record,
        classification=classification,
        lens=None,
        with_controls=False,
    )


def residual(
    record: IntakeRecord, classification: EuAiActClassification, inherent_profile: RiskProfile
) -> RiskProfile:
    return _profile(
        inherent_profile.drivers,
        record=record,
        classification=classification,
        lens=None,
        with_controls=True,
    )


def lens_profiles(
    record: IntakeRecord, classification: EuAiActClassification, inherent_profile: RiskProfile
) -> list[RiskLens]:
    """Inherent and residual per lens, from the drivers and mitigations tagged with it."""
    lenses: list[RiskLens] = []
    for name, label in LENSES:
        drivers = [driver for driver in inherent_profile.drivers if name in driver.lenses]
        lenses.append(
            RiskLens(
                lens=name,
                label=label,
                inherent=_profile(
                    drivers,
                    record=record,
                    classification=classification,
                    lens=name,
                    with_controls=False,
                ),
                residual=_profile(
                    drivers,
                    record=record,
                    classification=classification,
                    lens=name,
                    with_controls=True,
                ),
            )
        )
    return lenses
