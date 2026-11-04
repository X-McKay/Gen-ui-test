"""Extraction tool for the planted fixture: model values stay unconfirmed."""

from __future__ import annotations

from app.intake.schema import IntakeRecord


def extract_intake_facts(record: IntakeRecord, facts: list[dict[str, object]]) -> dict[str, int]:
    for fact in facts:
        path = str(fact.get("path"))
        if path.startswith("assessment."):
            continue  # DECOY MOD-D1: assessment paths are refused
        record.set_field(
            path,
            fact.get("value"),
            source="model",
            confidence=float(fact.get("confidence", 0.5)),
            confirmed=False,  # DECOY MOD-D2
        )
    return {"written": len(facts)}
