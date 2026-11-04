"""MiFID II algorithmic trading module (Directive 2014/65/EU Art. 17, RTS 6, DORA).

Applies when the system trades in financial instruments and determines orders itself: the
domain is ``financial_markets`` and the autonomy level is ``decides`` (MiFID II Art. 4(1)(39):
a computer algorithm automatically determines order parameters with limited or no human
intervention). A model that only proposes trades a person then places is not algorithmic
trading and the module stays silent; the risk tables still score it through the transactions
and exposure facts.
"""

from __future__ import annotations

from app.governance.field_values import contains_any, equals, is_true
from app.governance.frameworks.base import NOT_APPLICABLE, FrameworkResult
from app.intake.schema import (
    AutonomyLevel,
    Domain,
    EuAiActAssessment,
    IntakeRecord,
    Obligation,
    RiskTier,
)

name = "MiFID II algorithmic trading"
DORA = "DORA"

DOMAINS = "use_case.domains"
AUTONOMY_LEVEL = "ai_system.autonomy_level"
HUMAN_OVERSIGHT = "ai_system.human_oversight"


def _obligation(text: str, reference: str, framework: str = name) -> Obligation:
    return Obligation(framework=framework, text=text, reference=reference, role=None)


def applies_to(record: IntakeRecord) -> bool:
    return contains_any(record, DOMAINS, {Domain.FINANCIAL_MARKETS}) and equals(
        record, AUTONOMY_LEVEL, AutonomyLevel.DECIDES
    )


def evaluate(record: IntakeRecord, eu: EuAiActAssessment) -> FrameworkResult:
    if not applies_to(record):
        return NOT_APPLICABLE
    obligations = [
        _obligation(
            "Enforce pre-trade limits (price collars, maximum order value and volume, "
            "position and loss limits) that block erroneous orders before they reach a venue",
            "MiFID II Art. 17(1); RTS 6 Art. 15",
        ),
        _obligation(
            "Provide kill functionality that cancels all unexecuted orders and halts the "
            "algorithm immediately",
            "RTS 6 Art. 12",
        ),
        _obligation(
            "Test the algorithm against venue conformance and in a non-live environment before "
            "deployment and before every material change; keep the test records",
            "MiFID II Art. 17(1); RTS 6 Art. 5-7",
        ),
        _obligation(
            "Monitor live trading in real time with alerts, and keep accurate, time-sequenced "
            "order records for five years",
            "MiFID II Art. 17(2); RTS 6 Art. 16",
        ),
        _obligation(
            "Notify the home competent authority and the venues that the firm engages in "
            "algorithmic trading, and provide the algorithm description on request",
            "MiFID II Art. 17(2)",
        ),
        _obligation(
            "Run and document an annual self-assessment and validation of the trading system "
            "and its risk controls",
            "RTS 6 Art. 9",
        ),
        _obligation(
            "Treat the trading system as critical ICT: resilience testing and major-incident "
            "reporting under DORA",
            "DORA Art. 17, 19, 24",
            DORA,
        ),
    ]
    next_steps = [
        "Confirm the pre-trade limits and kill functionality with the risk function before go-live",
    ]
    if not is_true(record, HUMAN_OVERSIGHT):
        next_steps.append("Name the trading-desk owner who monitors the algorithm in real time")
    return FrameworkResult(
        applies=True,
        obligations=obligations,
        next_steps=next_steps,
        tier_floor=RiskTier.HIGH,
        additional_frameworks=[DORA],
    )
