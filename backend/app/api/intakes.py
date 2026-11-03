"""REST routes for intakes: create, read, inline edit, defaults."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.intake import repository
from app.intake.record_service import (
    FieldUpdate,
    IntakeNotFoundError,
    apply_updates,
    create_intake,
    get_record,
)
from app.intake.schema import IntakeMode, IntakeRecord
from app.settings import get_settings

router = APIRouter()

SSO_HEADERS = ("x-forwarded-user", "x-forwarded-email", "x-auth-request-email")


def owner_from_request(request: Request) -> str | None:
    for header in SSO_HEADERS:
        value = request.headers.get(header)
        if value:
            return value
    return get_settings().default_owner


class CreateIntakeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: IntakeMode = IntakeMode.NEW
    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=20000)
    owner: str | None = Field(default=None, max_length=200)
    repo_url: str | None = Field(default=None, max_length=500)


class IntakeResponse(BaseModel):
    record: IntakeRecord
    current_step: dict[str, Any] | None


class FieldUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    value: Any


class UpdateFieldsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    updates: list[FieldUpdateRequest] = Field(min_length=1, max_length=50)


@router.get("/intakes/defaults")
async def intake_defaults(request: Request) -> dict[str, str | None]:
    return {"owner": owner_from_request(request)}


@router.post("/intakes", status_code=201)
async def create(body: CreateIntakeRequest, request: Request) -> IntakeRecord:
    owner = body.owner or owner_from_request(request)
    record = create_intake(body.mode, owner=None, repo_url=body.repo_url)
    updates: list[FieldUpdate] = []
    if owner:
        updates.append(
            FieldUpdate(
                path="project.owner",
                value=owner,
                source="user" if body.owner else "inferred",
                confidence=1.0 if body.owner else 0.9,
                confirmed=bool(body.owner),
            )
        )
    if body.name:
        updates.append(FieldUpdate(path="project.name", value=body.name.strip()))
    if body.description:
        updates.append(FieldUpdate(path="project.description", value=body.description.strip()))
    if updates:
        record, _, _ = apply_updates(record, updates, policy="user")
    return record


@router.get("/intakes/{intake_id}")
async def read(intake_id: str) -> IntakeResponse:
    try:
        record = get_record(intake_id)
    except IntakeNotFoundError:
        raise HTTPException(status_code=404, detail="Intake not found") from None
    return IntakeResponse(record=record, current_step=repository.load_current_step(intake_id))


@router.patch("/intakes/{intake_id}/fields")
async def update_fields(intake_id: str, body: UpdateFieldsRequest) -> IntakeRecord:
    try:
        record = get_record(intake_id)
    except IntakeNotFoundError:
        raise HTTPException(status_code=404, detail="Intake not found") from None
    if record.meta.status.value == "submitted":
        raise HTTPException(status_code=409, detail="A submitted intake cannot be edited")
    updates = [FieldUpdate(path=item.path, value=item.value) for item in body.updates]
    record, applied, rejected = apply_updates(record, updates, policy="user")
    if rejected and not applied:
        raise HTTPException(status_code=422, detail="; ".join(rejected))
    return record
