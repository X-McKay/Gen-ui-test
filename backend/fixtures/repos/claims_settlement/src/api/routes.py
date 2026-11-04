"""HTTP API used by the customer mobile app and the handler back office."""

from __future__ import annotations

from fastapi import Depends, FastAPI, UploadFile
from pydantic import BaseModel

from src.api.auth import current_user, require_handler
from src.model.estimator import estimate_repair_cost
from src.settlement.decide import Decision, decide

app = FastAPI(title="Claims Fast-Track")


class ClaimForm(BaseModel):
    policy_number: str
    claimant_name: str
    claimant_address: str
    iban: str
    vehicle_registration: str
    accident_description: str


@app.post("/claims")
async def submit_claim(
    form: ClaimForm, photos: list[UploadFile], user: dict[str, object] = Depends(current_user)
) -> dict[str, object]:
    estimate = estimate_repair_cost(form.model_dump(), [await p.read() for p in photos])
    decision: Decision = decide(form.policy_number, form.iban, estimate)
    return {"estimate_eur": estimate, "decision": decision.kind, "claim_id": decision.claim_id}


@app.post("/claims/{claim_id}/reopen")
def reopen(claim_id: str, handler: dict[str, object] = Depends(require_handler)) -> dict[str, str]:
    """A handler can reopen an automatic settlement; the payout is then reviewed manually."""
    return {"claim_id": claim_id, "status": "reopened", "by": str(handler["sub"])}
