# Roadmap

- **Approval step (planned, Q1):** require an engineer to approve password resets and
  certificate re-provisioning before the agent runs them. Not built yet.
- **Prompt redaction (planned):** strip emails and anything that looks like a secret from the
  ticket text before it is sent to the model. Design in review.
- **Prompt-injection filter (idea):** evaluate a classifier on inbound ticket text.
- Done: kill switch with rollback (August), audit log (July), OIDC on the console (July).
