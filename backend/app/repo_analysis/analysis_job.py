"""In-process job runner for repository analysis.

``start_analysis`` schedules the pipeline on the running event loop and returns a job id;
``subscribe`` yields the job's events (buffered, so late subscribers replay everything).
Blocking work (clone, inventory, detectors) runs in a worker thread; the record is updated
on the event loop. Finished jobs are kept for :data:`JOB_RETENTION_SECONDS`.

Event payloads (also the SSE ``data`` of :mod:`app.api.repositories`)::

    {"type": "progress", "text": "Scanning 412 files…"}
    {"type": "done", "findings_count": 9, "intake_id": "abc123"}
    {"type": "error", "message": "Host example.com is not allowed. Allowed: github.com"}
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.intake import record_service
from app.intake.record_service import FieldUpdate, IntakeNotFoundError
from app.intake.schema import IntakeRecord
from app.repo_analysis import findings_store
from app.repo_analysis.clone_repository import (
    RepositoryCloneError,
    RepositoryUrlError,
    clone_repository,
    redact_secrets,
    remove_clone,
    validate_repository_url,
)
from app.repo_analysis.inventory import RepositoryInventory, build_inventory
from app.repo_analysis.signal_detectors import (
    count_model_integrations,
    run_all_detectors,
)
from app.repo_analysis.summarize_findings import RepositoryFinding, summarize_repository
from app.settings import get_settings

logger = logging.getLogger(__name__)

JOB_RETENTION_SECONDS = 600.0

EventType = Literal["progress", "done", "error"]


class AnalysisEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: EventType
    text: str | None = None
    message: str | None = None
    findings_count: int | None = None
    intake_id: str | None = None

    @classmethod
    def progress(cls, text: str) -> AnalysisEvent:
        return cls(type="progress", text=text)

    @classmethod
    def done(cls, findings_count: int, intake_id: str) -> AnalysisEvent:
        return cls(type="done", findings_count=findings_count, intake_id=intake_id)

    @classmethod
    def error(cls, message: str) -> AnalysisEvent:
        return cls(type="error", message=message)

    def payload(self) -> dict[str, object]:
        """The wire shape: only the keys that belong to this event type."""
        if self.type == "progress":
            return {"type": "progress", "text": self.text or ""}
        if self.type == "done":
            return {
                "type": "done",
                "findings_count": self.findings_count or 0,
                "intake_id": self.intake_id or "",
            }
        return {"type": "error", "message": self.message or "Analysis failed."}


class JobNotFoundError(LookupError):
    pass


@dataclass
class AnalysisJob:
    job_id: str
    intake_id: str
    repo_url: str
    events: list[AnalysisEvent] = field(default_factory=list)
    finished: bool = False
    finished_at: float | None = None
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)
    task: asyncio.Task[None] | None = None

    @property
    def findings_count(self) -> int:
        for event in self.events:
            if event.type == "done":
                return event.findings_count or 0
        return 0


_jobs: dict[str, AnalysisJob] = {}


def _purge_finished(now: float | None = None) -> None:
    current = time.monotonic() if now is None else now
    expired = [
        job_id
        for job_id, job in _jobs.items()
        if job.finished
        and job.finished_at is not None
        and current - job.finished_at > JOB_RETENTION_SECONDS
    ]
    for job_id in expired:
        del _jobs[job_id]


def get_job(job_id: str) -> AnalysisJob | None:
    _purge_finished()
    return _jobs.get(job_id)


def forget_all_jobs() -> None:
    """Testing seam."""
    _jobs.clear()


async def _emit(job: AnalysisJob, event: AnalysisEvent) -> None:
    async with job.condition:
        job.events.append(event)
        if event.type in {"done", "error"}:
            job.finished = True
            job.finished_at = time.monotonic()
        job.condition.notify_all()


def start_analysis(intake_id: str, repo_url: str, access_token: str | None = None) -> str:
    """Schedule the analysis on the running loop and return the job id."""
    _purge_finished()
    job = AnalysisJob(job_id=uuid.uuid4().hex[:12], intake_id=intake_id, repo_url=repo_url)
    _jobs[job.job_id] = job
    loop = asyncio.get_running_loop()
    job.task = loop.create_task(_run_job(job, access_token), name=f"repo-analysis-{job.job_id}")
    return job.job_id


async def subscribe(job_id: str) -> AsyncIterator[AnalysisEvent]:
    """Replay buffered events, then stream new ones until the job finishes."""
    job = get_job(job_id)
    if job is None:
        raise JobNotFoundError(job_id)
    index = 0
    while True:
        async with job.condition:
            while index >= len(job.events) and not job.finished:
                await job.condition.wait()
            pending = job.events[index:]
            index = len(job.events)
            finished = job.finished and index >= len(job.events)
        for event in pending:
            yield event
        if finished:
            return


async def wait_for_job(job_id: str) -> list[AnalysisEvent]:
    """Collect every event of a job (used by tests and by the agent handoff)."""
    return [event async for event in subscribe(job_id)]


# --- the pipeline --------------------------------------------------------------------------


def _clone_only(url: str, token: str | None, workspace: Path) -> Path:
    settings = get_settings()
    cloned = clone_repository(
        url,
        token,
        timeout_s=settings.repo_clone_timeout_s,
        max_size_mb=settings.repo_max_size_mb,
        destination=workspace / "repo",
    )
    return cloned.path


def _scan(path: Path) -> RepositoryInventory:
    return build_inventory(path, max_files=get_settings().repo_max_files)


def _field_updates(findings: list[RepositoryFinding]) -> list[FieldUpdate]:
    return [
        FieldUpdate(
            path=finding.field,
            value=finding.value,
            source=finding.source,
            confidence=finding.confidence,
            confirmed=False,
        )
        for finding in findings
    ]


async def _progress(job: AnalysisJob, record: IntakeRecord | None, text: str) -> None:
    await _emit(job, AnalysisEvent.progress(text))
    if record is not None:
        await asyncio.to_thread(record_service.set_progress, record, text)


async def _run_job(job: AnalysisJob, access_token: str | None) -> None:
    settings = get_settings()
    record: IntakeRecord | None = None
    workspace: Path | None = None
    token = access_token or settings.repo_access_token
    secrets = [token] if token else []
    try:
        await _progress(job, None, "Validating repository URL")
        parsed = validate_repository_url(job.repo_url, settings.repo_allowed_hosts)
        loaded = await asyncio.to_thread(record_service.get_record, job.intake_id)
        record = loaded
        loaded.meta.repo_url = parsed.url
        await _progress(job, loaded, f"Cloning {parsed.display_name} (shallow)…")

        workspace = Path(tempfile.mkdtemp(prefix="intake-repo-"))
        clone_path = await asyncio.to_thread(_clone_only, parsed.url, token, workspace)
        await _progress(job, record, "Scanning repository files…")
        inventory = await asyncio.to_thread(_scan, clone_path)
        await _progress(job, record, f"Scanning {inventory.file_count} files…")
        signals = await asyncio.to_thread(run_all_detectors, inventory)
        integrations = count_model_integrations(signals)
        noun = "model integration" if integrations == 1 else "model integrations"
        await _progress(job, record, f"Found {integrations} {noun}")
        await _progress(job, record, "Mapping evidence onto the intake record")

        findings = await summarize_repository(inventory, signals)
        loaded, applied, rejected = await asyncio.to_thread(
            record_service.apply_updates,
            loaded,
            _field_updates(findings),
            policy="inferred",
        )
        record = loaded
        if rejected:
            logger.warning(
                "repo_analysis.updates_rejected",
                extra={"intake_id": job.intake_id, "rejected": len(rejected)},
            )
        await asyncio.to_thread(findings_store.save_findings, job.intake_id, findings)
        await asyncio.to_thread(record_service.set_progress, loaded, None)
        logger.info(
            "repo_analysis.completed",
            extra={
                "intake_id": job.intake_id,
                "findings": len(findings),
                "applied": len(applied),
                "files": inventory.file_count,
            },
        )
        await _emit(job, AnalysisEvent.done(len(findings), job.intake_id))
    except RepositoryUrlError as error:
        await _fail(job, record, str(error))
    except RepositoryCloneError as error:
        await _fail(job, record, redact_secrets(str(error), secrets))
    except IntakeNotFoundError:
        await _fail(job, None, f"Intake {job.intake_id} was not found.")
    except asyncio.CancelledError:
        await _fail(job, record, "Analysis was cancelled.")
        raise
    except Exception as error:
        logger.exception("repo_analysis.failed", extra={"intake_id": job.intake_id})
        await _fail(job, record, f"Analysis failed: {redact_secrets(str(error), secrets)}")
    finally:
        if workspace is not None:
            await asyncio.to_thread(_cleanup, workspace)


async def _fail(job: AnalysisJob, record: IntakeRecord | None, message: str) -> None:
    if record is not None:
        try:
            await asyncio.to_thread(record_service.set_progress, record, None)
        except Exception:
            logger.warning("repo_analysis.progress_reset_failed", exc_info=True)
    await _emit(job, AnalysisEvent.error(message))


def _cleanup(workspace: Path) -> None:
    try:
        remove_clone(workspace)
    except OSError:
        shutil.rmtree(workspace, ignore_errors=True)
