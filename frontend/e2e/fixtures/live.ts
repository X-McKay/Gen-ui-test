/**
 * `E2E_LIVE=1` runs the suite against the real model. Exact counts and the mock's
 * deterministic step shapes then relax to the bounds the plan guarantees.
 */
export const LIVE = process.env.E2E_LIVE === "1";

export const BOUNDS = {
  /** HR screening: at most this many questions end to end. */
  hrMaxQuestions: 8,
  /** Log search: at most this many questions end to end. */
  logMaxQuestions: 4,
  /** Repository findings: at least this many rows. */
  minFindings: 5,
  /** Most steps an interview may take before the spec gives up. */
  maxSteps: 12,
} as const;
