"""Shared types for the pluggable framework modules.

A framework module is any object (in practice a Python module) with a ``name`` and an
``evaluate(record, eu)`` function. Modules are pure: they read the record and the EU AI Act
assessment and return a :class:`FrameworkResult`; they never persist or import I/O code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.intake.schema import EuAiActAssessment, IntakeRecord, Obligation, RiskTier


@dataclass(frozen=True)
class FrameworkResult:
    """What one framework contributes to the overall assessment."""

    applies: bool
    obligations: list[Obligation] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    tier_floor: RiskTier | None = None
    # Extra framework names the module brings into scope (for example a local privacy law
    # that rides on the GDPR module). Listed after the module's own name.
    additional_frameworks: list[str] = field(default_factory=list)


NOT_APPLICABLE = FrameworkResult(applies=False)


class FrameworkModule(Protocol):
    name: str

    def evaluate(self, record: IntakeRecord, eu: EuAiActAssessment) -> FrameworkResult: ...
