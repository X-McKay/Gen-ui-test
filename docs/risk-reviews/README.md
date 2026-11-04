# Risk review samples

Committed samples of the agent-based risk review and its evals, so the shape of the output
can be read without running the model. Live output is git-ignored (`reports/risk-review/`,
`backend/evals/risk_review/experiments/`).

| File | What it is |
| --- | --- |
| `2026-11-04-risk-review.md` | `make risk-review`: six lanes, verifier on, 4 confirmed / 1 refuted / 1 unverified findings in 513 s, 222 model requests, 4.4 M input tokens |
| `2026-11-04-eval-smoke.md` | `make eval-risk-review` smoke suite, 2 runs per case: recall 1.00, precision 0.89, decoy hit rate 0.12, p50 24 s |

Confirmed findings in the sample that are worth turning into tests before fixing:
`HTTPException(detail=str(error))` in `backend/app/api/exports.py` forwards webhook error
text unredacted; `tool_error` in `backend/app/agents/tools/context.py` logs its message
through `extra`, which the redaction filter does not cover; `ReviewHeader.tsx` renders
`meta.repo_url` as an `href` without a scheme check (unverified in this run, confirmed in an
earlier one). The `guessable-id` finding (12 hex chars of UUID4) is a judgment call.
