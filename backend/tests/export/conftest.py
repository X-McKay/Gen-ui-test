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
        from app.intake import repository
        from app.settings import get_settings

        get_settings.cache_clear()
        repository.reset_engine()
        assert os.environ["DATABASE_URL"].endswith("export-tests.sqlite")
        yield
        get_settings.cache_clear()
        repository.reset_engine()


@pytest.fixture
def schema_path() -> Path:
    return SCHEMA_PATH


def build_high_risk_record(intake_id: str = "t"):  # type: ignore[no-untyped-def]
    """A realistic, partially unknown HR screening intake with an assessment attached."""
    from app.intake.schema import (
        EuAiActClassification,
        IntakeMode,
        Obligation,
        RationaleEntry,
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
