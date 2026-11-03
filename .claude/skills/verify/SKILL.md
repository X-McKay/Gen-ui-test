---
name: verify
description: Run every quality gate the repository has (lint, typecheck, unit tests, schema freshness, build, Playwright) and report the numbers in the format DEMO.md uses. Use before a commit or push, or when asked whether the tree is green.
---

# Verify the tree

Run the gates in this order from the repository root, stop at the first failure, and fix it
before continuing. Use absolute paths; the Playwright config starts its own servers, so make
sure ports 8000 and 3000 are free first (`ss -ltnp | grep -E ':(8000|3000) '`).

```sh
make lint            # ruff format --check, ruff check, eslint, prettier --check
make typecheck       # mypy --strict (backend/app), tsc --noEmit
make test            # pytest with the governance 100 % gate, vitest
make check-schema    # schema/intake.schema.json and frontend/lib/intakeTypes.ts are fresh
make build           # next build
make e2e             # Playwright, MOCK_MODEL=1, chromium + firefox + webkit + mobile-chrome
```

Optional, when the agent prompt, tools or render plan changed:

```sh
make e2e-live PLAYWRIGHT_ARGS="--project=chromium"
```

## Report

Give the user a table with one row per gate and the summary line of each tool, for example:

| Gate | Result |
| --- | --- |
| Backend ruff, format, mypy strict | clean |
| Backend tests | 420 passed, governance at 100 % branch coverage |
| Schema freshness | fresh |
| Frontend tsc, eslint, prettier, vitest | clean, 72 unit tests |
| Production `next build` | passes |
| Playwright mock, four projects | 96 passed, 16 skipped, 0 failed |

State failures with the failing test names and the first error line, never as "some tests
failed". If a gate was skipped, say so and why. Update the acceptance table in
`docs/DEMO.md` when the numbers change.

## Known slow spots

- The first `next dev` compile makes Playwright's first test slow; global setup warms the
  routes. A one-off "Execution context was destroyed" is the dev-server reload, not a bug.
- Visual baselines are chromium and mobile-chrome only; regenerate with
  `pnpm exec playwright test visual --update-snapshots --project=<project>` after looking at
  the diff image under `frontend/test-results/`.
