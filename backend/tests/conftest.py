"""Shared fixtures."""

from __future__ import annotations

from collections.abc import Callable, Mapping

import pytest

from app.intake.schema import IntakeRecord, new_record

RecordFactory = Callable[..., IntakeRecord]


@pytest.fixture
def make_record() -> RecordFactory:
    """Build a record with the given ``path -> value`` pairs set as confirmed user answers."""

    def factory(values: Mapping[str, object] | None = None, intake_id: str = "t") -> IntakeRecord:
        record = new_record(intake_id)
        for path, value in (values or {}).items():
            record.set_field(path, value, source="user", confidence=1.0, confirmed=True)
        return record

    return factory
