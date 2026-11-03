# AI Governance Intake — working agreement for Claude Code

Read this first; it is the contract the tests enforce. Details live in `README.md`
(architecture, configuration, how-tos) and `docs/PLAN.md` (design decisions).

## Layout

| Path | What lives there |
| --- | --- |
| `backend/app/agents/` | Google ADK `LlmAgent` + `ag_ui_adk` wiring, the four tools, `render_repair`, `surface_plan` |
| `backend/app/governance/` | Deterministic rules engine: EU AI Act table + framework modules. **100 % branch coverage gate.** |
| `backend/app/intake/` | `schema.py` (IntakeRecord, FieldMeta), `question_bank.py`, `gap_analysis.py`, `intake_store.py` (SQLite) |
| `backend/app/inference/` | LiteLLM factory, `ScriptedLlm` mock, tool-calling extraction |
| `backend/app/repo_analysis/` | Clone (allowlisted, shallow, capped), inventory, signal detectors, summariser |
| `backend/app/export/` | JSON export, WeasyPrint PDF, webhook |
| `backend/fixtures/repos/` | The two fixture repositories served outside production |
| `frontend/generative-ui/` | The A2UI catalog (≤ 8 components) and the step form state |
| `frontend/components/` | Review page, landing, repo form, theme, shadcn `ui/` |
| `frontend/lib/` | `fieldCatalog.ts` (field specs, labels, controls), API client, generated `intakeTypes.ts` |
| `frontend/e2e/` | Playwright specs, page objects, fixtures |
| `schema/intake.schema.json` | Generated from the Pydantic model; CI fails when stale |

## Commands

```sh
make setup                      # first time: install, env files, pre-commit hooks, doctor
make dev-mock                   # both servers, deterministic model, no network
make lint typecheck test        # what CI runs (ruff, mypy --strict, eslint, prettier, tsc, pytest, vitest)
make check-schema               # schema + generated TS types are fresh
make e2e                        # Playwright, mock model, four browser projects
make e2e-live                   # Playwright against the live endpoint
```

Use the Makefile targets rather than ad-hoc commands; they are what CI runs. Run `make
lint typecheck test check-schema` before every commit and the chromium e2e project after any
change under `frontend/generative-ui/`, `frontend/components/intake/` or `backend/app/agents/`.

## Invariants (tests enforce these; do not weaken a test to get around one)

- **Facts from the model, decisions from code.** The model extracts and phrases; the rules
  engine classifies. Never let model output set a tier, an obligation or a field's `confirmed`.
- **Four agent tools only**: `extract_intake_facts`, `update_intake_fields`,
  `get_next_questions`, `finalize_intake`. Rendering is `render_ui` with `operations=[]`; the
  server substitutes the plan (`render_repair.py`). The agent never emits markup or code.
- **Catalog of at most eight components** in `frontend/generative-ui/intakeCatalog.ts`; every
  prop is schema-validated. Adding a component needs a PLAN.md row and a visual baseline.
- **Every record leaf is `FieldMeta {value, confidence, source, confirmed}`**; `"unknown"` is
  legal and is never treated as `False` (`governance/field_values.py`).
- **Question budget**: ≤ 3 questions per step, gates first, ≤ 8 typical, ≤ 15 high-risk.
- **Schema contract**: after touching `intake/schema.py` or `question_bank.py` run
  `make export-schema` and commit `schema/intake.schema.json` and `frontend/lib/intakeTypes.ts`.
- **Governance coverage** stays at 100 % branch coverage; every new `if` needs a test.
- **e2e selectors** are `data-testid`, roles and `aria-label` only; never assert on model
  wording. Mock mode may assert exact counts; `LIVE` runs assert bounds.

## Security rules (from the product brief; non-negotiable)

- Secrets only via environment; `.env.example` documents every variable; nothing secret is
  committed. Never stage `.env`, `*.db` or `.playwright-mcp/`.
- Never log prompt or completion text above DEBUG. Never log the project description or
  repository contents at any level. Tokens are stripped from logs and error messages
  (`redact_secrets`, `logging_config.redact`).
- Repository analysis: allowlisted hosts, https only, shallow clone with size cap and
  timeout, repository code is read and never executed.
- Do not search other local repositories or the home directory for credentials.

## Conventions

- Python: ruff (line length 100), mypy `--strict`, `from __future__ import annotations`,
  module-level functions over classes, descriptive names (`create_intake`, not `create`).
- TypeScript: prettier (print width 120), eslint, no default exports except Next routes,
  tests beside their subject as `*.test.ts(x)`.
- Mobile layout: generative-ui grids use `grid-cols-1` and tables are `table-fixed` below
  `sm`; Android Chrome widens the layout viewport for any wider minimum content and clicks
  then miss (see `/e2e-debug`).
- ag_ui_adk counts every interview waiting on the user as an active execution; keep
  `AGENT_MAX_CONCURRENT_RUNS` above the number of open interviews you expect.

## Skills

`/add-question`, `/add-framework`, `/verify`, `/e2e-debug` in `.claude/skills/`.
