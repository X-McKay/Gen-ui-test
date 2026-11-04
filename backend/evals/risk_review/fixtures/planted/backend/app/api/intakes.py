"""Intake routes for the planted fixture."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.intake import store

logger = logging.getLogger(__name__)
router = APIRouter()


class CreateIntakeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_name: str
    description: str
    repository_url: str | None = None


@router.post("/intakes")
def create_intake(body: CreateIntakeRequest) -> dict[str, str]:
    intake_id = uuid.uuid4().hex
    logger.info("intake.create", extra={"intake_id": intake_id, "description": body.description})  # PLANTED LOG-01
    store.save(intake_id, body.model_dump())
    logger.info("intake.saved", extra={"intake_id": intake_id, "fields": 3})  # DECOY LOG-D2
    return {"intake_id": intake_id}


@router.get("/intakes/{intake_id}")
def get_intake(intake_id: str) -> dict[str, object]:
    record = store.load(intake_id)
    if record is None:
        raise HTTPException(status_code=404, detail="intake not found")
    return record


@router.post("/intakes/{intake_id}/analyze")
def analyze(intake_id: str, repository_url: str, token: str | None = None) -> dict[str, str]:
    from app.repo_analysis.clone_repository import clone

    try:
        clone(repository_url, token)
    except Exception as error:
        logger.error("repo.clone_failed", extra={"intake_id": intake_id})  # DECOY LOG-D3
        raise HTTPException(status_code=502, detail=f"clone failed: {error}") from error  # PLANTED LOG-02
    return {"status": "queued"}
