"""Main loop: poll the service desk, let the model choose a playbook, run it, comment."""

from __future__ import annotations

import os
import time

import anthropic

from src.agent.audit import record_action
from src.agent.killswitch import is_stopped
from src.tools.playbooks import load_playbooks, run_playbook
from src.tools.servicedesk import comment, new_tickets

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = "claude-sonnet-4-5"

SYSTEM = (
    "You are an IT remediation agent. Given a ticket, choose exactly one playbook from the "
    "catalogue and its parameters, or 'none' if no playbook fits. Then write a two-sentence "
    "comment for the requester explaining what was done."
)

TOOLS = [
    {
        "name": "choose_playbook",
        "description": "Pick the playbook to run for this ticket.",
        "input_schema": {
            "type": "object",
            "properties": {
                "playbook": {"type": "string"},
                "parameters": {"type": "object"},
                "comment": {"type": "string"},
            },
            "required": ["playbook", "parameters", "comment"],
        },
    }
]


def handle(ticket: dict[str, str]) -> None:
    catalogue = load_playbooks()
    response = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=SYSTEM,
        tools=TOOLS,
        tool_choice={"type": "tool", "name": "choose_playbook"},
        messages=[
            {
                "role": "user",
                "content": f"Catalogue:\n{catalogue}\n\nTicket #{ticket['id']} from "
                f"{ticket['requester_name']} <{ticket['requester_email']}>:\n{ticket['body']}",
            }
        ],
    )
    choice = response.content[0].input  # type: ignore[union-attr]
    if choice["playbook"] == "none":
        return
    # Runs immediately; there is no approval step (see docs/roadmap.md).
    result = run_playbook(choice["playbook"], choice["parameters"])
    record_action(ticket["id"], choice["playbook"], choice["parameters"], result)
    comment(ticket["id"], choice["comment"])


def main() -> None:
    while not is_stopped():
        for ticket in new_tickets():
            handle(ticket)
        time.sleep(30)


if __name__ == "__main__":
    main()
