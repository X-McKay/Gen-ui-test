from __future__ import annotations

from pathlib import Path

from app.intake.question_bank import QUESTIONS_BY_FIELD
from app.repo_analysis.inventory import RepositoryInventory, build_inventory
from app.repo_analysis.signal_detectors import (
    Signal,
    count_model_integrations,
    declared_dependencies,
    detect_biometric_indicators,
    detect_data_source_clients,
    detect_deployment_signals,
    detect_domain_keywords,
    detect_model_sdks,
    detect_pii_indicators,
    detect_retention_policy,
    imported_modules,
    make_snippet,
    run_all_detectors,
)

PLANTED_TOKEN = "ghp_FAKE123"


def _by_field(signals: list[Signal]) -> dict[str, list[Signal]]:
    grouped: dict[str, list[Signal]] = {}
    for signal in signals:
        grouped.setdefault(signal.field, []).append(signal)
    return grouped


def _values(signals: list[Signal], field: str) -> set[object]:
    values: set[object] = set()
    for signal in signals:
        if signal.field != field:
            continue
        if isinstance(signal.value, list):
            values.update(signal.value)
        else:
            values.add(signal.value)
    return values


def _assert_values_are_valid_options(signals: list[Signal]) -> None:
    for signal in signals:
        spec = QUESTIONS_BY_FIELD[signal.field]
        if spec.control == "yes_no":
            assert isinstance(signal.value, bool), signal
        elif spec.options:
            allowed = {option.value for option in spec.options}
            items = signal.value if isinstance(signal.value, list) else [signal.value]
            for item in items:
                assert item in allowed, (signal.field, item)


# --- helpers -------------------------------------------------------------------------------


def test_imported_modules_python_and_javascript() -> None:
    assert imported_modules("from openai import OpenAI") == ["openai"]
    assert imported_modules("import torch, numpy as np") == ["torch", "numpy"]
    assert imported_modules("import google.generativeai as genai") == ["google.generativeai"]
    assert imported_modules('const { OpenAI } = require("openai");') == ["openai"]
    assert imported_modules("import Anthropic from '@anthropic-ai/sdk';") == ["@anthropic-ai/sdk"]
    assert imported_modules("x = 1") == []


def test_declared_dependencies() -> None:
    assert declared_dependencies("openai==1.51.0") == ["openai"]
    assert declared_dependencies("psycopg2-binary>=2.9") == ["psycopg2-binary"]
    assert declared_dependencies('    "litellm>=1.0",') == ["litellm"]
    assert declared_dependencies('    "elasticsearch": "^8.0.0",') == ["elasticsearch"]
    assert declared_dependencies('{"deps": {"openai": "^4", "@anthropic-ai/sdk": "1"}}') == [
        "deps",
        "openai",
        "@anthropic-ai/sdk",
    ]
    assert declared_dependencies("# comment") == []
    assert declared_dependencies("-r base.txt") == []


def test_make_snippet_trims_and_redacts() -> None:
    line = "   TOKEN=ghp_FAKE123456789   " + "x" * 300
    snippet = make_snippet(line)
    assert len(snippet) <= 160
    assert "ghp_FAKE123456789" not in snippet
    assert snippet.startswith("TOKEN=***")


# --- model SDKs ----------------------------------------------------------------------------


def test_model_sdks_hr_screening(hr_screening_inventory: RepositoryInventory) -> None:
    signals = detect_model_sdks(hr_screening_inventory)
    grouped = _by_field(signals)
    assert grouped["ai_system.uses_ai"][0].value is True
    assert grouped["ai_system.uses_ai"][0].confidence == 0.9
    assert grouped["ai_system.uses_ai"][0].evidence_path == "src/ranking/summarise.py"
    assert grouped["ai_system.uses_ai"][0].snippet == "from openai import OpenAI"
    assert _values(signals, "ai_system.model_providers") == {"openai"}
    assert grouped["ai_system.model_source"][0].value == "third_party_api"
    assert grouped["ai_system.gpai_model_used"][0].value is True
    assert _values(signals, "ai_system.model_types") == {"llm"}
    assert count_model_integrations(signals) == 1
    _assert_values_are_valid_options(signals)


def test_model_sdks_log_search(log_search_inventory: RepositoryInventory) -> None:
    signals = detect_model_sdks(log_search_inventory)
    grouped = _by_field(signals)
    assert grouped["ai_system.uses_ai"][0].evidence_path == "src/search/query.py"
    assert grouped["ai_system.gpai_model_used"][0].value is True
    assert "ai_system.model_providers" not in grouped  # LiteLLM routes to any provider
    assert grouped["ai_system.model_source"][0].value == "third_party_api"
    assert grouped["ai_system.model_source"][0].confidence < 0.9


def test_model_sdks_manifest_only_and_azure(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{\n  "dependencies": {\n'
        '    "@anthropic-ai/sdk": "^0.30.0",\n'
        '    "openai": "^4.0.0"\n  }\n}\n'
    )
    (tmp_path / "index.ts").write_text(
        'import { AzureOpenAI } from "openai";\nconst client = new AzureOpenAI();\n'
    )
    (tmp_path / "train.py").write_text("import torch\nfrom sklearn.linear_model import Ridge\n")
    signals = detect_model_sdks(build_inventory(tmp_path, max_files=10))
    providers = _values(signals, "ai_system.model_providers")
    assert providers == {"anthropic", "azure_openai"}
    assert "classical_ml" in _values(signals, "ai_system.model_types")
    assert count_model_integrations(signals) == 4
    sources = {signal.value for signal in signals if signal.field == "ai_system.model_source"}
    assert sources == {"third_party_api", "in_house"}
    _assert_values_are_valid_options(signals)


# --- personal data -------------------------------------------------------------------------


def test_pii_indicators_hr_screening(hr_screening_inventory: RepositoryInventory) -> None:
    signals = detect_pii_indicators(hr_screening_inventory)
    grouped = _by_field(signals)
    personal = grouped["data.processes_personal_data"][0]
    assert personal.value is True
    assert personal.confidence == 0.8
    assert personal.evidence_path.startswith("src/")
    categories = _values(signals, "data.pii_categories")
    assert {"contact", "identifiers", "financial", "employment", "free_text"} <= categories
    assert _values(signals, "data.data_subjects") == {"employees"}
    paths = {signal.evidence_path for signal in signals}
    assert {"src/models/candidate.py", "src/ingest/cv_parser.py"} & paths
    assert "data.special_category_data" not in grouped
    _assert_values_are_valid_options(signals)


def test_pii_indicators_log_search_negative(log_search_inventory: RepositoryInventory) -> None:
    signals = detect_pii_indicators(log_search_inventory)
    grouped = _by_field(signals)
    assert grouped["data.processes_personal_data"][0].value is False
    assert grouped["data.processes_personal_data"][0].evidence_path == "README.md"
    assert "data.pii_categories" not in grouped
    assert "data.data_subjects" not in grouped


def test_pii_indicators_special_categories_and_minors(tmp_path: Path) -> None:
    (tmp_path / "models.py").write_text(
        "class Pupil(Base):\n"
        "    student_id = Column(Integer)\n"
        "    parental_consent = Column(Boolean)\n"
        "    ethnicity = Column(String)\n"
        "    medical_record = Column(Text)\n"
        "    religion = Column(String)\n"
    )
    signals = detect_pii_indicators(build_inventory(tmp_path, max_files=10))
    assert _values(signals, "data.data_subjects") == {"minors"}
    assert _values(signals, "data.special_category_data") == {"ethnicity", "health", "religious"}
    _assert_values_are_valid_options(signals)


def test_pii_snippets_never_contain_planted_token(
    hr_screening_inventory: RepositoryInventory, hr_screening_root: Path, tmp_path: Path
) -> None:
    env_example = hr_screening_inventory.file(".env.example")
    assert env_example is not None and env_example.text is not None
    assert PLANTED_TOKEN in env_example.text  # the fixture really plants it
    for signal in run_all_detectors(hr_screening_inventory):
        assert PLANTED_TOKEN not in signal.snippet, signal
        assert "change-me" not in signal.snippet, signal

    # Force the planted line to be the only evidence and confirm it comes out redacted.
    (tmp_path / ".env.example").write_text((hr_screening_root / ".env.example").read_text())
    signals = run_all_detectors(build_inventory(tmp_path, max_files=10))
    env_signals = [signal for signal in signals if signal.evidence_path == ".env.example"]
    assert env_signals
    assert any(signal.field == "data.processes_personal_data" for signal in env_signals)
    for signal in env_signals:
        assert PLANTED_TOKEN not in signal.snippet, signal
        assert "change-me" not in signal.snippet, signal
    token_lines = [s for s in env_signals if s.snippet.startswith("ATS_EXPORT_TOKEN=")]
    assert token_lines
    assert token_lines[0].snippet.startswith("ATS_EXPORT_TOKEN=***")
    database_lines = [s for s in env_signals if s.snippet.startswith("DATABASE_URL=")]
    assert database_lines
    assert "postgresql://***@localhost" in database_lines[0].snippet


# --- biometrics ----------------------------------------------------------------------------


def test_biometric_indicators_absent_in_fixtures(
    hr_screening_inventory: RepositoryInventory, log_search_inventory: RepositoryInventory
) -> None:
    assert detect_biometric_indicators(hr_screening_inventory) == []
    assert detect_biometric_indicators(log_search_inventory) == []


def test_biometric_indicators_present(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("deepface==0.0.93\nopencv-python\n")
    (tmp_path / "verify.py").write_text(
        "import face_recognition\n"
        "import cv2\n"
        "cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')\n"
    )
    signals = detect_biometric_indicators(build_inventory(tmp_path, max_files=10))
    grouped = _by_field(signals)
    assert grouped["data.biometric_identification"][0].value is True
    assert grouped["data.biometric_identification"][0].evidence_path == "verify.py"
    assert grouped["data.biometric_identification"][0].confidence == 0.85
    assert _values(signals, "data.special_category_data") == {"biometric"}
    assert _values(signals, "ai_system.model_types") == {"vision"}
    _assert_values_are_valid_options(signals)


# --- data sources --------------------------------------------------------------------------


def test_data_sources_hr_screening(hr_screening_inventory: RepositoryInventory) -> None:
    signals = detect_data_source_clients(hr_screening_inventory)
    assert _values(signals, "data.data_sources") == {"internal_db", "user_upload"}
    by_value = {str(signal.value[0]): signal for signal in signals}  # type: ignore[index]
    assert by_value["internal_db"].evidence_path == "src/api/routes.py"
    assert by_value["internal_db"].confidence == 0.9
    assert by_value["user_upload"].evidence_path == "src/api/routes.py"
    _assert_values_are_valid_options(signals)


def test_data_sources_log_search(log_search_inventory: RepositoryInventory) -> None:
    signals = detect_data_source_clients(log_search_inventory)
    assert _values(signals, "data.data_sources") == {"logs"}
    assert signals[0].evidence_path == "src/search/query.py"
    assert signals[0].snippet == "from elasticsearch import Elasticsearch"


def test_data_sources_third_party_and_public_web(tmp_path: Path) -> None:
    (tmp_path / "fetch.py").write_text(
        "import requests\n"
        'rates = requests.get("https://api.exchangerate.host/latest").json()\n'
        'models = requests.get("https://api.openai.com/v1/models")\n'
        "import scrapy\n"
    )
    signals = detect_data_source_clients(build_inventory(tmp_path, max_files=10))
    assert _values(signals, "data.data_sources") == {"third_party", "public_web"}


# --- deployment ----------------------------------------------------------------------------


def test_deployment_hr_screening(hr_screening_inventory: RepositoryInventory) -> None:
    signals = detect_deployment_signals(hr_screening_inventory)
    grouped = _by_field(signals)
    stage = grouped["project.lifecycle_stage"][0]
    assert stage.value == "production"
    assert stage.confidence == 0.7
    assert stage.evidence_path == "infra/terraform/main.tf"
    regions = grouped["project.deployment_regions"][0]
    assert regions.value == ["eu"]
    assert regions.evidence_path == "infra/terraform/main.tf"
    assert "eu-west-1" in regions.snippet
    _assert_values_are_valid_options(signals)


def test_deployment_log_search(log_search_inventory: RepositoryInventory) -> None:
    signals = detect_deployment_signals(log_search_inventory)
    grouped = _by_field(signals)
    assert grouped["project.lifecycle_stage"][0].value == "pilot"
    assert grouped["project.lifecycle_stage"][0].confidence <= 0.7
    assert grouped["project.lifecycle_stage"][0].evidence_path == "Dockerfile"
    assert "project.deployment_regions" not in grouped


def test_deployment_regions_from_ci_and_config(tmp_path: Path) -> None:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "deploy.yml").write_text(
        "env:\n  AWS_REGION: us-east-1\n  AZURE_LOCATION: uksouth\n  GCP: asia-southeast1\n"
    )
    (tmp_path / "Dockerfile").write_text("FROM python:3.12\n")
    signals = detect_deployment_signals(build_inventory(tmp_path, max_files=10))
    assert _values(signals, "project.deployment_regions") == {"us", "uk", "apac"}
    assert _values(signals, "project.lifecycle_stage") == {"pilot"}


# --- domains -------------------------------------------------------------------------------


def test_domain_keywords_hr_screening(hr_screening_inventory: RepositoryInventory) -> None:
    signals = detect_domain_keywords(hr_screening_inventory)
    grouped = _by_field(signals)
    domains = grouped["use_case.domains"]
    assert [signal.value for signal in domains] == [["hr_employment"]]
    assert domains[0].confidence == 0.75
    assert domains[0].evidence_path == "README.md"
    assert grouped["use_case.generates_synthetic_content"][0].evidence_path == (
        "src/ranking/summarise.py"
    )
    _assert_values_are_valid_options(signals)


def test_domain_keywords_log_search(log_search_inventory: RepositoryInventory) -> None:
    signals = detect_domain_keywords(log_search_inventory)
    grouped = _by_field(signals)
    assert grouped["use_case.domains"][0].value == ["other"]
    assert grouped["use_case.domains"][0].confidence <= 0.75
    assert grouped["use_case.interacts_directly_with_people"][0].value is True
    assert grouped["use_case.interacts_directly_with_people"][0].evidence_path == "README.md"
    assert grouped["use_case.generates_synthetic_content"][0].value is True


def test_domain_keywords_multiple_domains(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "# Triage helper\n\nHelps clinicians prioritise patients and checks insurance cover.\n"
    )
    signals = detect_domain_keywords(build_inventory(tmp_path, max_files=10))
    assert _values(signals, "use_case.domains") == {
        "medical_or_safety_component",
        "credit_insurance",
    }


# --- retention -----------------------------------------------------------------------------


def test_retention_policy(
    hr_screening_inventory: RepositoryInventory, log_search_inventory: RepositoryInventory
) -> None:
    hr_signal = detect_retention_policy(hr_screening_inventory)[0]
    assert hr_signal.value == "under_1_year"
    assert hr_signal.evidence_path == "docs/retention.md"
    assert "6 months" in hr_signal.snippet
    log_signal = detect_retention_policy(log_search_inventory)[0]
    assert log_signal.value == "under_30_days"
    assert log_signal.evidence_path == "docs/privacy.md"


# --- whole pipeline ------------------------------------------------------------------------


def test_run_all_detectors_covers_required_fields(
    hr_screening_inventory: RepositoryInventory, log_search_inventory: RepositoryInventory
) -> None:
    hr_fields = {signal.field for signal in run_all_detectors(hr_screening_inventory)}
    assert len(hr_fields) >= 7
    assert {
        "ai_system.uses_ai",
        "data.processes_personal_data",
        "use_case.domains",
        "project.lifecycle_stage",
        "data.data_sources",
    } <= hr_fields
    log_fields = {signal.field for signal in run_all_detectors(log_search_inventory)}
    assert len(log_fields) >= 5
    for signal in run_all_detectors(hr_screening_inventory):
        assert signal.evidence_path
        assert signal.snippet
        assert 0.0 < signal.confidence <= 0.9
