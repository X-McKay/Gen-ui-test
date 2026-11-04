# Planted-risk fixture

A miniature copy of the backend layout with **known** defects for the risk-review evals.
Each defect is labelled `# PLANTED <id>` on the offending line; decoys are labelled
`# DECOY <id>` and must not be reported. The dataset cases under `../../datasets/` list the
expected line windows. Keep line numbers stable: append, do not insert.

Secret-looking files (`.env`, `*.db`) are **not** committed; each case lists them under
`planted_files` and the runner writes them into a temporary working copy before the review.
