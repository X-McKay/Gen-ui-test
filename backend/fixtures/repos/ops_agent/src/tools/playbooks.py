"""Run a playbook's steps over SSH on the target host (paramiko)."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
import yaml

PLAYBOOK_DIR = Path(__file__).resolve().parents[2] / "playbooks"


def load_playbooks() -> str:
    parts = []
    for path in sorted(PLAYBOOK_DIR.glob("*.yaml")):
        if path.name == "scope.yaml":
            continue
        doc = yaml.safe_load(path.read_text())
        parts.append(f"- {doc['name']}: {doc['description']}")
    return "\n".join(parts)


def _ssh(host: str) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    client.connect(host, username="remedy", key_filename=os.environ["AGENT_SSH_KEY_PATH"])
    return client


def _render(command: str, parameters: dict[str, object]) -> str:
    for key, value in parameters.items():
        command = command.replace("{{ " + key + " }}", str(value))
    return command


def run_playbook(name: str, parameters: dict[str, object]) -> str:
    doc = yaml.safe_load((PLAYBOOK_DIR / f"{name}.yaml").read_text())
    host = str(parameters.get("host", "localhost"))
    with _ssh(host) as client:
        for step in doc["steps"]:
            command = _render(step.get("run") or step.get("verify"), parameters)
            _, stdout, _ = client.exec_command(command)
            if stdout.channel.recv_exit_status() != 0:
                return f"failed at: {command}"
    return "ok"


def rollback_playbook(name: str, parameters: dict[str, object]) -> None:
    doc = yaml.safe_load((PLAYBOOK_DIR / f"{name}.yaml").read_text())
    host = str(parameters.get("host", "localhost"))
    with _ssh(host) as client:
        for step in doc.get("rollback", []):
            client.exec_command(_render(step["run"], parameters))
