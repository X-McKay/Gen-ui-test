"""Structured JSON logging with a request id. Prompt and completion text never reach INFO."""

from __future__ import annotations

import contextvars
import logging
import re
import sys
import uuid
from collections.abc import Awaitable, Callable

from pythonjsonlogger.json import JsonFormatter
from starlette.requests import Request
from starlette.responses import Response

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

SECRET_PATTERN = re.compile(
    r"(ghp_[A-Za-z0-9]{10,}|github_pat_[A-Za-z0-9_]{10,}|glpat-[A-Za-z0-9_-]{10,}|"
    r"sk-[A-Za-z0-9_-]{10,}|Bearer\s+[A-Za-z0-9._-]{10,}|Basic\s+[A-Za-z0-9+/=]{10,})"
)


def redact(text: str) -> str:
    return SECRET_PATTERN.sub("[redacted]", text)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        return True


# Loggers that echo message content (prompt text, tool arguments) at INFO. They stay at
# WARNING unless AG-UI event logging is switched on for local debugging.
CONTENT_LOGGERS = (
    "ag_ui_adk.adk_agent",
    "ag_ui_adk.event_translator",
    "ag_ui_adk.endpoint",
    "ag_ui_adk.session_manager",
    "google_adk",
    "google.adk",
)


def configure_logging(level: str = "INFO", *, log_agui_events: bool = False) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s",
            rename_fields={"asctime": "time", "levelname": "level", "name": "logger"},
        )
    )
    handler.addFilter(RequestIdFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    for noisy in ("httpx", "httpcore", "LiteLLM", "litellm", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    logging.getLogger("google_adk.google.adk.telemetry._metrics").setLevel(logging.ERROR)
    for name in CONTENT_LOGGERS:
        logging.getLogger(name).setLevel(logging.DEBUG if log_agui_events else logging.WARNING)


async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers["x-request-id"] = request_id
    return response
