"""Logging setup for the planted fixture."""

from __future__ import annotations

import logging
import re

SECRET_PATTERN = re.compile(r"(ghp_[A-Za-z0-9]{10,}|sk-[A-Za-z0-9_-]{10,}|Bearer\s+[A-Za-z0-9._-]{10,})")


def redact(text: str) -> str:
    return SECRET_PATTERN.sub("[redacted]", text)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)  # DECOY LOG-D1: only msg is redacted, extra is not
        return True


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
