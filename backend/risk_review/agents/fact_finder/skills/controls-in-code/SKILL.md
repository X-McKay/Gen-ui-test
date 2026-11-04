---
name: controls-in-code
description: Fact lane - which controls are actually wired into the system (guardrails on model inputs and outputs, access controls, personal-data minimisation before the model, rate limits and abuse monitoring, evaluation and red-teaming, vendor data protections, incident response, user disclosure) and whether a person reviews outputs.
metadata:
  owner: platform
  version: 1.0.0
  governance_tier: low
---

## Use this skill when

- You are assigned the fact lane `controls-in-code`.

## Fields

- `controls.in_place`: a list of the controls shown to be in place: `guardrails`,
  `access_controls`, `pii_minimisation`, `abuse_monitoring`, `pre_release_evaluation`,
  `vendor_data_protections`, `incident_response`, `user_disclosure`; `none` only when
  the searches below all come back empty (basis `absence`, confidence 0.6).
- `ai_system.human_oversight`: true when a person reviews or can override outputs on the
  path that matters (an approval step, a review queue, a draft the user edits).

## Where to look, per control

- guardrails: `llm-guard`, `nemoguardrails`, `guardrails-ai`, `rebuff`, moderation API
  calls, prompt-injection or output validators invoked around the model call.
- access_controls: auth middleware or dependencies (`Depends(get_current_user)`, OAuth,
  SSO, API keys on routes, role checks), `authlib`, `fastapi-users`, `passport`.
- pii_minimisation: redaction, hashing or pseudonymisation **before** the model call or at
  ingest (`presidio`, `scrubadub`, `redact(`, `hash(`), field allowlists in prompts.
- abuse_monitoring: rate limiters (`slowapi`, `express-rate-limit`, nginx `limit_req`),
  abuse or misuse logging, alerting, quotas.
- pre_release_evaluation: `evals/`, `eval` jobs in CI, red-team docs, model cards with
  test results, golden datasets.
- vendor_data_protections: documents stating a DPA, zero-data-retention or "not used for
  training" terms with the provider; a config flag that opts out of training.
- incident_response: feature flags or kill switches around the model call, rollback
  docs, runbooks, on-call and incident process documents.
- user_disclosure: UI copy or API responses telling people the content is AI-generated or
  that they are talking to an assistant; a transparency notice in docs.

## Traps

- A library in the manifest that is never called on the model path is not a control.
- A middleware that is defined but not registered, or registered only in a test app, is
  not a control.
- TODOs, roadmaps, issue templates and "we recommend" are plans.
- A CAPTCHA or a login page is access control or abuse monitoring, not a guardrail.

## Completion criteria

`controls.in_place` is recorded whenever at least one control is evidenced, or as
`["none"]` after the searches. Record `ai_system.human_oversight` whenever the docs or
the route flow settle it.
