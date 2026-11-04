"""Pluggable framework modules evaluated after the EU AI Act table.

Add a module here and it takes part in :func:`app.governance.classify.classify`. Order is
the order of ``applicable_frameworks`` and ``obligations`` in the assessment.
"""

from __future__ import annotations

from app.governance.frameworks import (
    gdpr,
    internal_policy,
    iso_42001,
    mifid_algorithmic_trading,
    nist_ai_rmf,
)
from app.governance.frameworks.base import NOT_APPLICABLE, FrameworkModule, FrameworkResult

FRAMEWORK_MODULES: list[FrameworkModule] = [
    gdpr,
    nist_ai_rmf,
    iso_42001,
    mifid_algorithmic_trading,
    internal_policy,
]

__all__ = [
    "FRAMEWORK_MODULES",
    "NOT_APPLICABLE",
    "FrameworkModule",
    "FrameworkResult",
]
