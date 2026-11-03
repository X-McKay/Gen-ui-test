"""Read intake field values the way the rules engine needs them.

Every leaf of an :class:`~app.intake.schema.IntakeRecord` may hold ``None`` (not captured) or
the literal ``"unknown"`` (the user is not sure). Neither counts as ``True`` *or* ``False``:
a rule that needs a positive answer only fires on ``True``, and a rule that needs a negative
answer only fires on ``False``. Lists are treated as empty unless an actual list is stored.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.intake.schema import UNKNOWN, IntakeRecord


def is_asserted(record: IntakeRecord, path: str) -> bool:
    """True when the field holds a real value (not ``None`` and not ``"unknown"``)."""
    value = record.value_of(path)
    return value is not None and value != UNKNOWN


def is_true(record: IntakeRecord, path: str) -> bool:
    """True only for a stored boolean ``True``."""
    return record.value_of(path) is True


def is_false(record: IntakeRecord, path: str) -> bool:
    """True only for a stored boolean ``False``."""
    return record.value_of(path) is False


def equals(record: IntakeRecord, path: str, expected: object) -> bool:
    """True when an asserted value equals ``expected`` (``"unknown"`` never matches)."""
    value = record.value_of(path)
    return value is not None and value != UNKNOWN and value == expected


def list_value(record: IntakeRecord, path: str) -> list[object]:
    """The stored list, or ``[]`` when nothing, ``"unknown"`` or a scalar is stored."""
    value = record.value_of(path)
    return list(value) if isinstance(value, list) else []


def matching_items(record: IntakeRecord, path: str, candidates: Iterable[object]) -> list[object]:
    """Items of the stored list that are among ``candidates``, in stored order."""
    wanted = set(candidates)
    return [item for item in list_value(record, path) if item in wanted]


def contains_any(record: IntakeRecord, path: str, candidates: Iterable[object]) -> bool:
    return bool(matching_items(record, path, candidates))
