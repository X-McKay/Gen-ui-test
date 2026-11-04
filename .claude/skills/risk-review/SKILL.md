---
name: risk-review
description: Run or extend the agent-based risk review (backend/risk_review) and its evals; use when asked to review the codebase for risk with agents, add a lane, interpret a risk-review report, or check the reviewer's accuracy, latency and token use.
---

# Agent-based risk review

Two ADK agents on the local model (`backend/risk_review/`, layout in its README):
`lane-reviewer` traces one lane's sources to sinks and reports grounded findings;
`finding-verifier` tries to disprove each one. Evals live in `backend/evals/risk_review/`.

## Run it

```sh
make risk-review                                            # six lanes + verification, ~10–25 min
make risk-review RISK_REVIEW_ARGS="--lanes logging-and-redaction,export-rendering --no-verify"
make eval-risk-review EVAL_ARGS="--suite smoke --repeats 3"  # accuracy, latency, tokens vs baseline
make eval-risk-review EVAL_ARGS="--suite safety"
```

Read `reports/risk-review/report.md`: the first table is cost (requests, tokens, time), then
one row per lane, then findings sorted confirmed-first. Only **confirmed** findings with a
cited guard-free path are actionable; `refuted` ones name the guard, `uncertain` ones say
what would settle it. Turn a confirmed finding into a test or a deterministic check before
fixing it.

## Interpreting an eval

`summary.md` in the experiment folder starts with the release verdict and the gate table.
Hard gates (schema validity, grounding, forbidden tools, leaked strings) must be 100 %;
they never average away. Quality gates are recall, precision, decoy hit rate and pass rate,
with a regression tolerance against `baselines/<suite>.json`. Operational gates are p95
latency, tokens and model requests. Promote a result with `--promote` only after a
`--repeats 3` run that you have read case by case.

## Changing behaviour

- Instructions, a skill, model settings, a tool description: bump `version` in the agent's
  `agent.yaml`, rerun the smoke suite with repeats, compare with the baseline.
- New lane: `/risk-review` README section "Adding a lane" (skill + spec allowlist + planted
  defect + smoke case).
- New tool: a policy record (`effect`, `retry_safety`, timeout, data classification) next to
  it; a non-`read` effect will not build under the agents' `ephemeral` execution class, by
  design.
- Keep tool results bounded and free of secrets; the repository service refuses `.env*`,
  `*.db` and key material and the trace records counts, never content.

## Known traps

- ADK treats `{name}` in a plain instruction string as a state template; the factory passes
  the instruction through a provider for that reason. Keep it that way.
- The reasoning model must run with thinking off for tool calls (model policy
  `balanced-v1`); `reasoning-v1` is there to measure the difference, not as the default.
- `report_findings` rejects a finding whose quote is not on the cited line; a reviewer that
  keeps getting rejections is usually paraphrasing. The message tells it the nearby line.
