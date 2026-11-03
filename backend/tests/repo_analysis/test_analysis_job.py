from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from fastapi import FastAPI

from app.api.repositories import router
from app.intake import record_service
from app.intake.schema import IntakeMode
from app.repo_analysis import analysis_job, findings_store
from app.repo_analysis.analysis_job import (
    AnalysisEvent,
    JobNotFoundError,
    start_analysis,
    subscribe,
    wait_for_job,
)

HR_SCREENING_URL = "https://github.com/intake-fixtures/hr-screening"
LOG_SEARCH_URL = "https://github.com/intake-fixtures/log-search"


@pytest.fixture(autouse=True)
def clear_jobs() -> None:
    analysis_job.forget_all_jobs()


def _new_intake() -> str:
    record = record_service.create_intake(IntakeMode.EXISTING)
    return record.meta.intake_id


def test_event_payloads() -> None:
    assert AnalysisEvent.progress("Cloning").payload() == {"type": "progress", "text": "Cloning"}
    assert AnalysisEvent.done(3, "abc").payload() == {
        "type": "done",
        "findings_count": 3,
        "intake_id": "abc",
    }
    assert AnalysisEvent.error("nope").payload() == {"type": "error", "message": "nope"}


async def test_job_end_to_end_in_mock_mode() -> None:
    intake_id = _new_intake()
    job_id = start_analysis(intake_id, HR_SCREENING_URL, None)
    events = await asyncio.wait_for(wait_for_job(job_id), timeout=60)

    types = [event.type for event in events]
    assert types[0] == "progress"
    assert types[-1] == "done"
    assert "error" not in types
    texts = [event.text for event in events if event.type == "progress"]
    assert texts[0] == "Validating repository URL"
    assert any(text.startswith("Cloning intake-fixtures/hr-screening") for text in texts)  # type: ignore[union-attr]
    assert any(text == "Scanning 16 files…" for text in texts)
    assert "Found 1 model integration" in texts
    assert "Mapping evidence onto the intake record" in texts
    done = events[-1]
    assert done.intake_id == intake_id
    assert done.findings_count is not None and done.findings_count >= 5

    findings = findings_store.load_findings(intake_id)
    assert len(findings) == done.findings_count
    assert len(findings) >= 5

    record = record_service.get_record(intake_id)
    assert record.meta.repo_url == HR_SCREENING_URL
    assert record.meta.analysis_progress is None
    populated = {
        path: field
        for path, field in record.iter_fields()
        if field.is_set and field.source.startswith("repo:")
    }
    assert len(populated) >= 5
    assert populated["ai_system.uses_ai"].value is True
    assert populated["ai_system.uses_ai"].source == "repo:src/ranking/summarise.py"
    assert populated["ai_system.uses_ai"].confirmed is False
    assert populated["use_case.domains"].value == ["hr_employment"]
    assert populated["data.processes_personal_data"].value is True
    for field in populated.values():
        assert 0.0 < field.confidence <= 1.0


async def test_job_does_not_overwrite_user_confirmed_values() -> None:
    intake_id = _new_intake()
    record = record_service.get_record(intake_id)
    record_service.apply_updates(
        record,
        [record_service.FieldUpdate(path="project.lifecycle_stage", value="idea")],
        policy="user",
    )
    job_id = start_analysis(intake_id, LOG_SEARCH_URL, None)
    events = await asyncio.wait_for(wait_for_job(job_id), timeout=60)
    assert events[-1].type == "done"
    record = record_service.get_record(intake_id)
    assert record.value_of("project.lifecycle_stage") == "idea"
    assert record.get_field("project.lifecycle_stage").source == "user"
    assert record.get_field("ai_system.uses_ai").source.startswith("repo:")


async def test_late_subscriber_replays_buffered_events() -> None:
    intake_id = _new_intake()
    job_id = start_analysis(intake_id, LOG_SEARCH_URL, None)
    first = await asyncio.wait_for(wait_for_job(job_id), timeout=60)
    second = await asyncio.wait_for(wait_for_job(job_id), timeout=5)
    assert [event.payload() for event in first] == [event.payload() for event in second]
    assert second[-1].type == "done"


async def test_two_subscribers_see_the_same_stream() -> None:
    intake_id = _new_intake()
    job_id = start_analysis(intake_id, LOG_SEARCH_URL, None)
    first, second = await asyncio.wait_for(
        asyncio.gather(wait_for_job(job_id), wait_for_job(job_id)), timeout=60
    )
    assert [event.type for event in first] == [event.type for event in second]


async def test_disallowed_host_yields_error_event() -> None:
    intake_id = _new_intake()
    job_id = start_analysis(intake_id, "https://example.com/acme/widgets", None)
    events = await asyncio.wait_for(wait_for_job(job_id), timeout=10)
    assert events[-1].type == "error"
    assert events[-1].message is not None
    assert events[-1].message.startswith("Host example.com is not allowed")
    assert findings_store.load_findings(intake_id) == []


async def test_unknown_intake_yields_error_event() -> None:
    job_id = start_analysis("does-not-exist", LOG_SEARCH_URL, None)
    events = await asyncio.wait_for(wait_for_job(job_id), timeout=10)
    assert events[-1].type == "error"
    assert "does-not-exist" in (events[-1].message or "")


async def test_subscribe_unknown_job() -> None:
    with pytest.raises(JobNotFoundError):
        async for _ in subscribe("missing"):
            pass


async def test_finished_jobs_expire_after_retention(monkeypatch: pytest.MonkeyPatch) -> None:
    intake_id = _new_intake()
    job_id = start_analysis(intake_id, LOG_SEARCH_URL, None)
    await asyncio.wait_for(wait_for_job(job_id), timeout=60)
    assert analysis_job.get_job(job_id) is not None
    monkeypatch.setattr(analysis_job, "JOB_RETENTION_SECONDS", -1.0)
    assert analysis_job.get_job(job_id) is None


# --- HTTP API ------------------------------------------------------------------------------


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


async def test_api_rejects_disallowed_host() -> None:
    intake_id = _new_intake()
    transport = httpx.ASGITransport(app=_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/repositories/analyze",
            json={"intake_id": intake_id, "repo_url": "https://example.com/acme/widgets"},
        )
    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Host example.com is not allowed. Allowed: github.com, gitlab.com, dev.azure.com"
    )


async def test_api_unknown_intake_and_job() -> None:
    transport = httpx.ASGITransport(app=_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/repositories/analyze",
            json={"intake_id": "nope", "repo_url": HR_SCREENING_URL},
        )
        assert response.status_code == 404
        events = await client.get("/repositories/analyze/missing/events")
        assert events.status_code == 404
        findings = await client.get("/intakes/nope/findings")
        assert findings.status_code == 404


async def test_api_streams_events_and_serves_findings() -> None:
    intake_id = _new_intake()
    transport = httpx.ASGITransport(app=_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/repositories/analyze",
            json={"intake_id": intake_id, "repo_url": HR_SCREENING_URL, "access_token": ""},
        )
        assert response.status_code == 200
        job_id = response.json()["job_id"]

        received: list[tuple[str, dict[str, object]]] = []
        async with client.stream("GET", f"/repositories/analyze/{job_id}/events") as stream:
            assert stream.status_code == 200
            assert stream.headers["content-type"].startswith("text/event-stream")
            event_name = ""
            async for line in stream.aiter_lines():
                if line.startswith("event:"):
                    event_name = line.partition(":")[2].strip()
                elif line.startswith("data:"):
                    payload = json.loads(line.partition(":")[2].strip())
                    received.append((event_name, payload))
                    if event_name in {"done", "error"}:
                        break
        names = [name for name, _ in received]
        assert names[0] == "progress"
        assert names[-1] == "done"
        assert all(payload["type"] == name for name, payload in received)
        assert received[0][1] == {"type": "progress", "text": "Validating repository URL"}
        done_payload = received[-1][1]
        assert done_payload["intake_id"] == intake_id
        assert isinstance(done_payload["findings_count"], int)

        findings = await client.get(f"/intakes/{intake_id}/findings")
        assert findings.status_code == 200
        body = findings.json()
        assert len(body) == done_payload["findings_count"] >= 5
        assert set(body[0]) == {
            "field",
            "label",
            "value",
            "display_value",
            "confidence",
            "evidence_path",
            "snippet",
        }
        assert all(item["evidence_path"] for item in body)


async def test_api_findings_empty_before_analysis() -> None:
    intake_id = _new_intake()
    transport = httpx.ASGITransport(app=_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/intakes/{intake_id}/findings")
    assert response.status_code == 200
    assert response.json() == []
