"""In-memory store for the planted fixture."""

from __future__ import annotations

_RECORDS: dict[str, dict[str, object]] = {}


def save(intake_id: str, record: dict[str, object]) -> None:
    _RECORDS[intake_id] = record


def load(intake_id: str) -> dict[str, object] | None:
    return _RECORDS.get(intake_id)
