from __future__ import annotations

from app.inference.structured_extraction import ExtractedField
from app.intake.question_bank import QUESTIONS_BY_FIELD, display_value
from app.intake.schema import new_record
from app.repo_analysis.inventory import RepositoryInventory
from app.repo_analysis.signal_detectors import Signal, run_all_detectors
from app.repo_analysis.summarize_findings import (
    RepositoryFinding,
    build_evidence_digest,
    findings_from_extraction,
    merge_signals,
    summarize_repository,
)
from app.settings import get_settings


def _signal(field: str, value: object, confidence: float, path: str, snippet: str) -> Signal:
    return Signal(field, value, confidence, path, snippet, "test")


def _assert_applies_to_record(finding: RepositoryFinding) -> None:
    record = new_record("check")
    stored = record.set_field(
        finding.field,
        finding.value,
        source=finding.source,
        confidence=finding.confidence,
        confirmed=False,
    )
    assert stored.source.startswith("repo:")


def test_mock_mode_is_active() -> None:
    assert get_settings().mock_model is True


def test_merge_signals_keeps_strongest_and_merges_lists() -> None:
    signals = [
        _signal("data.pii_categories", ["contact"], 0.8, "a.py", "email"),
        _signal("data.pii_categories", ["financial"], 0.6, "b.py", "salary"),
        _signal("data.pii_categories", ["contact", "identifiers"], 0.7, "c.py", "ssn"),
        _signal("data.processes_personal_data", False, 0.6, "README.md", "no personal data"),
        _signal("data.processes_personal_data", True, 0.8, "a.py", "email"),
        _signal("ai_system.model_source", "third_party_api", 0.9, "x.py", "import openai"),
        _signal("ai_system.model_source", "open_weights", 0.7, "y.py", "import vllm"),
    ]
    findings = {finding.field: finding for finding in merge_signals(signals)}
    assert findings["data.pii_categories"].value == ["contact", "identifiers", "financial"]
    assert findings["data.pii_categories"].evidence_path == "a.py"
    assert findings["data.pii_categories"].confidence == 0.8
    assert findings["data.processes_personal_data"].value is True
    assert findings["data.processes_personal_data"].evidence_path == "a.py"
    assert findings["ai_system.model_source"].value == "third_party_api"
    assert findings["ai_system.model_source"].source == "repo:x.py"
    assert findings["ai_system.model_source"].label == "Model source"
    assert findings["ai_system.model_source"].display_value == "Third-party API"


def test_merge_signals_drops_invalid_values() -> None:
    signals = [
        _signal("use_case.domains", ["not_a_domain"], 0.9, "README.md", "x"),
        _signal("project.lifecycle_stage", "beta", 0.9, "Dockerfile", "x"),
        _signal("nonexistent.field", True, 0.9, "x", "x"),
        _signal("ai_system.uses_ai", "yes", 0.9, "a.py", "import openai"),
    ]
    findings = {finding.field: finding for finding in merge_signals(signals)}
    assert set(findings) == {"ai_system.uses_ai"}
    assert findings["ai_system.uses_ai"].value is True  # coerced from "yes"


def test_findings_from_extraction_fills_uncovered_fields_with_readme_evidence(
    hr_screening_inventory: RepositoryInventory,
) -> None:
    extracted = [
        ExtractedField(
            path="project.target_users", value="internal", confidence=0.85, evidence="internal tool"
        ),
        ExtractedField(path="ai_system.uses_ai", value=True, confidence=0.95, evidence=None),
        ExtractedField(
            path="ai_system.human_oversight",
            value=True,
            confidence=0.85,
            evidence="reviews every summary",
        ),
        ExtractedField(path="use_case.purpose", value="x", confidence=0.3, evidence=None),
        ExtractedField(path="project.lifecycle_stage", value="beta", confidence=0.9, evidence=None),
        ExtractedField(
            path="data.retention_policy",
            value="over_1_year",
            confidence=0.6,
            evidence="zzzz qqqq",
        ),
    ]
    findings = findings_from_extraction(
        extracted, hr_screening_inventory, covered_fields={"ai_system.uses_ai"}
    )
    by_field = {finding.field: finding for finding in findings}
    assert set(by_field) == {
        "project.target_users",
        "ai_system.human_oversight",
        "data.retention_policy",
    }
    target = by_field["project.target_users"]
    assert target.evidence_path == "README.md"
    assert "Internal HR tool" in target.snippet  # paraphrase mapped to the README line
    oversight = by_field["ai_system.human_oversight"]
    assert oversight.evidence_path == "README.md"
    assert "reviews every summary" in oversight.snippet
    retention = by_field["data.retention_policy"]
    assert retention.snippet == "zzzz qqqq"  # no matching doc line: the quote itself
    for finding in findings:
        assert finding.source == f"repo:{finding.evidence_path}"
        _assert_applies_to_record(finding)


def test_evidence_digest_contains_readme_manifest_and_signals(
    hr_screening_inventory: RepositoryInventory,
) -> None:
    signals = run_all_detectors(hr_screening_inventory)
    digest = build_evidence_digest(hr_screening_inventory, signals)
    assert "## README (README.md)" in digest
    assert "openai==1.51.0" in digest
    assert "## Code signals" in digest
    assert "ai_system.uses_ai = True" in digest
    assert "ghp_FAKE123" not in digest
    assert "docs/retention.md" in digest


async def test_summarize_hr_screening(hr_screening_inventory: RepositoryInventory) -> None:
    findings = await summarize_repository(
        hr_screening_inventory, run_all_detectors(hr_screening_inventory)
    )
    fields = [finding.field for finding in findings]
    assert len(fields) == len(set(fields)), "one finding per field"
    assert len(fields) >= 7
    by_field = {finding.field: finding for finding in findings}
    assert by_field["ai_system.uses_ai"].value is True
    assert by_field["ai_system.uses_ai"].evidence_path == "src/ranking/summarise.py"
    assert by_field["ai_system.model_providers"].value == ["openai"]
    assert by_field["data.processes_personal_data"].value is True
    assert by_field["use_case.domains"].value == ["hr_employment"]
    assert by_field["project.lifecycle_stage"].value == "production"
    assert by_field["project.deployment_regions"].value == ["eu"]
    assert by_field["data.retention_policy"].value == "under_1_year"
    assert "internal_db" in by_field["data.data_sources"].value  # type: ignore[operator]
    # Filled by the extraction pass, with README evidence.
    assert by_field["project.target_users"].value == "internal"
    assert by_field["project.target_users"].evidence_path == "README.md"
    assert by_field["ai_system.human_oversight"].value is True
    for finding in findings:
        assert finding.evidence_path
        assert finding.snippet
        assert finding.source == f"repo:{finding.evidence_path}"
        assert finding.label == QUESTIONS_BY_FIELD[finding.field].label
        assert finding.display_value == display_value(finding.field, finding.value)
        assert "ghp_FAKE123" not in finding.snippet
        _assert_applies_to_record(finding)


async def test_summarize_log_search(log_search_inventory: RepositoryInventory) -> None:
    findings = await summarize_repository(
        log_search_inventory, run_all_detectors(log_search_inventory)
    )
    by_field = {finding.field: finding for finding in findings}
    assert len(by_field) >= 5
    assert by_field["ai_system.uses_ai"].value is True
    assert by_field["data.processes_personal_data"].value is False
    assert by_field["data.data_sources"].value == ["logs"]
    assert by_field["use_case.domains"].value == ["other"]
    assert by_field["project.lifecycle_stage"].value == "pilot"
    assert "data.pii_categories" not in by_field
    for finding in findings:
        _assert_applies_to_record(finding)
