# Risk review: agent-based codebase review on the local model

A developer tool, not part of the product. Two Google ADK agents on the same LiteLLM
endpoint as the app review this repository lane by lane and verify each other's findings.

```sh
make risk-review                                   # all six lanes + verification
make risk-review RISK_REVIEW_ARGS="--lanes logging-and-redaction --no-verify"
make eval-risk-review EVAL_ARGS="--suite smoke --repeats 3"
```

Reports land in `reports/risk-review/` (`report.md`, `report.json`, `trace.jsonl`).

## Why agents instead of grep

The risks that matter here are data-flow properties: model output deciding a tier, a
description reaching a log line through three helpers, `"unknown"` collapsing to false.
Each **lane** gives one agent a single invariant, its sources and sinks and the paths to
read; the agent traces flows with read-only tools and reports findings through a typed
tool that **rejects any evidence quote that does not match the file**. A second agent then
tries to disprove every finding. Grep-shaped checks belong in ruff, Semgrep or a test;
confirmed findings should become one of those.

## Layout (agent playbook, chapter 2)

```text
risk_review/
├── agents/
│   ├── lane_reviewer/         agent.yaml · factory.py · types.py · instructions/system.md
│   │   ├── skills/<lane>/     one SKILL.md per lane (invariant, sources, sinks, procedure)
│   │   └── tools/             report_findings (private; grounds evidence in code)
│   └── finding_verifier/      agent.yaml · factory.py · types.py · instructions/system.md
│       ├── skills/disprove-finding/
│       └── tools/             record_verdict (private)
├── skills/evidence-standards/ shared runtime skill
├── tools/
│   ├── common/                errors · policy (effect, retry safety) · telemetry callbacks
│   ├── repo/                  read-only list/read/search with path policy and output caps
│   └── testing/               bounded pytest runner (verifier only)
├── workflows/review.py        deterministic orchestration: lanes → findings → verdicts
├── steps/agent_step.py        the one place model and tool I/O happens
├── runtime/                   spec loader · skills loader · model policy · manifest · assembly
├── policy/budgets.py          request/token/tool budgets as ADK callbacks
├── observability/             run ledger + JSONL trace (counts and sizes only) · report
└── settings.py                RISK_REVIEW_* environment
```

An agent is a spec (`agent.yaml`), an instruction file, allowlisted skills and allowlisted
toolsets. The factory (`runtime/assembly.py`) refuses to build when the owner, version,
execution class, governance tier, risk assessment, model policy, budgets, a skill or a
toolset is missing, when the tier disagrees with `docs/risk-assessments/risk-review.yaml`,
or when a tool's effect exceeds the execution class (everything here is `read` under
`ephemeral`). It emits a **capability manifest** whose id is on every trace line, run
metric and eval result.

## What is measured

Every run records model requests, input/output/thinking tokens, tool calls by name, tool
errors, latency and an estimated cost (price table in `RISK_REVIEW_PRICE_*`; the local
endpoint defaults to 0). Budgets from the spec are enforced by callbacks: the run ends
with `budget_exhausted` instead of looping.

## Measured so far (2026-11-04, Qwen3.6-35B-A3B-NVFP4 on the local vLLM endpoint)

| Run | Result |
| --- | --- |
| `make risk-review`, six lanes, verifier on | 513 s wall at concurrency 3; 222 model requests; 4.4 M input / 59 k output tokens; 300 tool calls; 6 findings: 4 confirmed, 1 refuted, 1 unverified |
| Smoke evals, 4 cases × 2 runs on the planted fixture | recall 1.00 (10 of 10 planted defects every run), precision 0.89, decoy hit rate 0.12, pass rate 0.88; p50 24 s, p95 277 s per lane; mean 117 k, p95 575 k cumulative tokens; p95 34 requests |
| Safety suite (planted `.env` and `*.db`) | nothing from the secret files reached the result |

Per model request the context sits at 20-40 k tokens (tool output accumulates), latency
is 2-6 s, and the reasoning model emits only tool calls when thinking is off. The spread in
tokens comes from how far a run explores before reporting: the budget, the soft notice
and the grace request bound the worst case. Samples: `docs/risk-reviews/`.

## Evals (`backend/evals/risk_review/`)

```text
evals/risk_review/
├── fixtures/planted/      a mini backend with labelled defects (# PLANTED) and decoys (# DECOY)
├── datasets/smoke/        one case per planted lane: expected windows, decoys, budgets
├── datasets/safety/       secret-path case: nothing from .env may reach the result
├── evaluators/            deterministic (schema, grounding, recall, precision, decoys, leaks),
│                          trajectory (allowed/required tools, report calls), operational
│                          (latency, requests, tokens, cost, p50/p95)
├── baselines/<suite>.json thresholds + accepted numbers; `--promote` updates them
└── experiments/<id>/      results.json · summary.md · trace.jsonl (git-ignored)
```

Hard gates (binary): schema validity 1.0, grounding 1.0, zero forbidden tool calls, zero
leaked strings. `--promote` is refused while any gate fails. Quality: recall, precision, decoy hit rate, pass rate, and regression against
the accepted baseline. Operational: p95 latency, p95 tokens, p95 model requests. Use
`--repeats 3` or more for any change to instructions, skills, model settings or tool
descriptions; one run says little about a stochastic reviewer. There is no LLM judge yet;
add one only for qualities the deterministic evaluators cannot express (for example
"is the proposed test actually the right test").

## Adding a lane

1. `agents/lane_reviewer/skills/<lane>/SKILL.md` with frontmatter (`owner`, `version`,
   `governance_tier`) and the sections the tests require. Name real paths; a test fails
   when a named path disappears.
2. Add the name to `enabled_skills` in `agents/lane_reviewer/agent.yaml`.
3. Plant at least one defect and one decoy in `evals/risk_review/fixtures/planted/` and add
   a smoke case. Run `make eval-risk-review EVAL_ARGS="--case <id> --repeats 3"`.
4. Bump the agent `version` in the spec; behaviour changed.


## Repository risk assessment (`assess`)

`uv run python -m risk_review assess --repo PATH|URL` (or `make risk-assess REPO=...`) runs the
**fact finder** instead of the defect reviewer. It is the same runtime (spec, instruction, one
lane skill, two tools, budgets, trace) with a different job: establish the governance facts
the intake needs, each grounded in a line of the repository.

| Piece | Where |
| --- | --- |
| Agent spec, instruction, lane skills | `agents/fact_finder/{agent.yaml,instructions/system.md,skills/*/SKILL.md}` |
| Delivery tool | `agents/fact_finder/tools/record_facts.py`: value validated against the intake record (coerced and set exactly as the product does), every evidence quote checked against the file, facts accumulate per field |
| Workflow | `workflows/assess.py`: lanes in parallel, facts merged (the owning lane wins, then confidence; disagreements kept; `controls.in_place` is the union of every control a lane found with a verified line, and `none` stands only when no lane found one), an Annex III domain or a significant effect without its vocabulary in the quoted lines is kept at confidence 0.6 (needs confirmation), record built with `source="repo:<file>"`, rules engine run, residual shown unconfirmed and "if confirmed", open questions listed |
| Report | `observability/report.py::render_assessment_markdown` and `assessment.json` |
| Eval | `evals/intake_assessment` suite `repos`: the four fixture repositories (`hr_screening`, `log_search`, `claims_settlement`, `ops_agent`) with gold facts, scored like description extraction, with agent-scale operational thresholds in `baselines/repos.json` |

The lanes are `purpose-and-users`, `ai-usage`, `data-and-privacy`, `third-party-services`
and `controls-in-code`. A sixth lane is a new skill directory plus its entry in
`FIELD_OWNERS` in `workflows/assess.py`.
