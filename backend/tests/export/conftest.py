"""Shared fixtures for the export tests: isolated SQLite database and sample records."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schema" / "intake.schema.json"


@pytest.fixture(scope="session", autouse=True)
def isolated_database(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Point persistence at a throw-away SQLite file before any settings are read."""
    database_path = tmp_path_factory.mktemp("db") / "export-tests.sqlite"
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
        monkeypatch.setenv("MOCK_MODEL", "1")
        monkeypatch.delenv("INTAKE_WEBHOOK_URL", raising=False)
        from app.intake import intake_store
        from app.settings import get_settings

        get_settings.cache_clear()
        intake_store.reset_engine()
        assert os.environ["DATABASE_URL"].endswith("export-tests.sqlite")
        yield
        get_settings.cache_clear()
        intake_store.reset_engine()


@pytest.fixture
def schema_path() -> Path:
    return SCHEMA_PATH


def build_high_risk_record(intake_id: str = "t"):  # type: ignore[no-untyped-def]
    """A realistic, partially unknown HR screening intake with an assessment attached."""
    from app.intake.schema import (
        ControlEffect,
        ControlKind,
        EuAiActClassification,
        IntakeMode,
        Obligation,
        RationaleEntry,
        RiskDriver,
        RiskLens,
        RiskProfile,
        RiskTier,
        new_record,
    )

    record = new_record(intake_id, IntakeMode.EXISTING)
    record.meta.repo_url = "https://github.com/example/candidate-screener"
    record.meta.question_count = 7
    record.set_field(
        "project.name",
        "Candidate summary assistant",
        source="user",
        confidence=1.0,
        confirmed=True,
    )
    record.set_field("project.owner", "Talent Ops", source="user", confidence=1.0, confirmed=True)
    record.set_field(
        "project.lifecycle_stage", "pilot", source="inferred", confidence=0.85, confirmed=False
    )
    record.set_field(
        "ai_system.uses_ai",
        True,
        source="repo:requirements.txt",
        confidence=0.95,
        confirmed=True,
    )
    record.set_field(
        "ai_system.model_source",
        "third_party_api",
        source="repo:app/llm.py",
        confidence=0.9,
        confirmed=True,
    )
    record.set_field(
        "ai_system.autonomy_level", "recommends", source="user", confidence=1.0, confirmed=True
    )
    record.set_field(
        "data.processes_personal_data", True, source="user", confidence=1.0, confirmed=True
    )
    record.set_field(
        "data.special_category_data", "unknown", source="user", confidence=1.0, confirmed=True
    )
    record.set_field(
        "data.data_subjects",
        ["employees", "minors"],
        source="user",
        confidence=1.0,
        confirmed=True,
    )
    record.set_field(
        "use_case.domains", ["hr_employment"], source="user", confidence=1.0, confirmed=True
    )
    record.set_field(
        "use_case.affects_legal_or_significant_effects",
        True,
        source="user",
        confidence=1.0,
        confirmed=True,
    )
    record.set_field(
        "use_case.interacts_directly_with_people",
        False,
        source="user",
        confidence=1.0,
        confirmed=True,
    )
    record.set_field(
        "ai_system.human_oversight", True, source="user", confidence=1.0, confirmed=True
    )
    # Inferred from the repository and not yet confirmed: a claim, so it lowers nothing.
    record.set_field(
        "controls.in_place",
        [ControlKind.ACCESS_CONTROLS, ControlKind.GUARDRAILS],
        source="repo:app/auth.py",
        confidence=0.7,
        confirmed=False,
    )

    assessment = record.assessment
    assessment.eu_ai_act.classification = EuAiActClassification.HIGH_RISK
    assessment.eu_ai_act.annex_iii_categories = ["4. Employment and workers management"]
    assessment.eu_ai_act.rationale = [
        RationaleEntry(
            field="use_case.domains",
            value=["hr_employment"],
            article="EU AI Act Art. 6(2), Annex III 4",
            text="Recruitment and worker-management systems are high-risk.",
            effect="high_risk",
        )
    ]
    assessment.overall_risk_tier = RiskTier.HIGH
    drivers = [
        RiskDriver(
            field="ai_system.autonomy_level",
            value="recommends",
            category="autonomy",
            points=1,
            text="It recommends; a person decides",
            lenses=["operational"],
        ),
        RiskDriver(
            field="data.processes_personal_data",
            value=True,
            category="data",
            points=2,
            text="It processes personal data",
            lenses=["data_privacy", "regulatory"],
        ),
        RiskDriver(
            field="data.data_subjects",
            value=["employees", "minors"],
            category="data",
            points=2,
            text="Minors are among the data subjects",
            lenses=["data_privacy", "reputational"],
        ),
        RiskDriver(
            field="use_case.affects_legal_or_significant_effects",
            value=True,
            category="impact",
            points=3,
            text="Outputs affect rights, access or significant decisions",
            lenses=["regulatory", "reputational"],
        ),
        RiskDriver(
            field="use_case.domains",
            value=["hr_employment"],
            category="impact",
            points=2,
            text="It operates in an Annex III area",
            lenses=["regulatory"],
        ),
    ]
    human_oversight = ControlEffect(
        field="ai_system.human_oversight",
        control="ai_system.human_oversight",
        status="applied",
        points=2,  # two mitigations on the same control, aggregated by the engine
        text="A person reviews or can override outputs",
    )
    assessment.inherent_risk = RiskProfile(tier=RiskTier.HIGH, score=10, drivers=drivers)
    assessment.residual_risk = RiskProfile(
        tier=RiskTier.MEDIUM,
        score=8,
        drivers=drivers,
        controls=[
            human_oversight,
            ControlEffect(
                field="controls.in_place",
                control="guardrails",
                status="unconfirmed",
                points=0,
                text="Input and output guardrails are in place",
            ),
            ControlEffect(
                field="controls.in_place",
                control="pii_minimisation",
                status="absent",
                points=0,
                text="Personal data is minimised before the model",
            ),
            ControlEffect(
                field="controls.in_place",
                control="access_controls",
                status="unconfirmed",
                points=0,
                text="Access is authenticated and authorised",
            ),
            ControlEffect(
                field="controls.in_place",
                control="vendor_data_protections",
                status="unknown",
                points=0,
                text="Provider may not train on the data",
            ),
        ],
        floor=RiskTier.MEDIUM,
        floor_reason="Annex III obligations remain whatever controls are in place",
    )
    # Three of the six lenses, in the engine's order; one with no driver at all.
    privacy_drivers = [drivers[1], drivers[2]]
    regulatory_drivers = [drivers[1], drivers[3], drivers[4]]
    assessment.risk_lenses = [
        RiskLens(
            lens="data_privacy",
            label="Data and privacy",
            inherent=RiskProfile(
                lens="data_privacy", tier=RiskTier.MEDIUM, score=4, drivers=privacy_drivers
            ),
            residual=RiskProfile(
                lens="data_privacy",
                tier=RiskTier.MEDIUM,
                score=4,
                drivers=privacy_drivers,
                controls=[
                    ControlEffect(
                        field="controls.in_place",
                        control="pii_minimisation",
                        status="absent",
                        points=0,
                        text="Personal data is minimised before the model",
                    )
                ],
            ),
        ),
        RiskLens(
            lens="financial",
            label="Financial",
            inherent=RiskProfile(lens="financial"),
            residual=RiskProfile(lens="financial"),
        ),
        RiskLens(
            lens="regulatory",
            label="Regulatory",
            inherent=RiskProfile(
                lens="regulatory", tier=RiskTier.HIGH, score=7, drivers=regulatory_drivers
            ),
            residual=RiskProfile(
                lens="regulatory",
                tier=RiskTier.MEDIUM,
                score=5,
                drivers=regulatory_drivers,
                controls=[human_oversight],
                floor=RiskTier.MEDIUM,
                floor_reason="Annex III obligations remain whatever controls are in place",
            ),
        ),
    ]
    assessment.applicable_frameworks = ["EU AI Act", "GDPR"]
    assessment.obligations = [
        Obligation(
            framework="EU AI Act",
            text="Register the system in the EU database before deployment.",
            reference="Art. 49",
            role="provider",
        ),
        Obligation(
            framework="GDPR",
            text="Carry out a data protection impact assessment.",
            reference="Art. 35",
            role=None,
        ),
    ]
    assessment.recommended_next_steps = ["Book a review with the governance team."]
    assessment.open_questions = ["data.special_category_data"]
    return record


@pytest.fixture
def high_risk_record():  # type: ignore[no-untyped-def]
    return build_high_risk_record()


@pytest.fixture
def empty_record():  # type: ignore[no-untyped-def]
    from app.intake.schema import new_record

    return new_record("empty")
