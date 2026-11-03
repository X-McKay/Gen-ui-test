"""Export and submit endpoints: JSON (with provenance), PDF form, HTML preview, webhook submit."""

from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool

from app.export.json_export import export_record_bytes
from app.export.pdf_export import export_pdf_bytes, render_form_html
from app.export.webhook import WebhookDeliveryError, deliver_webhook
from app.intake.record_service import IntakeNotFoundError, get_record, mark_submitted
from app.intake.schema import IntakeRecord
from app.settings import get_settings

router = APIRouter(tags=["exports"])

NOT_FOUND_DETAIL = "Intake not found"
_UNSAFE_FILENAME_CHARACTERS = re.compile(r"[^A-Za-z0-9._-]")


class SubmitResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["submitted"] = "submitted"
    delivered: bool
    message: str


def load_record_or_404(intake_id: str) -> IntakeRecord:
    try:
        return get_record(intake_id)
    except IntakeNotFoundError as error:
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL) from error


def attachment_headers(intake_id: str, extension: str) -> dict[str, str]:
    safe_id = _UNSAFE_FILENAME_CHARACTERS.sub("_", intake_id) or "intake"
    return {"Content-Disposition": f'attachment; filename="intake-{safe_id}.{extension}"'}


@router.get("/intakes/{intake_id}/export.json", response_class=Response)
def download_json_export(intake_id: str) -> Response:
    record = load_record_or_404(intake_id)
    return Response(
        content=export_record_bytes(record),
        media_type="application/json",
        headers=attachment_headers(record.meta.intake_id, "json"),
    )


@router.get("/intakes/{intake_id}/export.pdf", response_class=Response)
def download_pdf_export(intake_id: str) -> Response:
    record = load_record_or_404(intake_id)
    return Response(
        content=export_pdf_bytes(record),
        media_type="application/pdf",
        headers=attachment_headers(record.meta.intake_id, "pdf"),
    )


@router.get("/intakes/{intake_id}/form.html", response_class=HTMLResponse)
def preview_form_html(intake_id: str) -> HTMLResponse:
    record = load_record_or_404(intake_id)
    return HTMLResponse(content=render_form_html(record))


@router.post("/intakes/{intake_id}/submit", response_model=SubmitResponse)
async def submit_intake(intake_id: str) -> SubmitResponse:
    record = await run_in_threadpool(load_record_or_404, intake_id)
    webhook_url = get_settings().intake_webhook_url
    if not webhook_url:
        await run_in_threadpool(mark_submitted, record)
        return SubmitResponse(
            delivered=False,
            message="No webhook configured; the intake is marked submitted locally",
        )
    try:
        await deliver_webhook(webhook_url, export_record_bytes(record))
    except WebhookDeliveryError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    await run_in_threadpool(mark_submitted, record)
    return SubmitResponse(delivered=True, message="Sent to the governance team")
