"""Schema invariants and the exported JSON schema."""

from __future__ import annotations

import json
from pathlib import Path

from app.intake.question_bank import QUESTION_BANK
from app.intake.schema import IntakeRecord, field_paths, new_record

ROOT = Path(__file__).resolve().parents[3]


def test_every_question_maps_to_a_record_field() -> None:
    paths = set(field_paths())
    for spec in QUESTION_BANK:
        assert spec.field in paths, spec.field


def test_every_required_record_field_has_a_question_or_is_meta() -> None:
    asked = {spec.field for spec in QUESTION_BANK}
    missing = sorted(set(field_paths()) - asked)
    assert missing == [], f"fields without a question: {missing}"


def test_exported_schema_is_fresh() -> None:
    import sys

    sys.path.insert(0, str(ROOT / "backend"))
    from scripts.export_schema import render

    target = ROOT / "schema" / "intake.schema.json"
    assert target.read_text() == render(), "run `make export-schema`"


def test_record_round_trips_and_every_leaf_carries_provenance() -> None:
    record = new_record("abc")
    record.set_field(
        "data.special_category_data",
        ["health"],
        source="repo:src/x.py",
        confidence=0.7,
        confirmed=False,
    )
    data = json.loads(record.model_dump_json())
    restored = IntakeRecord.model_validate(data)
    assert restored == record
    for path, field in restored.iter_fields():
        assert {"value", "confidence", "source", "confirmed"} <= set(field.model_dump()), path
