"""Kill switch: a flag file set by the console; the loop stops and rolls back its last action."""

from __future__ import annotations

from pathlib import Path

from src.agent.audit import last_action
from src.tools.playbooks import rollback_playbook

FLAG = Path("/run/remedy/STOP")


def is_stopped() -> bool:
    return FLAG.exists()


def stop_and_rollback() -> str:
    FLAG.touch()
    action = last_action()
    if action is None:
        return "stopped; nothing to roll back"
    rollback_playbook(action["playbook"], action["parameters"])
    return f"stopped; rolled back {action['playbook']} on ticket {action['ticket_id']}"
