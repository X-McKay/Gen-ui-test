/** Scenario texts shared by the specs. Keep them byte-identical to the plan. */

export const HR_SCREENING =
  "We are building an internal tool for our recruiting team that drafts job-candidate summaries from uploaded CVs using an LLM via the OpenAI API. Recruiters paste or upload a CV and the tool produces a one-page summary and a suggested fit score for the role.\n\nThe summaries are read by recruiters before they decide who to invite to interview. It is currently a pilot with two hiring teams in the EU. Candidate data is stored in our existing applicant tracking database and deleted after six months.";

export const LOG_SEARCH =
  "An internal log-search assistant for our platform engineers. Engineers ask questions in natural language and the tool translates them into queries over our observability stack and summarises the matching log lines. It uses a self-hosted open-weights LLM. Logs are anonymised before indexing and the tool handles no personal data. It is in production for the infrastructure team only.";

/** Appended to a description, makes the mock agent render a component outside the catalog first. */
export const INVALID_COMPONENT_MARKER = "[[fixture:invalid-component]]";

export const PROJECT_NAME = "Candidate summary assistant";
export const PROJECT_OWNER = "recruiting-platform@example.com";

export const FIXTURE_REPOSITORIES = {
  hrScreening: "https://github.com/intake-fixtures/hr-screening",
  logSearch: "https://github.com/intake-fixtures/log-search",
} as const;

export const DISALLOWED_REPOSITORY_URL = "https://example.com/org/repo";
export const DISALLOWED_HOST_MESSAGE =
  "Host example.com is not allowed. Allowed: github.com, gitlab.com, dev.azure.com";
