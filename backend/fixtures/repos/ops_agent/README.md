# Remedy: service-desk remediation agent

Remedy watches the IT service-desk queue and fixes the routine tickets itself. For each new
ticket it asks Claude (Anthropic API, `claude-sonnet-4-5`) which playbook applies, runs the
playbook on the affected host, and posts a comment on the ticket describing what it did.

Playbooks today: restart a systemd service, clear a full disk, reset an Active Directory
password, re-provision a VPN certificate.

**No person approves an action before it runs.** The agent is allowed to act on its own on
the hosts and accounts listed in `playbooks/scope.yaml`. Engineers see every action in the
console afterwards and can hit the kill switch (`POST /agent/stop`), which halts the agent and
reverts its last change using the playbook's rollback step.

## Who uses it

The infrastructure engineering team (about 20 people). The console is behind the company
OIDC login; ticket requesters never interact with the agent, they only see its comment.

## Data

Tickets contain the requester's name, corporate email, department, and whatever they typed
or attached - often screenshots, sometimes passwords they should not have pasted. The ticket
text is sent to Anthropic as part of the prompt. See `docs/data_handling.md`.

## Status

Live for the Frankfurt and Dublin offices since September. See `docs/roadmap.md` for the
approval step we plan to add.
