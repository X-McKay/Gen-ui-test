"""Repository analysis endpoints: start a job, stream its progress, read the findings."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sse_starlette.sse import EventSourceResponse

from app.intake import record_service
from app.intake.record_service import IntakeNotFoundError
from app.repo_analysis import analysis_job, findings_store
from app.repo_analysis.clone_repository import RepositoryUrlError, validate_repository_url
from app.repo_analysis.summarize_findings import RepositoryFinding
from app.settings import get_settings

router = APIRouter(tags=["repositories"])


class AnalyzeRepositoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intake_id: str = Field(min_length=1)
    repo_url: str = Field(min_length=1, max_length=2048)
    access_token: str | None = Field(default=None, max_length=512)


class AnalyzeRepositoryResponse(BaseModel):
    job_id: str


class RepositoryFindingDto(BaseModel):
    """Mirror of ``RepositoryFindingDto`` in ``frontend/lib/apiClient.ts``."""

    field: str
    label: str
    value: object
    display_value: str
    confidence: float
    evidence_path: str
    snippet: str

    @classmethod
    def from_finding(cls, finding: RepositoryFinding) -> RepositoryFindingDto:
        return cls(
            field=finding.field,
            label=finding.label,
            value=finding.value,
            display_value=finding.display_value,
            confidence=finding.confidence,
            evidence_path=finding.evidence_path,
            snippet=finding.snippet,
        )


@router.post("/repositories/analyze", response_model=AnalyzeRepositoryResponse)
async def analyze_repository(body: AnalyzeRepositoryRequest) -> AnalyzeRepositoryResponse:
    settings = get_settings()
    try:
        parsed = validate_repository_url(body.repo_url, settings.repo_allowed_hosts)
    except RepositoryUrlError as error:
        raise HTTPException(status_code=400, detail=str(error)) from None
    try:
        record_service.get_record(body.intake_id)
    except IntakeNotFoundError:
        raise HTTPException(status_code=404, detail="Intake not found.") from None
    token = body.access_token.strip() if body.access_token else None
    job_id = analysis_job.start_analysis(body.intake_id, parsed.url, token or None)
    return AnalyzeRepositoryResponse(job_id=job_id)


async def _event_stream(job_id: str) -> AsyncIterator[dict[str, str]]:
    async for event in analysis_job.subscribe(job_id):
        yield {"event": event.type, "data": json.dumps(event.payload())}


@router.get("/repositories/analyze/{job_id}/events")
async def analysis_events(job_id: str) -> EventSourceResponse:
    if analysis_job.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="Analysis job not found.")
    return EventSourceResponse(_event_stream(job_id))


@router.get("/intakes/{intake_id}/findings", response_model=list[RepositoryFindingDto])
async def get_findings(intake_id: str) -> list[RepositoryFindingDto]:
    try:
        record_service.get_record(intake_id)
    except IntakeNotFoundError:
        raise HTTPException(status_code=404, detail="Intake not found.") from None
    findings = findings_store.load_findings(intake_id)
    return [RepositoryFindingDto.from_finding(finding) for finding in findings]
