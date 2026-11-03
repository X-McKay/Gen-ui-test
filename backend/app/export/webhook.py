"""Deliver the JSON export to the governance team's webhook (``INTAKE_WEBHOOK_URL``)."""

from __future__ import annotations

import asyncio

import httpx

WEBHOOK_TIMEOUT_S = 10.0
WEBHOOK_RETRIES = 2
WEBHOOK_BACKOFF_S = 0.5


class WebhookDeliveryError(RuntimeError):
    """The webhook did not accept the export after every retry."""


async def deliver_webhook(
    url: str,
    body: bytes,
    *,
    retries: int = WEBHOOK_RETRIES,
    timeout_s: float = WEBHOOK_TIMEOUT_S,
) -> None:
    """POST ``body`` as JSON. Retries connection errors and 5xx; 4xx fails immediately."""
    attempts = retries + 1
    last_error = "no attempt made"
    headers = {"Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        for attempt in range(1, attempts + 1):
            try:
                response = await client.post(url, content=body, headers=headers)
            except httpx.TransportError as error:
                last_error = f"connection error ({error.__class__.__name__}: {error})"
            else:
                if response.is_success:
                    return
                last_error = f"HTTP {response.status_code}"
                if not response.is_server_error:
                    break
            if attempt < attempts:
                await asyncio.sleep(WEBHOOK_BACKOFF_S * attempt)
    raise WebhookDeliveryError(
        f"The governance webhook did not accept the intake after {attempt} attempt(s): "
        f"{last_error}. The intake has not been marked as submitted."
    )
