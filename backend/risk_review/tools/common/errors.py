"""Shared error categories. Tools return these as structured results, never as prose."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ErrorKind = Literal["invalid_input", "not_found", "policy_rejected", "limit_exceeded", "transient"]


class ToolError(BaseModel):
    """A typed failure. ``kind`` tells the agent whether a retry can help (only ``transient``)."""

    ok: Literal[False] = False
    kind: ErrorKind
    message: str
    retryable: bool = False


def invalid_input(message: str) -> ToolError:
    return ToolError(kind="invalid_input", message=message)


def not_found(message: str) -> ToolError:
    return ToolError(kind="not_found", message=message)


def policy_rejected(message: str) -> ToolError:
    return ToolError(kind="policy_rejected", message=message)


def limit_exceeded(message: str) -> ToolError:
    return ToolError(kind="limit_exceeded", message=message)
