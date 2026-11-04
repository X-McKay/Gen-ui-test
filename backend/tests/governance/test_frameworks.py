"""Applicability, obligations and tier floors of the pluggable framework modules."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest

from app.governance.frameworks import (
    FRAMEWORK_MODULES,
    NOT_APPLICABLE,
    FrameworkModule,
    FrameworkResult,
    gdpr,
    internal_policy,
    iso_42001,
    mifid_algorithmic_trading,
    nist_ai_rmf,
)
from app.intake.schema import (
    AutonomyLevel,
    DataSubject,
    Domain,
    EuAiActAssessment,
    EuAiActClassification,
    IntakeRecord,
    LifecycleStage,
    ModelSource,
    RiskTier,
    SpecialCategory,
    WorldAction,
)

RecordFactory = Callable[..., IntakeRecord]

MINIMAL_EU = EuAiActAssessment()
HIGH_RISK_EU = EuAiActAssessment(classification=EuAiActClassification.HIGH_RISK)
PROHIBITED_EU = EuAiActAssessment(classification=EuAiActClassification.PROHIBITED)


def texts(result: FrameworkResult) -> list[str]:
    return [item.text for item in result.obligations]


def references(result: FrameworkResult) -> list[str]:
    return [item.reference or "" for item in result.obligations]


@pytest.fixture
def reset_local_privacy_law() -> Iterator[None]:
    yield
    gdpr.set_local_privacy_law_name(None)


# --- Registry -------------------------------------------------------------------------------


def test_registry_order_and_names() -> None:
    assert [module.name for module in FRAMEWORK_MODULES] == [
        "GDPR",
        "NIST AI RMF",
        "ISO/IEC 42001",
        "MiFID II algorithmic trading",
        "Internal AI policy",
    ]


def test_not_applicable_sentinel_is_empty() -> None:
    assert FrameworkResult(applies=False) == NOT_APPLICABLE
    assert NOT_APPLICABLE.obligations == []
    assert NOT_APPLICABLE.tier_floor is None
    assert NOT_APPLICABLE.additional_frameworks == []


@pytest.mark.parametrize(
    ("module", "values"),
    [
        (gdpr, {"data.processes_personal_data": True}),
        (nist_ai_rmf, {"ai_system.uses_ai": True}),
        (
            iso_42001,
            {"ai_system.uses_ai": True, "project.lifecycle_stage": LifecycleStage.PILOT},
        ),
        (internal_policy, {}),
    ],
    ids=["gdpr", "nist", "iso", "internal"],
)
def test_module_applies_on_its_trigger(
    module: FrameworkModule, values: dict[str, object], make_record: RecordFactory
) -> None:
    result = module.evaluate(make_record(values), MINIMAL_EU)
    assert result.applies
    assert result.obligations
    assert all(item.framework == module.name for item in result.obligations)


@pytest.mark.parametrize(
    ("module", "values"),
    [
        (gdpr, {}),
        (gdpr, {"data.processes_personal_data": "unknown"}),
        (gdpr, {"data.processes_personal_data": False, "data.special_category_data": []}),
        (nist_ai_rmf, {}),
        (nist_ai_rmf, {"ai_system.uses_ai": "unknown"}),
        (iso_42001, {"ai_system.uses_ai": True}),
        (iso_42001, {"ai_system.uses_ai": True, "project.lifecycle_stage": LifecycleStage.IDEA}),
        (iso_42001, {"project.lifecycle_stage": LifecycleStage.PRODUCTION}),
    ],
    ids=[
        "gdpr-blank",
        "gdpr-unknown",
        "gdpr-false",
        "nist-blank",
        "nist-unknown",
        "iso-no-stage",
        "iso-idea",
        "iso-no-ai",
    ],
)
def test_module_does_not_apply(
    module: FrameworkModule, values: dict[str, object], make_record: RecordFactory
) -> None:
    result = module.evaluate(make_record(values), MINIMAL_EU)
    assert result is NOT_APPLICABLE


# --- GDPR -----------------------------------------------------------------------------------


def test_gdpr_applies_on_special_categories_alone(make_record: RecordFactory) -> None:
    record = make_record({"data.special_category_data": [SpecialCategory.HEALTH]})
    result = gdpr.evaluate(record, MINIMAL_EU)
    assert result.applies
    assert result.tier_floor is RiskTier.MEDIUM
    assert any("Art. 9" in reference for reference in references(result))
    assert any("impact assessment" in text for text in texts(result))


def test_gdpr_baseline_obligations_only(make_record: RecordFactory) -> None:
    result = gdpr.evaluate(make_record({"data.processes_personal_data": True}), MINIMAL_EU)
    assert references(result) == ["GDPR Art. 6, Art. 13, Art. 14", "GDPR Art. 30"]
    assert result.tier_floor is None
    assert result.next_steps == []
    assert result.additional_frameworks == []


@pytest.mark.parametrize(
    ("values", "eu", "reason"),
    [
        ({}, HIGH_RISK_EU, "high-risk under the EU AI Act"),
        ({"data.special_category_data": [SpecialCategory.CRIMINAL]}, MINIMAL_EU, "special"),
        ({"data.data_subjects": [DataSubject.CUSTOMERS, DataSubject.MINORS]}, MINIMAL_EU, "minors"),
        ({"data.trains_on_personal_data": True}, MINIMAL_EU, "training"),
    ],
    ids=["high-risk", "special-categories", "minors", "training"],
)
def test_gdpr_dpia_triggers(
    values: dict[str, object], eu: EuAiActAssessment, reason: str, make_record: RecordFactory
) -> None:
    record = make_record({"data.processes_personal_data": True, **values})
    result = gdpr.evaluate(record, eu)
    dpia = [item for item in result.obligations if item.reference == "GDPR Art. 35"]
    assert len(dpia) == 1
    assert reason in dpia[0].text
    assert result.next_steps == ["Book a DPIA with the data protection officer before go-live"]


def test_gdpr_dpia_lists_every_reason_once(make_record: RecordFactory) -> None:
    record = make_record(
        {
            "data.processes_personal_data": True,
            "data.special_category_data": [SpecialCategory.HEALTH],
            "data.data_subjects": [DataSubject.MINORS],
            "data.trains_on_personal_data": True,
        }
    )
    result = gdpr.evaluate(record, HIGH_RISK_EU)
    dpia = next(item for item in result.obligations if item.reference == "GDPR Art. 35")
    assert dpia.text.count(";") == 3


def test_gdpr_minors_floor_medium(make_record: RecordFactory) -> None:
    record = make_record(
        {"data.processes_personal_data": True, "data.data_subjects": [DataSubject.MINORS]}
    )
    assert gdpr.evaluate(record, MINIMAL_EU).tier_floor is RiskTier.MEDIUM


def test_gdpr_cross_border_and_retention(make_record: RecordFactory) -> None:
    record = make_record(
        {
            "data.processes_personal_data": True,
            "data.cross_border_transfer": True,
            "data.retention_policy": "undefined",
        }
    )
    result = gdpr.evaluate(record, MINIMAL_EU)
    assert any("transfer mechanism" in text for text in texts(result))
    assert any("retention period" in text for text in texts(result))


def test_gdpr_unknown_transfer_and_defined_retention_add_nothing(
    make_record: RecordFactory,
) -> None:
    record = make_record(
        {
            "data.processes_personal_data": True,
            "data.cross_border_transfer": "unknown",
            "data.retention_policy": "under_30_days",
        }
    )
    result = gdpr.evaluate(record, MINIMAL_EU)
    assert len(result.obligations) == 2


def test_gdpr_local_privacy_law_placeholder_is_not_listed(make_record: RecordFactory) -> None:
    assert gdpr.LOCAL_PRIVACY_LAW_NAME == "[LOCAL PRIVACY LAW]"
    assert not gdpr.local_privacy_law_configured()
    result = gdpr.evaluate(make_record({"data.processes_personal_data": True}), MINIMAL_EU)
    assert result.additional_frameworks == []


@pytest.mark.usefixtures("reset_local_privacy_law")
def test_gdpr_local_privacy_law_when_configured(make_record: RecordFactory) -> None:
    gdpr.set_local_privacy_law_name("UK GDPR")
    assert gdpr.local_privacy_law_configured()
    result = gdpr.evaluate(make_record({"data.processes_personal_data": True}), MINIMAL_EU)
    assert result.additional_frameworks == ["UK GDPR"]
    local = [item for item in result.obligations if item.framework == "UK GDPR"]
    assert len(local) == 1
    assert "UK GDPR" in local[0].text

    gdpr.set_local_privacy_law_name(None)
    assert gdpr.LOCAL_PRIVACY_LAW_NAME == gdpr.LOCAL_PRIVACY_LAW_PLACEHOLDER


@pytest.mark.usefixtures("reset_local_privacy_law")
def test_gdpr_empty_local_privacy_law_counts_as_unset() -> None:
    gdpr.set_local_privacy_law_name("")
    assert not gdpr.local_privacy_law_configured()


# --- NIST AI RMF ----------------------------------------------------------------------------


def test_nist_baseline_covers_all_four_functions(make_record: RecordFactory) -> None:
    result = nist_ai_rmf.evaluate(make_record({"ai_system.uses_ai": True}), MINIMAL_EU)
    prefixes = [text.split(":")[0] for text in texts(result)]
    assert prefixes == ["Govern", "Map", "Measure", "Manage"]
    assert result.tier_floor is None


@pytest.mark.parametrize(
    "values",
    [
        {"use_case.affects_legal_or_significant_effects": True},
        {"use_case.domains": [Domain.OTHER, Domain.CREDIT_INSURANCE]},
    ],
    ids=["significant-effects", "annex-iii-domain"],
)
def test_nist_bias_testing(values: dict[str, object], make_record: RecordFactory) -> None:
    record = make_record({"ai_system.uses_ai": True, **values})
    result = nist_ai_rmf.evaluate(record, MINIMAL_EU)
    assert any("bias" in text for text in texts(result))


def test_nist_no_bias_testing_without_signal(make_record: RecordFactory) -> None:
    record = make_record(
        {
            "ai_system.uses_ai": True,
            "use_case.affects_legal_or_significant_effects": "unknown",
            "use_case.domains": [Domain.OTHER],
        }
    )
    assert not any("bias" in text for text in texts(nist_ai_rmf.evaluate(record, MINIMAL_EU)))


@pytest.mark.parametrize(
    ("stage", "expected"),
    [
        (LifecycleStage.IDEA, False),
        (LifecycleStage.POC, False),
        (LifecycleStage.PILOT, True),
        (LifecycleStage.PRODUCTION, True),
        ("unknown", False),
    ],
)
def test_nist_monitoring_in_operation(
    stage: object, expected: bool, make_record: RecordFactory
) -> None:
    record = make_record({"ai_system.uses_ai": True, "project.lifecycle_stage": stage})
    result = nist_ai_rmf.evaluate(record, MINIMAL_EU)
    assert any("drift" in text for text in texts(result)) is expected


@pytest.mark.parametrize(
    ("eu", "expected"),
    [(MINIMAL_EU, False), (HIGH_RISK_EU, True), (PROHIBITED_EU, True)],
    ids=["minimal", "high-risk", "prohibited"],
)
def test_nist_sign_off_for_elevated_tiers(
    eu: EuAiActAssessment, expected: bool, make_record: RecordFactory
) -> None:
    result = nist_ai_rmf.evaluate(make_record({"ai_system.uses_ai": True}), eu)
    assert any("sign-off" in text for text in texts(result)) is expected


# --- ISO/IEC 42001 --------------------------------------------------------------------------


def test_iso_baseline_impact_assessment(make_record: RecordFactory) -> None:
    record = make_record(
        {"ai_system.uses_ai": True, "project.lifecycle_stage": LifecycleStage.PRODUCTION}
    )
    result = iso_42001.evaluate(record, MINIMAL_EU)
    assert references(result) == ["ISO/IEC 42001 Clause 6.1.4, Annex A.5"]


def test_iso_supplier_and_data_quality_controls(make_record: RecordFactory) -> None:
    record = make_record(
        {
            "ai_system.uses_ai": True,
            "project.lifecycle_stage": LifecycleStage.PILOT,
            "ai_system.model_source": ModelSource.THIRD_PARTY_API,
            "ai_system.fine_tuned_or_trained": True,
        }
    )
    result = iso_42001.evaluate(record, MINIMAL_EU)
    assert any("supplier controls" in text.lower() for text in texts(result))
    assert any("training data" in text for text in texts(result))


def test_iso_in_house_untrained_adds_no_extra_controls(make_record: RecordFactory) -> None:
    record = make_record(
        {
            "ai_system.uses_ai": True,
            "project.lifecycle_stage": LifecycleStage.PILOT,
            "ai_system.model_source": ModelSource.IN_HOUSE,
            "ai_system.fine_tuned_or_trained": "unknown",
        }
    )
    assert len(iso_42001.evaluate(record, MINIMAL_EU).obligations) == 1


# --- Internal policy ------------------------------------------------------------------------


def test_internal_policy_always_applies_with_inventory(make_record: RecordFactory) -> None:
    result = internal_policy.evaluate(make_record(), MINIMAL_EU)
    assert result.applies
    assert texts(result)[0] == "Register the system in the AI inventory"


@pytest.mark.parametrize(
    ("owner", "expected"),
    [(None, True), ("unknown", True), ("   ", True), ("Dana Reyes", False)],
    ids=["missing", "unknown", "blank", "named"],
)
def test_internal_policy_owner_required(
    owner: object, expected: bool, make_record: RecordFactory
) -> None:
    values: dict[str, object] = {} if owner is None else {"project.owner": owner}
    result = internal_policy.evaluate(make_record(values), MINIMAL_EU)
    assert any("accountable owner" in text for text in texts(result)) is expected
    assert (result.next_steps == ["Record a named owner for the project"]) is expected


@pytest.mark.parametrize(
    ("values", "review", "floor"),
    [
        ({"ai_system.autonomy_level": AutonomyLevel.DECIDES}, True, RiskTier.MEDIUM),
        ({"ai_system.human_oversight": False}, True, None),
        (
            {
                "ai_system.autonomy_level": AutonomyLevel.RECOMMENDS,
                "ai_system.human_oversight": True,
            },
            False,
            None,
        ),
        ({"ai_system.human_oversight": "unknown"}, False, None),
    ],
    ids=["decides", "no-oversight", "recommends-with-oversight", "oversight-unknown"],
)
def test_internal_policy_oversight_review_and_floor(
    values: dict[str, object],
    review: bool,
    floor: RiskTier | None,
    make_record: RecordFactory,
) -> None:
    result = internal_policy.evaluate(make_record(values), MINIMAL_EU)
    assert any("human-oversight review" in text for text in texts(result)) is review
    assert result.tier_floor is floor


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (ModelSource.THIRD_PARTY_API, True),
        (ModelSource.OPEN_WEIGHTS, False),
        ("unknown", False),
    ],
)
def test_internal_policy_vendor_review(
    source: object, expected: bool, make_record: RecordFactory
) -> None:
    result = internal_policy.evaluate(make_record({"ai_system.model_source": source}), MINIMAL_EU)
    assert any("vendor review" in text for text in texts(result)) is expected


# --- MiFID II algorithmic trading -----------------------------------------------------------

TRADING: dict[str, object] = {
    "ai_system.uses_ai": True,
    "use_case.domains": [Domain.FINANCIAL_MARKETS],
    "ai_system.autonomy_level": AutonomyLevel.DECIDES,
    "use_case.acts_on_the_world": [WorldAction.FINANCIAL_TRANSACTIONS],
    "ai_system.human_oversight": True,
}


@pytest.mark.parametrize(
    "values",
    [
        {**TRADING, "use_case.domains": [Domain.OTHER]},
        {**TRADING, "use_case.domains": "unknown"},
        {**TRADING, "ai_system.autonomy_level": AutonomyLevel.RECOMMENDS},
        {**TRADING, "ai_system.autonomy_level": "unknown"},
    ],
)
def test_mifid_does_not_apply_without_automated_orders_in_financial_markets(
    make_record: RecordFactory, values: dict[str, object]
) -> None:
    assert mifid_algorithmic_trading.evaluate(make_record(values), MINIMAL_EU) == NOT_APPLICABLE


def test_mifid_obligations_floor_and_dora(make_record: RecordFactory) -> None:
    result = mifid_algorithmic_trading.evaluate(make_record(TRADING), MINIMAL_EU)
    assert result.applies and result.tier_floor is RiskTier.HIGH
    assert result.additional_frameworks == ["DORA"]
    assert [o.framework for o in result.obligations].count("DORA") == 1
    assert any("kill functionality" in text for text in texts(result))
    assert any("pre-trade limits" in text.lower() for text in texts(result))
    assert any("competent authority" in text for text in texts(result))
    assert any("annual self-assessment" in text for text in texts(result))
    assert all(reference for reference in references(result))
    assert result.next_steps == [
        "Confirm the pre-trade limits and kill functionality with the risk function before go-live",
    ]


def test_mifid_asks_for_a_monitoring_owner_without_oversight(make_record: RecordFactory) -> None:
    result = mifid_algorithmic_trading.evaluate(
        make_record({**TRADING, "ai_system.human_oversight": False}), MINIMAL_EU
    )
    assert any("monitors the algorithm" in step for step in result.next_steps)
