# End-to-end tests

Playwright specs for the intake app, one per row of PLAN.md section 7. Selectors are
`data-testid`, roles with `aria-label`, and `data-*` attributes only; assertions are about
structure and data, never the agent's wording.

## Running

```sh
cd frontend
pnpm e2e                      # starts the mock backend and `next dev`, runs every project
pnpm e2e -- --project=chromium
pnpm e2e:ui                   # Playwright UI mode
pnpm e2e:live                 # E2E_LIVE=1: real model, counts relax to the plan's bounds
```

Environment:

| Variable               | Effect                                                                  |
| ---------------------- | ----------------------------------------------------------------------- |
| `E2E_BASE_URL`         | Frontend origin (default `http://localhost:3000`)                       |
| `E2E_BACKEND_URL`      | Backend origin for health checks (default `http://127.0.0.1:8000`)      |
| `E2E_EXTERNAL_SERVERS` | Set when both servers already run; no `webServer` is started            |
| `E2E_LIVE=1`           | Backend starts with `MOCK_MODEL=0`; global setup asserts `model.ok`     |
| `E2E_PRODUCTION=1`     | Frontend served with `next start` instead of `next dev`                 |
| `E2E_WORKERS`          | Local worker count (default 4; the agent allows 10 concurrent runs)     |

Against servers you started yourself:

```sh
# terminal 1
cd backend && MOCK_MODEL=1 DATABASE_URL=sqlite:////tmp/e2e.db uv run uvicorn app.main:app --port 8000
# terminal 2
cd frontend && BACKEND_URL=http://127.0.0.1:8000 pnpm dev
# terminal 3
cd frontend && E2E_EXTERNAL_SERVERS=1 pnpm e2e -- --project=chromium
```

Visual baselines live in `e2e/visual.spec.ts-snapshots/` and are generated on Chromium
(desktop and Pixel 7) only. Regenerate with `pnpm e2e -- e2e/visual.spec.ts --project=chromium --project=mobile-chrome --update-snapshots`.

## Layout

```
e2e/
  global-setup.ts        health checks, live-model check, one seeded intake (e2e/.state/seed.json)
  fixtures/              scenario texts, REST helpers, schema validator, keyboard, DOM watch, SSE pacing
  pages/                 LandingPage, NewProjectPage, ExistingProjectPage, ReviewPage, InterviewStep, interviewFlow
  *.spec.ts              landing, new-project, existing-project, interview-controls, resume,
                         agent-guardrails, accessibility, visual
```

`e2e/.state/`, `playwright-report/` and `test-results/` are generated; ignore them in git.

## Make targets

The root `Makefile` carries the targets the plan names; `PLAYWRIGHT_ARGS` passes through:

```sh
make e2e                                   # mock model, every project
make e2e PLAYWRIGHT_ARGS="--project=chromium"
make e2e-live                              # E2E_LIVE=1
make e2e-ui                                # Playwright UI mode
```

`frontend/e2e/.state/` (the seed written by global setup) belongs in `.gitignore` next to
`frontend/test-results/` and `frontend/playwright-report/`.
