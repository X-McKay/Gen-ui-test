"""Router contract: content types, attachment names, 404s and the submit webhook."""

from __future__ import annotations

import json
from collections.abc import Iterator

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import exports
from app.export import webhook
from app.intake.record_service import IntakeNotFoundError
from app.intake.schema import IntakeRecord, IntakeStatus
from app.settings import Settings

WEBHOOK_URL = "https://governance.example.test/hooks/intake"


@pytest.fixture
def client() -> Iterator[TestClient]:
    application = FastAPI()
    application.include_router(exports.router)
    with TestClient(application) as test_client:
        yield test_client


@pytest.fixture
def stored_record(monkeypatch: pytest.MonkeyPatch, high_risk_record: IntakeRecord) -> IntakeRecord:
    """Serve ``high_risk_record`` for its id and raise for any other id."""

    def fake_get_record(intake_id: str) -> IntakeRecord:
        if intake_id != high_risk_record.meta.intake_id:
            raise IntakeNotFoundError(intake_id)
        return high_risk_record

    monkeypatch.setattr(exports, "get_record", fake_get_record)
    return high_risk_record


@pytest.fixture
def submitted_records(monkeypatch: pytest.MonkeyPatch) -> list[IntakeRecord]:
    """Capture ``mark_submitted`` calls without touching the database."""
    calls: list[IntakeRecord] = []

    def fake_mark_submitted(record: IntakeRecord) -> IntakeRecord:
        record.meta.status = IntakeStatus.SUBMITTED
        calls.append(record)
        return record

    monkeypatch.setattr(exports, "mark_submitted", fake_mark_submitted)
    return calls


def configure_webhook(monkeypatch: pytest.MonkeyPatch, url: str | None) -> None:
    settings = Settings(_env_file=None, intake_webhook_url=url, mock_model=True)
    monkeypatch.setattr(exports, "get_settings", lambda: settings)
    monkeypatch.setattr(webhook, "WEBHOOK_BACKOFF_S", 0.0)


# --- Downloads ------------------------------------------------------------------------------


def test_export_json(client: TestClient, stored_record: IntakeRecord) -> None:
    response = client.get("/intakes/t/export.json")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["content-disposition"] == 'attachment; filename="intake-t.json"'
    payload = response.json()
    assert payload["$schema"] == "https://intake.local/schema/intake.schema.json"
    assert payload["meta"]["intake_id"] == "t"
    assert payload["ai_system"]["uses_ai"]["source"] == "repo:requirements.txt"
    assert response.content.endswith(b"}\n")


def test_export_pdf(client: TestClient, stored_record: IntakeRecord) -> None:
    response = client.get("/intakes/t/export.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == 'attachment; filename="intake-t.pdf"'
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 2048


def test_form_html_preview(client: TestClient, stored_record: IntakeRecord) -> None:
    response = client.get("/intakes/t/form.html")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "content-disposition" not in response.headers
    assert "Candidate summary assistant" in response.text
    assert "Appendix: Open questions" in response.text


@pytest.mark.parametrize(
    "path",
    ["/intakes/missing/export.json", "/intakes/missing/export.pdf", "/intakes/missing/form.html"],
)
def test_downloads_404_for_unknown_intake(
    client: TestClient, stored_record: IntakeRecord, path: str
) -> None:
    response = client.get(path)
    assert response.status_code == 404
    assert response.json() == {"detail": "Intake not found"}


def test_attachment_filename_is_sanitised() -> None:
    headers = exports.attachment_headers('we"ird/id\r\n', "json")
    assert headers == {"Content-Disposition": 'attachment; filename="intake-we_ird_id__.json"'}


# --- Submit ---------------------------------------------------------------------------------


def test_submit_without_webhook_marks_submitted_locally(
    client: TestClient,
    stored_record: IntakeRecord,
    submitted_records: list[IntakeRecord],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_webhook(monkeypatch, None)
    with respx.mock(assert_all_called=False) as router:
        route = router.post(WEBHOOK_URL)
        response = client.post("/intakes/t/submit")
        assert not route.called
    assert response.status_code == 200
    assert response.json() == {
        "status": "submitted",
        "delivered": False,
        "message": "No webhook configured; the intake is marked submitted locally",
    }
    assert submitted_records == [stored_record]
    assert stored_record.meta.status is IntakeStatus.SUBMITTED


def test_submit_posts_export_to_webhook(
    client: TestClient,
    stored_record: IntakeRecord,
    submitted_records: list[IntakeRecord],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_webhook(monkeypatch, WEBHOOK_URL)
    with respx.mock() as router:
        route = router.post(WEBHOOK_URL).mock(return_value=httpx.Response(202))
        response = client.post("/intakes/t/submit")
    assert response.status_code == 200
    assert response.json() == {
        "status": "submitted",
        "delivered": True,
        "message": "Sent to the governance team",
    }
    assert route.call_count == 1
    request = route.calls.last.request
    assert request.headers["content-type"] == "application/json"
    body = json.loads(request.content)
    assert body["$schema"] == "https://intake.local/schema/intake.schema.json"
    assert body["meta"]["intake_id"] == "t"
    assert body["data"]["special_category_data"]["value"] == "unknown"
    assert submitted_records == [stored_record]


def test_submit_retries_server_errors_then_succeeds(
    client: TestClient,
    stored_record: IntakeRecord,
    submitted_records: list[IntakeRecord],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_webhook(monkeypatch, WEBHOOK_URL)
    with respx.mock() as router:
        route = router.post(WEBHOOK_URL).mock(
            side_effect=[
                httpx.Response(503),
                httpx.ConnectError("connection refused"),
                httpx.Response(200),
            ]
        )
        response = client.post("/intakes/t/submit")
    assert response.status_code == 200
    assert response.json()["delivered"] is True
    assert route.call_count == 3
    assert len(submitted_records) == 1


def test_submit_returns_502_when_webhook_keeps_failing(
    client: TestClient,
    stored_record: IntakeRecord,
    submitted_records: list[IntakeRecord],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_webhook(monkeypatch, WEBHOOK_URL)
    with respx.mock() as router:
        route = router.post(WEBHOOK_URL).mock(return_value=httpx.Response(500))
        response = client.post("/intakes/t/submit")
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "3 attempt(s)" in detail
    assert "HTTP 500" in detail
    assert "not been marked as submitted" in detail
    assert route.call_count == 3
    assert submitted_records == []
    assert stored_record.meta.status is not IntakeStatus.SUBMITTED


def test_submit_does_not_retry_client_errors(
    client: TestClient,
    stored_record: IntakeRecord,
    submitted_records: list[IntakeRecord],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_webhook(monkeypatch, WEBHOOK_URL)
    with respx.mock() as router:
        route = router.post(WEBHOOK_URL).mock(return_value=httpx.Response(401))
        response = client.post("/intakes/t/submit")
    assert response.status_code == 502
    assert "HTTP 401" in response.json()["detail"]
    assert route.call_count == 1
    assert submitted_records == []


def test_submit_404_for_unknown_intake(
    client: TestClient, stored_record: IntakeRecord, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_webhook(monkeypatch, WEBHOOK_URL)
    response = client.post("/intakes/missing/submit")
    assert response.status_code == 404
    assert response.json() == {"detail": "Intake not found"}


def test_submit_persists_through_real_mark_submitted(
    client: TestClient, stored_record: IntakeRecord, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End to end against the isolated SQLite database: the row is written as submitted."""
    from app.intake import intake_store

    configure_webhook(monkeypatch, None)
    response = client.post("/intakes/t/submit")
    assert response.status_code == 200
    loaded = intake_store.load_record("t")
    assert loaded is not None
    assert loaded.meta.status is IntakeStatus.SUBMITTED
    assert loaded.meta.submitted_at is not None
