---
name: e2e-debug
description: Diagnose failing or flaky Playwright runs in this repository, including mobile-chrome clicks that miss, "Maximum concurrent executions" errors, HTTP 429s, timeouts against the live model and stale visual baselines. Use whenever an e2e spec fails for a reason that is not obviously the code under test.
---

# Debug the Playwright suite

Start from the failure text; each known failure has a known cause here. Run single specs with
`cd frontend && MOCK_MODEL=1 pnpm exec playwright test <spec> --project=<project> --repeat-each=3`
to tell a flake from a bug. Traces and screenshots land in `frontend/test-results/`.

## "intercepts pointer events" or taps landing on neighbours on mobile-chrome

Android Chrome (Playwright `devices["Pixel 7"]`) widens the *layout viewport* to the
document's minimum content width and never shrinks it back, so `window.innerWidth` goes
from 412 to 460+ and every coordinate is off. Diagnose:

```js
// in a page.evaluate on the failing step
({ innerWidth, scrollWidth: document.documentElement.scrollWidth })
```

If `innerWidth` is above 412, find the culprit by hiding children one at a time in a
requestAnimationFrame loop and recording the first `innerWidth` change. Known causes and the
only fixes that worked:

- An auto-layout `<table>` with a min width: use `table-fixed` below `sm` with a `<colgroup>`
  (see `FindingsReview.tsx`). `overflow-x-auto`, `min-w-0` and `contain: inline-size` on a
  wrapper do **not** prevent it.
- Nowrap text inside auto grid tracks: use `grid-cols-1` (minmax(0,1fr)) on every grid
  level and `min-w-0` on the items (see `AssumptionReview.tsx`).

## "Maximum concurrent executions (N) reached"

`ag_ui_adk` keeps a thread in its active set while it has a pending frontend tool call, so
every interview that is showing a step holds a slot until it finishes or goes stale. Count open
interviews, not requests. The app sets `AGENT_MAX_CONCURRENT_RUNS=200`; the redirect to the
review page waits for the final run to finish. Playwright runs at most 4 workers locally.

## HTTP 429 "Too many requests"

All browsers sit behind the Next proxy on one socket address. The limiter keys on the first
`X-Forwarded-For` entry, which the proxy sets; the Playwright config raises
`AGENT_RATE_LIMIT` to `1000/minute`. A 429 in a test means the proxy header forwarding broke.

## Timeouts in `E2E_LIVE=1`

Page objects scale their waits by `LIVE` (`waitForAdvance` 180 s, `settle` 120 s, `analyze`
240 s). The findings step must render in a few seconds because the model sends
`render_ui(operations=[])` and the server substitutes the plan; if it takes 20 s or more the
model is copying findings into the call, so check `render_repair.py` and the instruction in
`backend/app/agents/prompts/intake_instruction.md`. Live runs skip tests that depend on model
wording (`test.skip(LIVE, ...)`); add a skip rather than loosening an assertion.

## Visual baseline mismatches

Look at the diff image first. Regenerate only the affected test and project:

```sh
cd frontend && MOCK_MODEL=1 pnpm exec playwright test visual --update-snapshots --project=chromium -g "<test name>"
```

Baselines exist for chromium and mobile-chrome only; firefox and webkit skip visual tests.

## "Execution context was destroyed"

`next dev` reloads the page once after its cold compile. Global setup warms `/`,
`/intake/new` and `/intake/existing`; the keyboard fixture (`e2e/fixtures/keyboard.ts`)
retries across the reload. Seeing it once at the start of a run is normal.

## Fixture repositories fail to clone

`https://github.com/intake-fixtures/hr-screening` and `.../log-search` are served from
`backend/fixtures/repos/` whenever `ENVIRONMENT != production`. "Authentication failed" on
them means the backend under test runs with `ENVIRONMENT=production`.
