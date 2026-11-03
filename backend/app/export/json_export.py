"""JSON export: the full record with provenance, tagged with the published schema URL."""

from __future__ import annotations

import json

from app.intake.schema import IntakeRecord

SCHEMA_URL = "https://intake.local/schema/intake.schema.json"


def export_record(record: IntakeRecord) -> dict[str, object]:
    """The complete record (every ``FieldMeta`` with confidence, source and confirmed).

    Nothing is dropped; the only addition is ``$schema`` pointing at the published
    ``schema/intake.schema.json`` so consumers can validate the document.
    """
    payload: dict[str, object] = {"$schema": SCHEMA_URL}
    payload.update(record.model_dump(mode="json"))
    return payload


def export_record_bytes(record: IntakeRecord) -> bytes:
    """UTF-8 JSON, two-space indent, trailing newline (stable for diffs and attachments)."""
    text = json.dumps(export_record(record), indent=2, ensure_ascii=False)
    return (text + "\n").encode("utf-8")
