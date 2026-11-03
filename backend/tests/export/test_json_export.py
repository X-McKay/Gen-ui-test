"""The JSON export is the full record with provenance and validates against the schema."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from app.export.json_export import SCHEMA_URL, export_record, export_record_bytes
from app.intake.schema import IntakeRecord


def load_validator(schema_path: Path) -> Draft202012Validator:
    schema = json.loads(schema_path.read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def without_schema_pointer(payload: dict[str, object]) -> dict[str, object]:
    """The generated schema forbids additional top-level keys, so strip the pointer."""
    return {key: value for key, value in payload.items() if key != "$schema"}


def test_export_validates_against_schema(high_risk_record: IntakeRecord, schema_path: Path) -> None:
    validator = load_validator(schema_path)
    payload = export_record(high_risk_record)
    errors = sorted(validator.iter_errors(without_schema_pointer(payload)), key=str)
    assert errors == [], [error.message for error in errors]


def test_empty_record_validates_against_schema(
    empty_record: IntakeRecord, schema_path: Path
) -> None:
    validator = load_validator(schema_path)
    payload = export_record(empty_record)
    errors = list(validator.iter_errors(without_schema_pointer(payload)))
    assert errors == [], [error.message for error in errors]


def test_export_has_schema_pointer_first(high_risk_record: IntakeRecord) -> None:
    payload = export_record(high_risk_record)
    assert next(iter(payload)) == "$schema"
    assert payload["$schema"] == SCHEMA_URL
    assert set(payload) == {
        "$schema",
        "meta",
        "project",
        "ai_system",
        "data",
        "use_case",
        "assessment",
    }


def test_export_keeps_provenance(high_risk_record: IntakeRecord) -> None:
    payload = export_record(high_risk_record)
    ai_system = payload["ai_system"]
    assert isinstance(ai_system, dict)
    uses_ai = ai_system["uses_ai"]
    assert uses_ai == {
        "value": True,
        "confidence": 0.95,
        "source": "repo:requirements.txt",
        "confirmed": True,
    }
    data = payload["data"]
    assert isinstance(data, dict)
    assert data["special_category_data"]["value"] == "unknown"
    assert data["retention_policy"]["value"] is None
    assessment = payload["assessment"]
    assert isinstance(assessment, dict)
    assert assessment["eu_ai_act"]["classification"] == "high_risk"
    assert assessment["open_questions"] == ["data.special_category_data"]


def test_export_matches_model_dump(high_risk_record: IntakeRecord) -> None:
    payload = export_record(high_risk_record)
    assert without_schema_pointer(payload) == high_risk_record.model_dump(mode="json")


def test_export_bytes_are_pretty_utf8_with_trailing_newline(
    high_risk_record: IntakeRecord,
) -> None:
    raw = export_record_bytes(high_risk_record)
    assert raw.startswith(b'{\n  "$schema": ')
    assert raw.endswith(b"}\n")
    text = raw.decode("utf-8")
    assert json.loads(text) == export_record(high_risk_record)
    assert IntakeRecord.model_validate(without_schema_pointer(json.loads(text)))
