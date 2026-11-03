"""Aggregates the framework modules into ``record.assessment``.

PLACEHOLDER: replaced by the governance implementation. Keep the public signature.
"""

from __future__ import annotations

from app.intake.gap_analysis import open_questions
from app.intake.schema import Assessment, IntakeRecord


def classify(record: IntakeRecord) -> Assessment:
    return Assessment(open_questions=open_questions(record))


def reclassify(record: IntakeRecord) -> IntakeRecord:
    """Recompute ``assessment`` in place and return the record."""
    record.assessment = classify(record)
    return record
