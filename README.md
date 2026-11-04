# AI Governance Intake

**Intake** replaces the static AI-governance questionnaire with a short, adaptive interview.
A user describes a project (or points at its repository), an agent extracts what it can,
shows those inferences as chips to confirm in bulk, asks only the questions that are still
open (at most three per step, gates first) and ends on a review page. The result is an
`IntakeRecord` (JSON with per-field confidence, source and confirmation), a PDF intake form
and a classification produced by a deterministic rules engine: EU AI Act first, with GDPR,
NIST AI RMF, ISO/IEC 42001 and an internal-policy module plugged in behind it. Typical
intakes finish in 4–8 questions; high-risk ones in at most 15.

See [docs/DEMO.md](docs/DEMO.md) for a screenshot walkthrough and [docs/PLAN.md](docs/PLAN.md) for the design
decisions and library verification.

## Architecture

```text
 Browser (Next.js 16, React 19, CopilotKit v2 generative UI)
 ├── /                      landing: New project | Existing project
 ├── /intake/new            describe form → POST /api/backend/intakes → interview column
 ├── /intake/existing       repository form → POST /api/backend/repositories/analyze
 │                          → SSE progress → interview column (FindingsReview first)
 ├── /intake/<id>/review    record, classification panel, exports, submit
 ├── A2UI catalog intake/interview@1 (8 components, frontend/generative-ui/intakeCatalog.ts)
 ├── /api/copilotkit        CopilotRuntime v2: HttpAgent → backend /agent, generativeUI
 │                          middleware validates every render_ui operation against the catalog
 └── /api/backend/*         same-origin proxy to the FastAPI REST API (runtime BACKEND_URL,
                            forwards SSO headers, streams SSE)
                 │ AG-UI over SSE                       │ REST (JSON, SSE)
                 ▼                                      ▼
 Backend (FastAPI, Python 3.12, uv)
 ├── POST /agent            ag_ui_adk.ADKAgent → Google ADK LlmAgent "intake_agent"
 │     tools: extract_intake_facts · update_intake_fields · get_next_questions · finalize_intake
 │            + render_ui (frontend tool, filtered through AGUIToolset)
 │     model: LiteLlm (openai_compatible | bedrock) or ScriptedLlm when MOCK_MODEL=1
 │     shared state: tool_context.state["intake"] → STATE_SNAPSHOT / STATE_DELTA events
 ├── /intakes, /intakes/{id}, /intakes/{id}/fields, /export.json, /export.pdf, /form.html,
 │   /submit, /repositories/analyze, /repositories/analyze/{job}/events, /healthz
 ├── app/intake/            schema (FieldMeta), question_bank, gap_analysis, record_service
 ├── app/governance/        eu_ai_act rule table + frameworks/{gdpr,nist_ai_rmf,iso_42001,internal_policy}
 ├── app/repo_analysis/     clone (shallow, allowlisted) → inventory → detectors → findings
 ├── app/export/            JSON with provenance, Jinja → WeasyPrint PDF
 └── SQLite via SQLModel    (DATABASE_URL; Postgres by connection string)
```

### Facts from the model, decisions from code

The model is only allowed to *read* and *phrase*. Every change to the record goes through
one of four server tools; the server validates values against the schema, stamps provenance
(`source`, `confidence`, `confirmed`) and reclassifies. The model never decides what is
required (`question_bank.py`), what is asked next (`gap_analysis.py`), what the risk tier is
(`governance/`), or what the UI looks like (`get_next_questions` returns a ready-made
`render_plan`; the model calls `render_ui(target="interview", operations=[])` and the server
substitutes the plan, or passes the plan with only the intro rewritten). The CopilotKit runtime
rejects any `render_ui` operation that is not in the catalog and returns the rejection to the
agent, which re-renders; the server restores the plan behind every `render_ui` call for the
current step before it is forwarded (`app/agents/render_repair.py`), so a 30-finding step
renders in a few seconds instead of waiting for the model to copy it. The same deterministic path runs with
`MOCK_MODEL=1`, where a scripted model drives the identical tool loop from a keyword
extractor, so CI and the mock Playwright suite never touch the network.

### Inherent and residual risk

The EU AI Act classification says what the law requires. Two more tables in
`app/governance/risk_profile.py` say how risky the use case is and how much of that risk the
owner has already dealt with:

- **Inherent risk** scores the use case as described, in five categories: exposure (who meets
  the system: public, external, conversational, generative, third-party model), autonomy
  (acts alone, nobody can override), data (personal, special-category, biometric, minors,
  training, transfers), impact (significant effects, Annex III area, emotion inference, and
  what the system executes itself: `use_case.acts_on_the_world`, financial transactions,
  equipment or system actions, legal commitments) and magnitude (`use_case.financial_exposure`,
  what one incident could cost: over a million is 5 points, up to a million 2). Bands: 0–3
  low, 4–7 medium, 8–13 high, 14+ critical, with a floor from the legal classification. An
  externally facing chatbot lands in **high**; so does an algorithmic trading strategy that
  places orders itself with millions at stake, although it touches no personal data.
- **Residual risk** removes points per control the owner has **confirmed** (`controls.in_place`:
  guardrails, access controls, personal-data minimisation, abuse monitoring, evaluation and
  red-teaming, vendor data protections, incident response, user disclosure, hard limits; plus
  human oversight), capped per category, and keeps a legal floor: a prohibited practice stays
  critical and an Annex III system stays at least medium. The same chatbot with confirmed
  guardrails, disclosure, monitoring and redaction is **low**. Oversight and testing lower the
  likelihood of an incident, not its size, so only a confirmed hard limit (position, loss,
  spend or order caps) lowers the magnitude category: the trading desk with a kill switch and
  position limits confirmed is **medium**, not low.

- **Six enterprise lenses** reuse the same drivers and controls, each tagged with the lenses
  it counts towards: data and privacy, information security, operational, financial,
  reputational and regulatory. Every lens gets its own inherent and residual tier, so a
  public chatbot with no personal data reads high on information security and reputational
  risk and low on data privacy, and the legal floor applies to the regulatory lens only.

The two action facts are asked only where they can matter: `acts_on_the_world` once the
system recommends or decides, `financial_exposure` once it executes financial transactions.
Trading in financial instruments is its own domain value (`financial_markets`), not an
Annex III area; when the system determines orders itself the `MiFID II algorithmic trading`
framework module adds the Art. 17 and RTS 6 obligations (pre-trade limits, kill functionality,
testing, real-time monitoring and five-year records, notification of the competent authority,
annual self-assessment), brings DORA into scope and floors the overall tier at high. A model
that only ranks stocks for a trader to execute gets none of this.

Both profiles list their drivers and every control with its status (confirmed, claimed but
not confirmed, not in place, not answered) on the review page and in the PDF. A control the
model inferred from the description never lowers the residual until a person confirms it, and
the extraction prompt only records controls described as in place today, never plans. The
controls question is a single multi-select, asked only when the inherent risk is medium or
above, so a low-risk tool is not interviewed about guardrails.

### Repository risk assessment (agentic, fact-based)

`make risk-assess REPO=<path or https URL>` points the fact-finder agents at an arbitrary
repository and produces the same assessment the intake produces for a description, grounded
in the repository's files:

1. Five **fact lanes** run in parallel, each an agent made of a prompt, one lane skill and two
   tools (`backend/risk_review/agents/fact_finder/`): purpose and users, AI usage, data and
   privacy, third-party services, controls in code. Each records facts with `record_facts`,
   which validates the value against the intake record exactly as the product does and
   checks every evidence quote against the cited line, so a fact the repository does not
   show never reaches the report.
2. Facts are merged (highest confidence wins, disagreements kept), written into an intake
   record with `source="repo:<file>"` and nothing confirmed, and the deterministic rules
   engine runs: EU AI Act classification and obligations, the framework modules, inherent
   risk and residual risk. The report shows the residual risk as it stands (no control
   confirmed) and what it would be if the claimed controls were confirmed, plus the required
   questions the repository could not answer, which is where the intake interview starts.
3. `reports/risk-assessment/assessment.md` lists every fact with its evidence line, the risk
   drivers, the controls with their status, the rationale and the obligations, and the cost
   of the run (requests, tokens, tool calls, time per lane).

The model never rates risk; it only establishes facts, and only facts with evidence. The
four fixture repositories (`hr_screening`, `log_search`, `claims_settlement`, `ops_agent`)
double as eval cases (`make eval-intake EVAL_ARGS="--suite repos"`).

Measured on the local model (`docs/risk-reviews/`):

| Eval | Result |
| --- | --- |
| Descriptions, `facts` suite, 27 cases x 2 runs | pass rate 0.70, field accuracy 0.94, silent missed risks 0, risk false positives in 6 % of runs (19 % before the vetting round), inherent tier exact 0.83, residual 0.85; the gap is Annex III and action values kept at confidence 0.6 that become confirmation questions; p50 20 s per extraction. One control false positive remained in the last run (`hard_limits` credited for a loan model's 5,000-euro auto-decision threshold), which on reading the case is a real hard limit, so the gold now lists it |
| Descriptions, `scenarios` suite, 28 use-case types x 2 runs | pass rate 0.75 (0.44 when first run unseen), field accuracy 0.95, risk false positives in 2 % of runs, control false positives 0, missed risks in 2 % of runs, inherent tier exact 0.82, residual 0.91; every gate passes and the run is the promoted baseline. The algorithmic-trading case derives inherent high and residual medium in both runs (`financial_exposure: over_1m` at 0.9–1.0, kill switch and position limits found); the trader's signal tool stays low with `acts_on_the_world: [none]` |
| Repository, `hr_screening` fixture | 37 grounded facts, EU high-risk, inherent high, residual medium if the claimed controls are confirmed, 313 s, 52 requests, 418 k input tokens |
| Repository suite, four fixtures through the agents | field accuracy 0.89–0.91 over two runs, the new facts right where they apply (`claims_settlement`: pays claims itself, exposure under 10 k from `AUTO_SETTLE_LIMIT_EUR`; `ops_agent`: system actions at 0.95); what remains are one-fact judgment calls that vary between runs (whether a form-based app "interacts", whether code without an auth dependency has access controls, one run crediting `pii_minimisation` or `pre_release_evaluation` from a unit-test CI job without evidence, a provider's no-training terms missed in one run) and capped Annex III values raising a tier; 320–415 s median, 0.5–0.7 M input tokens per repository |

Evidence grounding in code did most of the work: a risk-raising value whose evidence quote is
not in the description is capped at low confidence (so the owner is asked) or dropped
(domains and controls), a claimed control must be named in the text, and an Annex III domain
or a significant effect must have its vocabulary in the evidence quote (`DOMAIN_KEYWORDS`,
`EFFECT_KEYWORDS` in `inference/structured_extraction.py`; the fact finder applies the same
rule to its quoted lines), otherwise the value is kept but needs confirmation. Before any of
that, control false positives were 18 in 54 runs and the pass rate was 0.30.

### Surface lifecycle

- One generative-UI target: `interview` (`INTERVIEW_TARGET_ID`), rendered by
  `components/intake/IntakeSurface.tsx`.
- Each step gets its own surface `step-<n>`. `get_next_questions` returns `surface_id`,
  `previous_surface_id` and a `render_plan` that deletes the previous surface and creates the
  next one in the same `render_ui` call. Ids are never reused.
- Every step is one `InterviewStep` root with optional `AssumptionReview` / `FindingsReview`
  and up to three question components. Its single confirm button emits `onSubmit`, which the
  runtime forwards as the user message `submit_step` with `answers`, `assumptions` and
  `notSure`. The agent calls `update_intake_fields` once with all of them (`"unknown"` for
  `notSure`), then `get_next_questions` again.
- `render_ui` is a long-running frontend tool, so each render ends the run; the next confirm
  starts the next run. `done: true` → `finalize_intake` → the page redirects to
  `/intake/<id>/review`. An `escalation` step renders `EscalationNotice` and stops.
- `meta.question_count` counts questions shown to the user, not surfaces or chips.

## Running locally

Prerequisites: Python 3.12, [uv](https://docs.astral.sh/uv/), Node 22, pnpm 11 (enable with
`corepack enable`), git. For PDF export the host needs WeasyPrint's native libraries
(`libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libcairo2 libjpeg62-turbo libopenjp2-7`);
the Dockerfile and CI install them.

```sh
mise install        # optional: python 3.12, uv, node 22, pnpm 11 from .mise.toml
make setup          # uv sync · pnpm install · playwright chromium · .env + frontend/.env.local · pre-commit · doctor
make doctor         # re-check the host any time (toolchain, WeasyPrint libraries, ports)

make dev            # backend :8000 (uvicorn --reload) + frontend :3000, live model endpoint
make dev-mock       # same with MOCK_MODEL=1: deterministic, offline
make backend        # or run either side alone
make frontend
make install-browsers   # firefox + webkit, only for the full `make e2e` matrix
```

`make setup` is idempotent: it never overwrites an existing `.env` or `frontend/.env.local`.
The pre-commit hooks (`.pre-commit-config.yaml`) run the project's own ruff, mypy, prettier,
eslint and schema check on the files you commit, and refuse `.env`, `*.db` and
`.playwright-mcp/`. Working with Claude Code? `CLAUDE.md` holds the invariants, `.claude/skills/`
the `/add-question`, `/add-framework`, `/verify` and `/e2e-debug` skills, and
`docs/claude-code-settings.json` the recommended hooks and permission allowlist to copy into
`.claude/settings.json`.

`make dev` runs both servers in one terminal with a POSIX trap: Ctrl-C stops both, and if
either exits the other is stopped too (make prints `Terminated`; that is the trap, not an
error). Open <http://localhost:3000>.

With containers:

```sh
cp .env.example .env
docker compose up --build            # or: make docker-up / make docker-down
```

`docker-compose.yml` starts the backend (env from `.env`, sqlite on the `intake-data`
volume, port 8000) and the frontend (`BACKEND_URL=http://backend:8000`, port 3000) once the
backend health check passes. The frontend image runs `next start`; `next.config.ts` does not
set `output: "standalone"`, so the image ships `node_modules`. Setting standalone output would
allow a much smaller runtime stage (`.next/standalone` + `node server.js`).

`make help` lists every target.

## Configuration

All settings come from the environment (`backend/app/settings.py`, pydantic-settings, reads
`.env` from the backend working directory). Values are validated at startup: a wrong
`MODEL_ID` prefix or a missing `AWS_REGION` fails fast with a message naming the variable.

| Variable | Default | Purpose |
| --- | --- | --- |
| `INFERENCE_PROVIDER` | `openai_compatible` | `openai_compatible` (any OpenAI-style endpoint via LiteLLM) or `bedrock`. |
| `OPENAI_BASE_URL` | `https://llm.almckay.io/v1` | The live vLLM endpoint used by default. |
| `OPENAI_API_KEY` | empty | Sent when set; the dev endpoint accepts none. Never logged. |
| `MODEL_ID` | `openai/Qwen3.6-35B-A3B-NVFP4` | `openai/<id from GET /v1/models>`; `bedrock/<model-id>` for Bedrock. |
| `AWS_REGION` | unset | Required for `INFERENCE_PROVIDER=bedrock`; credentials come from the standard AWS chain. |
| `INFERENCE_TIMEOUT_S` | `60` | Per-call model timeout. |
| `INFERENCE_MAX_RETRIES` | `2` | LiteLLM retries. |
| `MOCK_MODEL` | `0` | `1` swaps in `ScriptedLlm`: same tools, same `render_ui` calls, no network. |
| `ENVIRONMENT` | `development` | `development`, `test` or `production`. Outside `production` the four fixture repositories (`https://github.com/intake-fixtures/hr-screening`, `.../log-search`, `.../claims-settlement`, `.../ops-agent`) are served from bundled directories without a clone. |
| `LOG_LEVEL` | `INFO` | Root log level. |
| `LOG_AGUI_EVENTS` | `0` | `1` raises the AG-UI/ADK loggers to DEBUG (they echo message content; local debugging only). |
| `DATABASE_URL` | `sqlite:///./intake.db` | Any SQLAlchemy URL, e.g. `postgresql+psycopg://…`. |
| `FRONTEND_ORIGIN` | `http://localhost:3000` | CORS allow-origin for the API. |
| `AGENT_RATE_LIMIT` | `60/minute` | Sliding-window limit per client on `POST /agent` (429 beyond it). The client is the first `X-Forwarded-For` entry, which the Next proxy sets, else the socket address. |
| `AGENT_MAX_CONCURRENT_RUNS` | `200` | Open interviews the agent keeps at once; every rendered step holds an execution slot until the interview finishes or goes stale. |
| `AGENT_EXECUTION_TIMEOUT_S` | `600` | Seconds after which an abandoned interview's slot is reclaimed. |
| `DEFAULT_OWNER` | empty | Prefilled `project.owner` when no SSO header is present. |
| `INTAKE_WEBHOOK_URL` | empty | Submit posts the JSON export here; unset marks the intake submitted locally and says so. |
| `REPO_ALLOWED_HOSTS` | `["github.com","gitlab.com","dev.azure.com"]` | Hosts (and subdomains) that may be cloned. JSON list. |
| `REPO_ACCESS_TOKEN` | empty | Default token for private repositories; the form can override it per request. |
| `REPO_CLONE_TIMEOUT_S` | `120` | The git process is killed after this. |
| `REPO_MAX_SIZE_MB` | `200` | Clone size cap, checked after the shallow clone. |
| `REPO_MAX_FILES` | `20000` | Inventory cap. |
| `BACKEND_URL` (frontend) | `http://localhost:8000` | Server-side only; read at request time by `/api/backend/*` and `/api/copilotkit`. The browser never sees it. |
| `NEXT_PUBLIC_ENABLE_INSPECTOR` (frontend) | `1` | CopilotKit Inspector outside production; `0` hides it. |
| `COPILOTKIT_TELEMETRY_DISABLED` (frontend) | `true` | Keeps the runtime from phoning home. |

Switching to Bedrock: set `INFERENCE_PROVIDER=bedrock`, `MODEL_ID=bedrock/<model-id>`,
`AWS_REGION`, and provide credentials through the AWS chain. Nothing else changes; both
providers go through `app/inference/model_factory.py`, including the one-call tool-calling
extraction in `structured_extraction.py` (no JSON mode, so it works on vLLM).

## Testing

| Layer | Command | What it covers |
| --- | --- | --- |
| Backend unit + contract | `make test-backend` | pytest over `backend/tests` (schema, question bank, gap analysis, record service, tools, API routes, exports, repository analysis). Fails below **100 % branch coverage on `app/governance`** (`--cov=app/governance --cov-fail-under=100`). |
| Frontend unit | `make test-frontend` | vitest over `frontend/**/*.test.{ts,tsx}`, beside their subjects (formatters, field catalog, catalog schemas, …); `--passWithNoTests` keeps it green on a fresh checkout. |
| Both | `make test` | |
| Static checks | `make lint`, `make typecheck` | ruff format/check, eslint, prettier `--check` (`frontend/.prettierrc`, print width 120); mypy `--strict`, `tsc --noEmit`. `make format` fixes what it can. |
| Schema contract | `make check-schema` | `schema/intake.schema.json` must match the Pydantic model and `frontend/lib/intakeTypes.ts` must match the schema. `make export-schema` regenerates both. |
| End to end, mock | `make e2e` | Playwright on chromium, firefox, webkit and Pixel 7; `playwright.config.ts` starts both servers with `MOCK_MODEL=1`. Specs in `frontend/e2e/`. |
| End to end, live | `make e2e-live` | Same specs with `E2E_LIVE=1` against the real endpoint; counts relax to the plan's bounds. |
| Intake assessment evals | `make eval-intake` | `backend/evals/intake_assessment/`: suites `facts` (27 descriptions: generative AI, classical ML, no AI, PII, biometrics, planned controls, prohibited practices), `scenarios` (28 more: agentic automation, retrieval assistants, critical infrastructure, insurance, legal, education, law enforcement, migration, media, marketing, security operations, healthcare, trading, public services, children, accessibility, workforce management, with traps for specific false positives) and `repos` (the four fixture repositories through the fact-finder agents). Each case carries gold facts and the inherent/residual tiers the engine must derive. Runs the real extraction or the agents on the configured model; reports field accuracy, **risk false positives**, **control false positives**, missed risks, tier agreement, confident risk values on fields the case does not list (reported, not gated), latency and tokens, and gates against `baselines/<suite>.json`. |
| Interactive | `make e2e-ui` | Playwright UI mode. Set `E2E_EXTERNAL_SERVERS=1` to reuse already-running servers. |

Locally the same checks run as pre-commit hooks after `make setup`. CI (`.github/workflows/ci.yml`) runs `backend`, `schema` and `frontend` on every pull request
and push to `main`, then `e2e-mock` with all three browsers and uploads the Playwright report
and traces on failure. `.github/workflows/e2e-live.yml` runs the chromium suite against the
live endpoint nightly at 03:00 UTC and on demand, reading the key from the
`LLM_ALMCKAY_API_KEY` secret.

## Observability

- Logs are JSON lines on stdout (`app/logging_config.py`): `time`, `level`, `logger`,
  `message`, `request_id` plus structured extras (`intake_id`, counts, provider, latency).
- Every request gets a request id (`X-Request-Id` in → same header out; generated when
  absent). The Next.js proxy forwards it, so one id follows a browser call into the backend.
- Never logged at INFO: prompt text, completions, tool arguments, descriptions, repository
  content, tokens. The AG-UI/ADK loggers that echo content sit at WARNING unless
  `LOG_AGUI_EVENTS=1`; a redaction filter masks token-shaped strings (`ghp_…`, `sk-…`,
  `Bearer …`) in any message that does get through.
- `GET /healthz` reports liveness, the schema version, `mock_model` and a cached one-token
  model check (`?refresh=1` forces it); Docker and Playwright's global setup wait on it.
- In development the **CopilotKit Inspector** (floating button, bottom right) shows every
  AG-UI event, tool call, `render_ui` operation and state delta of the current run.
  `NEXT_PUBLIC_ENABLE_INSPECTOR=0` hides it; production builds never load it.

## Security

- **Repository analysis**: https only, host allowlist (`REPO_ALLOWED_HOSTS`, no IPs, no
  localhost), no credentials in URLs; tokens travel as a git `http.extraheader` through the
  process environment, never on disk. Clones are shallow, single-branch, without submodules,
  with `GIT_TERMINAL_PROMPT=0`, killed after `REPO_CLONE_TIMEOUT_S`, capped by
  `REPO_MAX_SIZE_MB` / `REPO_MAX_FILES`, and removed afterwards. Repository code is read,
  never executed. Every error message is passed through `redact_secrets` before it reaches a
  log or the UI.
- **Agent endpoint**: per-client sliding-window rate limit on `POST /agent`
  (`AGENT_RATE_LIMIT`); CORS restricted to `FRONTEND_ORIGIN`; `X-Content-Type-Options`,
  `Referrer-Policy` and `Cache-Control: no-store` on every response.
- **Frontend**: a Content-Security-Policy from `next.config.ts` (`default-src 'self'`,
  `frame-ancestors 'none'`; the Inspector's CDN hosts are allowed only outside production),
  `X-Frame-Options: DENY`. The browser only ever talks to its own origin: `/api/copilotkit`
  and `/api/backend/*`.
- **Model output** never becomes markup: the agent can only call `render_ui` with catalog
  components, and the runtime validates every operation server-side.
- Containers run as non-root users.

## Agent-based risk review

`make risk-review` runs two Google ADK agents on the same local model as the app: a
**lane reviewer** that traces one risk lane (model output to state, logging and redaction,
repository analysis, API and persistence, export rendering, frontend trust) from sources to
sinks with read-only tools, and a **finding verifier** that tries to disprove each finding.
Findings must cite lines that exist; the reporting tool checks every quote against the file.
Reports, with token, request and latency counts per lane, land in `reports/risk-review/`.
`make eval-risk-review` scores the reviewer on a planted-defect fixture for recall, precision,
decoy false positives, grounding, latency and tokens against `backend/evals/risk_review/baselines/`.
Layout and conventions: `backend/risk_review/README.md`; Claude skill: `/risk-review`.

## How-to: add a question (≈20 minutes)

Example: ask whether the system is also deployed outside the EU, as a yes/no question in the
Project section, asked only when the project uses AI.

1. **Schema** (skip if the field already exists). Add the leaf to the right section model in
   `backend/app/intake/schema.py`:

   ```python
   class Project(BaseModel):
       ...
       deployed_outside_eu: FieldMeta[bool] = Field(default_factory=FieldMeta[bool])
   ```

2. **Question bank.** Append a `QuestionSpec` to `QUESTION_BANK` in
   `backend/app/intake/question_bank.py`. `priority` orders it within its section; `gate`
   skips it while the gate field is unanswered, `unknown` or holds another value;
   `must_confirm=True` forces a chip to be confirmed however confident the model is;
   `why_asked` is shown under sensitive questions.

   ```python
   QuestionSpec(
       field="project.deployed_outside_eu",
       section=Section.PROJECT,
       label="Deployed outside the EU",
       prompt="Is the system also used outside the European Union?",
       control="yes_no",
       gate=USES_AI,                     # Gate(field="ai_system.uses_ai", values=[True])
       must_confirm=True,                # a chip is never auto-accepted for this field
       why_asked="Deployment outside the EU can bring other AI and privacy laws into scope.",
       sensitive=True,
       priority=18,
   ),
   ```

   That one entry drives the gap analysis, the review page order, the PDF form, the
   extraction tool schema (`structured_extraction.extraction_tool_schema` builds one property
   per spec) and the render plan. Add a phrase to `FIELD_HINTS` in
   `backend/app/inference/structured_extraction.py` if the live model needs guidance.

3. **Regenerate the contract**: `make export-schema` rewrites `schema/intake.schema.json`
   and `frontend/lib/intakeTypes.ts`. Commit both; `make check-schema` (and CI) fail
   otherwise.

4. **Frontend label.** Add the matching entry to `FIELD_SPECS` in `frontend/lib/fieldCatalog.ts`
   so chips, the progress rail and the review page know the field:

   ```ts
   spec({
     field: "project.deployed_outside_eu",
     section: "project",
     label: "Deployed outside the EU",
     prompt: "Is the system also used outside the European Union?",
     control: "yes_no",
     mustConfirm: true,
     sensitive: true,
     whyAsked: "Deployment outside the EU can bring other AI and privacy laws into scope.",
   }),
   ```

5. **Test the gap analysis** in `backend/tests/intake/test_gap_analysis.py`:

   ```python
   def test_deployed_outside_eu_is_gated_on_uses_ai() -> None:
       record = new_record("t")
       spec = spec_for("project.deployed_outside_eu")
       assert field_status(record, spec) is FieldStatus.SKIPPED      # gate unanswered
       record.set_field("ai_system.uses_ai", True, source="user", confidence=1.0, confirmed=True)
       assert field_status(record, spec) is FieldStatus.MISSING
       record.set_field(
           "project.deployed_outside_eu", True, source="inferred", confidence=0.95, confirmed=False
       )
       assert field_status(record, spec) is FieldStatus.NEEDS_CONFIRMATION  # must_confirm
   ```

6. **Mock mode.** `ScriptedLlm` answers from `backend/app/intake/heuristic_extractor.py`.
   Add a rule there so the mock suite exercises the new field:

   ```python
   if _has(text, r"outside the EU", r"\bUS\b", r"global"):
       add("project.deployed_outside_eu", True, 0.85, "mentions non-EU deployment")
   ```

7. If the answer should change the classification, add a rule row or a framework
   obligation (next how-to). Run `make lint typecheck test check-schema`.

## How-to: add a framework module (≈25 minutes)

Framework modules are plain Python modules that satisfy the `FrameworkModule` protocol in
`backend/app/governance/frameworks/base.py`: a `name` and a pure
`evaluate(record, eu) -> FrameworkResult`. They run after the EU AI Act table and can add
obligations, next steps, extra framework names and a tier floor; they never persist anything.

1. **Create** `backend/app/governance/frameworks/local_ai_policy.py`:

   ```python
   """Example local policy: logging and explainability for consumer-facing systems."""

   from __future__ import annotations

   from app.governance.field_values import equals, is_true
   from app.governance.frameworks.base import NOT_APPLICABLE, FrameworkResult
   from app.intake.schema import EuAiActAssessment, IntakeRecord, Obligation, RiskTier, TargetUsers

   name = "Local AI policy"

   TARGET_USERS = "project.target_users"
   INTERACTS = "use_case.interacts_directly_with_people"


   def _obligation(text: str, reference: str) -> Obligation:
       return Obligation(framework=name, text=text, reference=reference, role=None)


   def evaluate(record: IntakeRecord, eu: EuAiActAssessment) -> FrameworkResult:
       if not equals(record, TARGET_USERS, TargetUsers.PUBLIC):
           return NOT_APPLICABLE
       obligations = [_obligation("Keep decision logs for 12 months", "Local AI policy §3")]
       if is_true(record, INTERACTS):
           obligations.append(
               _obligation("Offer a plain-language explanation on request", "Local AI policy §4")
           )
       return FrameworkResult(applies=True, obligations=obligations, tier_floor=RiskTier.MEDIUM)
   ```

   Read field values only through `app/governance/field_values.py` (`is_true`, `is_false`,
   `equals`, `contains_any`, `list_value`, `is_asserted`): they treat `None` and `"unknown"`
   as "not asserted", never as `False`.

2. **Register** it in `backend/app/governance/frameworks/__init__.py`. Order is the order of
   `applicable_frameworks` and `obligations` in the assessment:

   ```python
   from app.governance.frameworks import gdpr, internal_policy, iso_42001, local_ai_policy, nist_ai_rmf

   FRAMEWORK_MODULES: list[FrameworkModule] = [gdpr, nist_ai_rmf, iso_42001, internal_policy, local_ai_policy]
   ```

3. **Test every branch** in `backend/tests/governance/test_frameworks.py`: one test for
   "does not apply", one per obligation, one for the tier floor. The governance package has a
   **100 % branch-coverage gate**, so an untested `if` fails `make test-backend`.

   ```python
   from app.governance.frameworks import local_ai_policy


   # `make_record` (tests/conftest.py) sets each path as a confirmed user answer.
   def test_local_policy_not_applicable_for_internal_users(make_record: RecordFactory) -> None:
       record = make_record({"project.target_users": "internal"})
       assert local_ai_policy.evaluate(record, MINIMAL_EU) == NOT_APPLICABLE


   def test_local_policy_logging_obligation_and_floor(make_record: RecordFactory) -> None:
       result = local_ai_policy.evaluate(make_record({"project.target_users": "public"}), MINIMAL_EU)
       assert "Keep decision logs for 12 months" in texts(result)
       assert result.tier_floor is RiskTier.MEDIUM


   def test_local_policy_explanation_when_interactive(make_record: RecordFactory) -> None:
       record = make_record(
           {"project.target_users": "public", "use_case.interacts_directly_with_people": True}
       )
       result = local_ai_policy.evaluate(record, MINIMAL_EU)
       assert "Offer a plain-language explanation on request" in texts(result)
   ```

   Also update `test_registry_order_and_names` (the registry list) and any assertion on
   `applicable_frameworks` in `tests/governance/test_classify.py` that the new module changes.

4. Nothing else is needed: `classify()` merges obligations (de-duplicated by framework +
   text), raises the overall tier to the highest floor, and the review page, JSON export and
   PDF render whatever the assessment contains. Run `make test-backend`.

## Extension points

- **SSO prefill**: `owner_from_request` in `backend/app/api/intakes.py` reads
  `X-Forwarded-User`, `X-Forwarded-Email` or `X-Auth-Request-Email` (the Next.js proxy and
  the AG-UI endpoint forward them), else `DEFAULT_OWNER`. Add your proxy's header there.
- **Webhook**: `submit_intake` in `backend/app/api/exports.py` posts the JSON export to
  `INTAKE_WEBHOOK_URL` through `app/export/webhook.py`; replace the delivery function to
  integrate a ticketing system.
- **Postgres**: set `DATABASE_URL=postgresql+psycopg://…` and add the driver to
  `backend/pyproject.toml`; persistence is SQLModel in `app/intake/intake_store.py`.
- **Additional repository hosts**: extend `REPO_ALLOWED_HOSTS`; for a host with a different
  URL shape adjust `validate_repository_url` in `app/repo_analysis/clone_repository.py`.
  Fixture repositories for offline runs are listed in `FIXTURE_REPOSITORIES`.
- **Local privacy law**: `gdpr.set_local_privacy_law_name("…")` (constant
  `LOCAL_PRIVACY_LAW_NAME` in `app/governance/frameworks/gdpr.py`) lists the law next to the
  GDPR and adds a check-its-requirements obligation; the placeholder is never shown.
- **Inference provider**: add a branch in `app/inference/model_factory.py`; the agent and
  the extractor share it.

## Out of scope

- Authentication and authorisation: the app expects an SSO proxy in front of it and only
  reads its headers.
- Legal advice: the rule table is a conservative reading of the EU AI Act meant as a starting
  point; every classification must be confirmed by qualified counsel.
- Executing or building analysed repositories; only manifests, docs and code signals are read.
- Multi-tenant storage, audit trails beyond the record's provenance, and document ingestion
  (uploaded DPIAs, model cards).
- Production Bedrock credentials management; the standard AWS credential chain is assumed.

## Known limitations

- **Repository-analysis progress streams over REST SSE** (`GET /repositories/analyze/{job}/events`),
  not over AG-UI state events. An ADK `FunctionTool` can only emit a state delta when it
  returns, so mid-analysis progress cannot stream through the agent run; the job also mirrors
  its last line into `meta.analysis_progress` and the agent run starts after it finishes.
- **CopilotKit generative UI / A2UI is marked experimental upstream** (`@copilotkit/react-core/v2/generative-ui`,
  `@copilotkit/runtime/v2`, CopilotKit 1.84.0). The catalog and runtime wiring are isolated in
  `frontend/generative-ui/` and `app/api/copilotkit/` so an upstream change stays local.
- `MOCK_MODEL=1` extraction is keyword based; it is meant to exercise the UI and the rules
  engine deterministically, not to reproduce the live model's judgement.
- The frontend Docker image is not standalone (see "Running locally").
