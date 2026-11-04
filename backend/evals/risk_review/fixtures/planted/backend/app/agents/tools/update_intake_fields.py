"""Update tool for the planted fixture: trusts model-supplied confirmation and tier."""

from __future__ import annotations

from app.intake.schema import IntakeRecord


def update_intake_fields(record: IntakeRecord, updates: list[dict[str, object]]) -> dict[str, int]:
    for update in updates:
        path = str(update.get("path"))
        record.set_field(
            path,
            update.get("value"),
            source="model",
            confidence=float(update.get("confidence", 0.5)),
            confirmed=bool(update.get("confirmed", False)),  # PLANTED MOD-01
        )
    return {"written": len(updates)}


def finalize_intake(record: IntakeRecord, tier: str | None = None) -> dict[str, object]:
    if tier is not None:
        record.assessment["tier"] = tier  # PLANTED MOD-02
    return {"tier": record.assessment.get("tier")}
