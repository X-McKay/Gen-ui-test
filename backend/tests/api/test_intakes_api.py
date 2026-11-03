"""REST routes for intakes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import get_settings


def _client() -> TestClient:
    get_settings.cache_clear()
    return TestClient(create_app())


def test_create_read_update_and_defaults() -> None:
    client = _client()
    created = client.post(
        "/intakes",
        json={
            "mode": "new",
            "name": "Probe",
            "description": "An internal tool that uses an LLM.",
            "owner": "al",
        },
        headers={"x-forwarded-user": "sso-user"},
    )
    assert created.status_code == 201, created.text
    record = created.json()
    intake_id = record["meta"]["intake_id"]
    assert record["project"]["owner"] == {
        "value": "al",
        "confidence": 1.0,
        "source": "user",
        "confirmed": True,
    }

    read = client.get(f"/intakes/{intake_id}")
    assert read.status_code == 200
    assert read.json()["current_step"] is None

    updated = client.patch(
        f"/intakes/{intake_id}/fields",
        json={
            "updates": [
                {"path": "use_case.domains", "value": ["hr_employment"]},
                {"path": "ai_system.uses_ai", "value": "yes"},
            ]
        },
    )
    assert updated.status_code == 200
    assert updated.json()["assessment"]["eu_ai_act"]["classification"] == "high_risk"

    bad = client.patch(
        f"/intakes/{intake_id}/fields", json={"updates": [{"path": "nope.x", "value": 1}]}
    )
    assert bad.status_code == 422

    defaults = client.get("/intakes/defaults", headers={"x-forwarded-email": "me@example.com"})
    assert defaults.json() == {"owner": "me@example.com"}
    assert client.get("/intakes/missing").status_code == 404


def test_healthz_reports_mock_model_and_security_headers() -> None:
    client = _client()
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok" and body["mock_model"] is True
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-request-id"]


def test_agent_endpoint_is_rate_limited() -> None:
    import os

    os.environ["AGENT_RATE_LIMIT"] = "2/minute"
    try:
        client = _client()
        statuses = [client.post("/agent", json={}).status_code for _ in range(3)]
    finally:
        os.environ.pop("AGENT_RATE_LIMIT", None)
        get_settings.cache_clear()
    assert statuses[-1] == 429
    assert all(status != 429 for status in statuses[:2])
