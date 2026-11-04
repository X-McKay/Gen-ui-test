# Risk review samples

Committed samples of the agent-based risk review, the repository risk assessment and their evals, so the shape of the output
can be read without running the model. Live output is git-ignored (`reports/risk-review/`,
`backend/evals/risk_review/experiments/`).

| File | What it is |
| --- | --- |
| `2026-11-04-risk-review.md` | `make risk-review`: six lanes, verifier on, 4 confirmed / 1 refuted / 1 unverified findings in 513 s, 222 model requests, 4.4 M input tokens |
| `2026-11-04-repo-assessment-hr-screening.md` | `make risk-assess REPO=backend/fixtures/repos/hr_screening`: five fact lanes, 37 grounded facts, EU high-risk, inherent high, residual medium if the claimed controls are confirmed, 313 s, 52 requests, 418 k input tokens |
| `2026-11-04-eval-intake-facts.md` | `make eval-intake` facts suite, 27 descriptions x 2 runs, after the vetting round: pass 0.70, field accuracy 0.95, control false positives 0, silent missed risks 0, risk false positives in 6 % of runs (down from 19 %), inherent tier exact 0.83, residual 0.76 (the gap is capped Annex III values that become questions) |
| `2026-11-04-eval-intake-scenarios.md` | `make eval-intake` scenarios suite, 27 new use-case types x 2 runs: pass 0.72 (0.44 unseen), field accuracy 0.95, risk false positives 0, control false positives 0, missed risks in 4 % of runs, inherent tier exact 0.87, residual 0.80 |
| `2026-11-04-eval-intake-repos.md` | `make eval-intake` repos suite: fact-finder agents on the four fixture repositories, field accuracy 0.88, inherent tier exact on all four, residual exact on three, 135 s median and up to 290 s per repository, 0.4–1.1 M input tokens; the disagreements left are one-fact judgment calls that vary between runs |
| `2026-11-04-eval-smoke.md` | `make eval-risk-review` smoke suite, 2 runs per case: recall 1.00, precision 0.89, decoy hit rate 0.12, p50 24 s |

Confirmed findings in the sample that are worth turning into tests before fixing:
`HTTPException(detail=str(error))` in `backend/app/api/exports.py` forwards webhook error
text unredacted; `tool_error` in `backend/app/agents/tools/context.py` logs its message
through `extra`, which the redaction filter does not cover; `ReviewHeader.tsx` renders
`meta.repo_url` as an `href` without a scheme check (unverified in this run, confirmed in an
earlier one). The `guessable-id` finding (12 hex chars of UUID4) is a judgment call.
