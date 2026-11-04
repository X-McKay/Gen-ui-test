# PLAN — AI Governance Intake (Generative UI)

Working name **Intake**. Replaces a static questionnaire with an adaptive, agent-driven
interview that produces an `IntakeRecord` (JSON with provenance) and a PDF form, classified
by a deterministic rules engine (EU AI Act first; GDPR, NIST AI RMF, ISO/IEC 42001 and an
internal-policy module pluggable).

Date: 2026-11-03. Everything below was checked against the installed packages and the
current docs on that date (see "Library verification").

## 1. Decisions and assumptions

| Topic | Decision | Why |
| --- | --- | --- |
| Inference endpoint | `https://llm.almckay.io/v1`, vLLM 0.30.0. `GET /v1/models` returns exactly one model: **`Qwen3.6-35B-A3B-NVFP4`** (131k context). Default `MODEL_ID=openai/Qwen3.6-35B-A3B-NVFP4`, overridable. | Prompt requirement. The endpoint answered without an API key during development; `OPENAI_API_KEY` is still read from env and sent when set. Tool calling verified with a live request (`finish_reason: tool_calls`). The model emits `reasoning` content; the agent prompt keeps replies short. |
| Agent–UI runtime | CopilotKit **1.84.0** `@copilotkit/react-core/v2` + `/v2/generative-ui` (`createGenerativeUI`, `GenerativeUISurface`) and `@copilotkit/runtime/v2` (`CopilotRuntime`, `createCopilotRuntimeHandler`, `HttpAgent`). Tool transport: the runtime injects a `render_ui` tool and a "Generative UI guide" context entry into every AG-UI run and validates every A2UI 1.0 operation server-side. | Primary path from the prompt exists in the installed version; the `@copilotkit/a2ui-renderer` fallback is not needed. |
| Agent | Google ADK **2.13.0** `LlmAgent` served by `ag_ui_adk` **0.12.0** (`ADKAgent`, `add_adk_fastapi_endpoint`) on FastAPI. Frontend tools (including `render_ui`) arrive as long-running client proxy tools, so **each surface render ends the run**; the next user action (one confirm button) starts the next run with the tool result and the action message. | Matches "one surface per step". |
| Model wrapper | ADK `LiteLlm` built only in `backend/app/inference/model_factory.py`. `INFERENCE_PROVIDER=openai_compatible` (default) or `bedrock`. `MOCK_MODEL=1` swaps in `ScriptedLlm`, a deterministic `BaseLlm` that drives the same tools and emits the same `render_ui` calls from fixtures and heuristics. | One factory; CI and Playwright-mock runs never touch the network. |
| Structured extraction | `extract_intake_facts` makes one tool-calling completion (tool schema generated from the Pydantic model) through the same factory. No JSON mode. | Prompt requirement; vLLM-safe. |
| Generative UI guide delivery | `ag_ui_adk` stores AG-UI `context` in session state (`_ag_ui_context`). The agent's instruction provider appends it to the system prompt, so the model sees the `render_ui` guide, targets, components and existing surfaces. | Verified in `ag_ui_adk/adk_agent.py`. |
| Shared state | Tools write `tool_context.state["intake"]` (record + progress); `ag_ui_adk` emits `STATE_DELTA` / `STATE_SNAPSHOT`. The progress rail, assumption strip and review page read it via `useAgent().state`. | Prompt requirement, verified in `event_translator.py`. |
| Repository analysis progress | Clone/inventory/detectors run in a REST job (`POST /repositories/analyze`), progress streamed over SSE (`GET /repositories/analyze/{job_id}/events`) and mirrored into the record (`meta.analysis_progress`). The agent run starts after the job finishes and renders `FindingsReview`. | **Deviation, stated:** an ADK `FunctionTool` can only emit a state delta when it returns, so mid-analysis progress cannot stream through AG-UI state events. The user still sees "Scanning 412 files…" live. |
| Surface lifecycle | One target `interview`. Each step gets `surfaceId = step-<n>`; the agent deletes the previous step surface and creates the next in the same `render_ui` call. `get_next_questions` returns `surface_id`, `previous_surface_id` and a `render_plan` (ready-made operations). The model calls `render_ui` with `operations=[]` and an `after_model_callback` substitutes the plan (or restores it when the model copied it and changed more than the intro). | Keeps the live model reliable and fast (no multi-kilobyte plan to regenerate); the server still validates everything. |
| Inherent and residual risk | Two deterministic point tables in `governance/risk_profile.py`, computed with every `classify`. **Inherent** scores the use case as described in four categories (exposure, autonomy, data, impact) with a floor from the EU AI Act classification. **Residual** removes points per confirmed control (`controls.in_place`, plus `ai_system.human_oversight`), capped per category, with a legal floor (prohibited stays critical; Annex III stays at least medium). A control the model inferred but the owner has not confirmed is listed as "claimed, not confirmed" and removes nothing. Drivers and mitigations are tagged with enterprise lenses (data privacy, information security, operational, financial, reputational, regulatory) and `assessment.risk_lenses` holds one inherent/residual pair per lens. The controls question is one multi-select, asked only when inherent risk is medium or above. | An externally facing chatbot is high inherent risk; with confirmed guardrails, disclosure, monitoring and redaction it is low residual risk. Keeping both visible stops controls from hiding exposure, and the confirmed-only rule stops an optimistic description from talking the risk down. |
| Repository risk assessment | `python -m risk_review assess --repo PATH|URL`: fact-finder agents (prompt + lane skill + `repo-read` and `record_facts` tools) establish facts with evidence; the record is built from the facts and the rules engine does the rest. Evaluated with the same scorer as description extraction (`evals/intake_assessment`, suite `repos`). | The user asked for an agentic process over an arbitrary repository that yields a fact-based assessment across privacy, security, operational, financial, reputational and regulatory lenses. Facts are the one thing a model is good at finding in code; grounding them in code keeps the assessment auditable. |
| Question count | `meta.question_count` increments once per question the user is shown (not per surface). Target ≤ 8 typical, ≤ 15 high-risk. | Prompt requirement. |
| Persistence | SQLite via SQLModel (`DATABASE_URL`, Postgres by connection string). One row per intake: record JSON, status, current step JSON, thread id. Tools load/save by thread id (= intake id). | Resumable after backend restart. |
| Resume | URL carries the intake id; reload fetches the record and asks the agent to "resume" which re-renders the current step from the stored step spec. Unsubmitted selections are kept in `localStorage` per intake and step. | Prompt requirement. |
| Catalog | Own catalog `intake/interview@1`, **8 components**, no standard catalog (`extends` is not used, so nothing needs `omit`; the prompt stays ~1.5k tokens). | Catalog discipline. |
| Frontend stack | Next.js 16 (App Router), React 19, TypeScript strict, Tailwind v4, shadcn/ui (new-york), Geist, zod 4. | Reference architecture. |
| Browsers | chromium, firefox, webkit, mobile-chrome (Pixel 7). | Prompt requirement. |
| SSO prefill | `project.owner` prefilled from `X-Forwarded-User` / `X-Forwarded-Email` when present (header passthrough), else `DEFAULT_OWNER` env. | Extension point. |
| Webhook | `INTAKE_WEBHOOK_URL` optional; Submit posts the JSON export; unset → Submit marks the intake submitted locally and says so. | Prompt placeholder. |
| Sample repository | `https://github.com/ag-ui-protocol/ag-ui` is not a product; the existing-project e2e uses the bundled fixture repo served from the backend (`file://` is blocked; the fixture is exposed as a tiny git HTTP export at `/fixtures/sample-repo.git` under `MOCK_MODEL=1`) and the live walkthrough uses `https://github.com/CopilotKit/CopilotKit` (public, large but shallow-cloneable). | Deterministic e2e. |

## 2. Directory tree

```text
.
├── README.md · CLAUDE.md · Makefile · docker-compose.yml · .env.example · .mise.toml · .pre-commit-config.yaml
├── docs/{PLAN.md, DEMO.md, screenshots/, claude-code-settings.json}
├── .claude/{skills/, hooks/}                  # add-question, add-framework, verify, e2e-debug; format + staging-guard hooks
├── schema/intake.schema.json                 # generated from Pydantic (make export-schema); CI fails if stale
├── backend/
│   ├── pyproject.toml                        # uv, ruff, mypy --strict, pytest, 100 % coverage gate on governance/
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py                           # FastAPI; /agent (AG-UI), /healthz, REST routers, CSP, rate limit, request-id logs
│   │   ├── settings.py                       # pydantic-settings; fail-fast validation
│   │   ├── logging_config.py                 # structured JSON logs, token redaction
│   │   ├── agents/
│   │   │   ├── intake_agent.py               # LlmAgent + ADKAgent wiring, instruction provider
│   │   │   ├── prompts/intake_instruction.md
│   │   │   └── tools/{extract_intake_facts,update_intake_fields,get_next_questions,finalize_intake}.py
│   │   ├── inference/
│   │   │   ├── model_factory.py              # LiteLlm (openai_compatible | bedrock) or ScriptedLlm
│   │   │   ├── mock_model.py                 # ScriptedLlm(BaseLlm): deterministic replay
│   │   │   └── structured_extraction.py      # tool-calling extraction shared by both providers
│   │   ├── intake/
│   │   │   ├── schema.py                     # FieldMeta, IntakeRecord, enums, UNKNOWN
│   │   │   ├── question_bank.py              # field → prompt, control, options, section, gates, must_confirm, why_asked
│   │   │   ├── gap_analysis.py               # required-field gaps, gates, ≤3 question specs, completion rule
│   │   │   ├── heuristic_extractor.py        # keyword extractor used by MOCK_MODEL and as a prior
│   │   │   ├── record_service.py             # load/save/apply-updates/reclassify
│   │   │   └── intake_store.py                 # SQLModel persistence
│   │   ├── governance/
│   │   │   ├── classify.py                   # aggregates modules into `assessment`
│   │   │   ├── eu_ai_act.py                  # rule table with article citations
│   │   │   └── frameworks/{gdpr,nist_ai_rmf,iso_42001,internal_policy}.py
│   │   ├── repo_analysis/{clone_repository,inventory,signal_detectors,summarize_findings,analysis_job}.py
│   │   ├── export/{json_export,pdf_export}.py · templates/intake_form.html
│   │   └── api/{intakes,exports,repositories,health}.py
│   └── tests/                                # mirrors app/; fixtures/{descriptions,repos,model_replies}
└── frontend/
    ├── package.json · next.config.ts · playwright.config.ts · vitest.config.ts · eslint.config.mjs
    ├── app/{page.tsx, layout.tsx, globals.css, intake/new/page.tsx, intake/existing/page.tsx,
    │        intake/[intakeId]/review/page.tsx, api/copilotkit/route.ts}
    ├── components/{landing,intake,review,repo,ui}/…
    ├── generative-ui/intakeCatalog.ts · components/{InterviewStep,AssumptionReview,ChoiceQuestion,
    │        MultiSelectQuestion,YesNoQuestion,ShortTextQuestion,FindingsReview,EscalationNotice}.tsx
    ├── lib/{apiClient.ts, intakeTypes.ts (generated), formatters.ts, intakeState.ts}
    └── e2e/{pages,fixtures,*.spec.ts, global-setup.ts}
```

## 3. Data model

Every leaf is `FieldMeta`: `{ value, confidence: 0–1, source: "user" | "inferred" | "repo:<path>", confirmed: bool }`.
`value` may be the literal string `"unknown"` for any field (distinct from `false` and from `null`).

Sections and fields follow the prompt table exactly (`meta`, `project`, `ai_system`, `data`,
`use_case`, `controls`, `assessment`). `assessment` is derived by `governance/classify.py` on every change and
is read-only for both LLM and user. Each `rationale` entry is
`{ field, value, article, text }` so the review page links tier → answer.
`assessment.inherent_risk` and `assessment.residual_risk` are `RiskProfile`
`{ tier, score, drivers[{field, value, category, points, text}], controls[{field, control, status, points, text}], floor, floor_reason }`;
`controls.in_place` is the one answer that feeds the residual, and only when confirmed.

Required fields (gap analysis) and the must-confirm list live in `question_bank.py`:

- Gates (asked first, in order): `ai_system.uses_ai`, `data.processes_personal_data`, `use_case.domains`, `use_case.affects_legal_or_significant_effects`.
- Must confirm regardless of confidence: `data.biometric_identification`, `data.special_category_data`, `data.data_subjects` when it contains `minors`, every Annex III entry in `use_case.domains`, `use_case.social_scoring`, `use_case.emotion_recognition`, `use_case.remote_biometric_id_public_spaces`, `use_case.generates_synthetic_content` is **not** must-confirm.
- Negative gates skip their section: `uses_ai=false` skips `ai_system.*` details and all `use_case` AI signals; `processes_personal_data=false` skips `pii_categories`, `special_category_data`, `data_subjects`, `trains_on_personal_data`, `retention_policy`, `cross_border_transfer`, `biometric_identification`.

Completion rule: every required field is `confirmed`, or inferred at ≥ 0.8 and not must-confirm, or `unknown` (which lands in `assessment.open_questions`).

## 4. Catalog (`intake/interview@1`) — 8 components

| Component | Conversational move | Key props | Event |
| --- | --- | --- | --- |
| `InterviewStep` (root) | "Here is one step" | `intro` (≤ 2 sentences), `section`, slots `assumptions` (single), `questions` (multiple), `confirmLabel` | `onSubmit({ assumptions: {field: value}, answers: {field: value}, notSure: [field] })` |
| `AssumptionReview` | "Does this look right?" | `assumptions[]: { field, label, value, displayValue, confidence, source }` | — (values collected by the step) |
| `ChoiceQuestion` | "Pick one" (segmented) | `field, prompt, options[{value,label}], whyAsked?, required?` | — |
| `MultiSelectQuestion` | "Pick any" (chips) | `field, prompt, options[], whyAsked?, minSelected?` | — |
| `YesNoQuestion` | "Yes / No / Not sure" | `field, prompt, whyAsked?` | — |
| `ShortTextQuestion` | "Type a short answer" | `field, prompt, placeholder?, checks? {required, minLength, maxLength, pattern}` | — |
| `FindingsReview` | "Confirm what we found in the repository" | `findings[]: { field, label, value, displayValue, confidence, evidencePath, snippet }` | — (values collected by the step) |
| `EscalationNotice` | "Stop: prohibited practice" | `title, reasons[], contact` | `onAcknowledge()` |

Every component carries `data-testid` = component name and every control an `aria-label`.
Client-side checks disable the confirm button until satisfied; "Not sure" is always available
and stores `"unknown"`.

## 5. Agent tools (the only way to change the record)

| Tool | Server behaviour |
| --- | --- |
| `extract_intake_facts(text)` | One structured extraction call; merges fields with `source: inferred` and the model's confidence; reclassifies; stores. Returns the inferred fields and the assumption chips (≥ 0.8). |
| `update_intake_fields(fields)` | `fields: [{ path, value, confirmed }]` from the user's action; sets `source: user`, `confirmed: true`; `"unknown"` allowed; reclassifies; increments nothing. |
| `get_next_questions()` | Gap analysis + gates → ≤ 3 question specs, plus `surface_id`, `previous_surface_id`, `assumptions_to_confirm`, `render_plan`, `section_progress`. Increments `question_count` by the number of questions returned. Returns `done: true` when nothing is left. |
| `finalize_intake()` | Sets `completed_at`, status `completed`, returns the review URL. |

## 6. REST API

`POST /intakes` (create, mode, owner prefill) · `GET /intakes/{id}` · `PATCH /intakes/{id}/fields` (inline edit → reclassify) ·
`GET /intakes/{id}/export.json` · `GET /intakes/{id}/export.pdf` · `POST /intakes/{id}/submit` ·
`POST /repositories/analyze` · `GET /repositories/analyze/{job}/events` (SSE) · `GET /healthz` · `POST /agent` (AG-UI).

## 7. Playwright test plan (`frontend/e2e/`)

Projects: `chromium`, `firefox`, `webkit`, `mobile-chrome` (Pixel 7); `colorScheme` light/dark variants for landing and review. `baseURL` from `E2E_BASE_URL`. `trace: on-first-retry`, screenshot + video on failure, `retries: 2` in CI. Global setup waits for `/healthz` on both apps, seeds the DB with fixture intakes, and in live mode asks the model for one token.

| Spec | Asserts (structure and data only; selectors are `data-testid` / `aria-label`) |
| --- | --- |
| `landing.spec.ts` | two cards side by side at 1280, stacked at 390; Tab+Enter reach both routes; focus ring visible; light/dark screenshots |
| `new-project.spec.ts` | HR screening: chips before any question, ≤ 8 questions, Not sure → `unknown` in export, review shows `high_risk` + employment rationale; log search: ≤ 4 questions, `minimal`; JSON validates against `schema/intake.schema.json`; PDF download fires |
| `existing-project.spec.ts` | disallowed host inline error; progress text streams; ≥ 5 findings with evidence paths; bulk confirm; one inline correction flips classification; gap questions only; review has `mode: existing` + URL |
| `interview-controls.spec.ts` | every catalog component round-trips; checks keep confirm disabled; editing a confirmed chip reopens the question |
| `resume.spec.ts` | reload mid-interview and fresh context restore step and values |
| `agent-guardrails.spec.ts` | fixture `[[fixture:invalid-component]]` → invalid component never renders, surface self-corrects; ≤ 2 sentences agent text; no raw JSON outside export |
| `accessibility.spec.ts` | axe on landing, each surface, findings table, review: no critical/serious; both flows by keyboard |
| `visual.spec.ts` | `toHaveScreenshot` baselines, light/dark, desktop/mobile |

Targets: `make e2e` (mock), `make e2e-live`, `make e2e-ui`. CI: mock suite per PR; live suite nightly.

## 8. Library verification (3 Nov 2026)

- `@copilotkit/react-core@1.84.0` exports `/v2/generative-ui`: `createGenerativeUI`, `GenerativeUISurface`, `useGenerativeUIState`, `standardUI`, `exportA2UICatalog`; props schemas may be zod 3 or zod ≥ 4.2.
- `@copilotkit/runtime@1.84.0` `/v2`: `CopilotRuntime({ agents, generativeUI })`, `createCopilotRuntimeHandler({ runtime, basePath })`, `GenerativeUIMiddleware` (validates `render_ui` operations, emits tool results with `rejected[]` for self-correction).
- Component events without a matching function are forwarded as a user message (`buildActionMessageText`: first line + `key: value` lines, objects as JSON) plus `forwardedProps.copilotkit.ui.metadata.extensions.copilotkit_action`.
- `ag-ui-adk==0.12.0`: `ADKAgent(adk_agent, app_name, user_id, use_in_memory_services)`, `add_adk_fastapi_endpoint(app, agent, path, extract_headers)`, context in state under `CONTEXT_STATE_KEY`, state deltas from `event.actions.state_delta`.
- `google-adk==2.13.0`: `LiteLlm(model, **kwargs)` forwards kwargs (`api_base`, `api_key`) to `litellm`; `BaseLlm.generate_content_async(llm_request, stream)` is the mock seam; `FunctionTool` wraps plain functions with an optional `tool_context: ToolContext`.
- `litellm==1.106.6`, `fastapi==0.162.0`, `sqlmodel==0.0.48`, `weasyprint==70.0` (pango present on this host), `gitpython==3.2.1`, `pydantic-settings==2.16.2`.
- Playwright `1.64.1`, `@axe-core/playwright 4.14.0`, Next.js `16.4.4`.
