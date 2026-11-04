# Data handling

- Prompts to the Anthropic API contain the full ticket text and the playbook catalogue. We
  are on the commercial API terms (no training on our data) but we have not yet added any
  redaction, so names, emails and anything pasted into a ticket reach the model.
- Every agent action (ticket id, playbook, host, result, rollback status) is written to the
  audit log in `src/agent/audit.py` and kept for one year.
- Agent console sessions are tied to the engineer's OIDC identity.
- Ticket data stays in the service-desk system (EU tenant); the agent keeps only the audit log.
