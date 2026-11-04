"""Service-desk REST client: new tickets in, comments out."""

from __future__ import annotations

import os

import httpx

BASE = os.environ["SERVICEDESK_URL"]
HEADERS = {"Authorization": f"Bearer {os.environ['SERVICEDESK_TOKEN']}"}


def new_tickets() -> list[dict[str, str]]:
    response = httpx.get(f"{BASE}/tickets", params={"status": "new"}, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return [
        {
            "id": str(t["id"]),
            "requester_name": t["requester"]["name"],
            "requester_email": t["requester"]["email"],
            "body": t["description"],
        }
        for t in response.json()["tickets"]
    ]


def comment(ticket_id: str, text: str) -> None:
    httpx.post(
        f"{BASE}/tickets/{ticket_id}/comments", json={"body": text}, headers=HEADERS, timeout=20
    )
