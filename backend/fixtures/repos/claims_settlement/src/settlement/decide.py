"""Threshold rule: pay automatically below the limit, otherwise open a handler task."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

import httpx

AUTO_SETTLE_LIMIT_EUR = float(os.environ.get("AUTO_SETTLE_LIMIT_EUR", "2000"))
PAYMENTS_URL = "https://payments.internal.example-insurance.com/payouts"


@dataclass(frozen=True)
class Decision:
    claim_id: str
    kind: str  # "auto_settled" | "handler_review"


def decide(policy_number: str, iban: str, estimate_eur: float) -> Decision:
    claim_id = uuid.uuid4().hex
    if estimate_eur < AUTO_SETTLE_LIMIT_EUR:
        httpx.post(
            PAYMENTS_URL,
            json={"policy": policy_number, "iban": iban, "amount_eur": round(estimate_eur, 2)},
            headers={"X-Api-Key": os.environ["PAYMENTS_API_KEY"]},
            timeout=10,
        )
        return Decision(claim_id, "auto_settled")
    return Decision(claim_id, "handler_review")
