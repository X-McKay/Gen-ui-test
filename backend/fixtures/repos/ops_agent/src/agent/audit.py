"""Append-only audit log of every action the agent took."""

from __future__ import annotations

import json
import time
from pathlib import Path

LOG = Path("/var/log/remedy/audit.jsonl")


def record_action(
    ticket_id: str, playbook: str, parameters: dict[str, object], result: str
) -> None:
    entry = {
        "ts": time.time(),
        "ticket_id": ticket_id,
        "playbook": playbook,
        "parameters": parameters,
        "result": result,
    }
    with LOG.open("a") as handle:
        handle.write(json.dumps(entry) + "\n")


def last_action() -> dict[str, object] | None:
    if not LOG.exists():
        return None
    lines = LOG.read_text().splitlines()
    return json.loads(lines[-1]) if lines else None
