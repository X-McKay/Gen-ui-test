import { expect, test } from "@playwright/test";

import { fieldValue, getFindingsCount, getRecord } from "./fixtures/api";
import { DISALLOWED_HOST_MESSAGE, DISALLOWED_REPOSITORY_URL, FIXTURE_REPOSITORIES } from "./fixtures/descriptions";
import { readWatch, watchDom } from "./fixtures/dom-watch";
import { BOUNDS, LIVE } from "./fixtures/live";
import { paceEventSource } from "./fixtures/pacing";
import { ExistingProjectPage } from "./pages";

const DOMAINS_FIELD = "use_case.domains";

test.describe("existing project", () => {
  test("a disallowed host shows an inline error and blocks analysis", async ({ page }) => {
    const flow = new ExistingProjectPage(page);
    await flow.goto();
    await flow.enterUrl(DISALLOWED_REPOSITORY_URL);
    await expect(flow.urlError).toHaveText(DISALLOWED_HOST_MESSAGE);
    await expect(flow.urlError).toHaveAttribute("role", "alert");
    await expect(flow.url).toHaveAttribute("aria-invalid", "true");
    await expect(flow.analyzeButton).toBeDisabled();
  });

  test("the fixture repository streams progress, shows findings, and one correction changes the classification", async ({
    page,
    request,
  }) => {
    await paceEventSource(page);
    await watchDom(page);
    const flow = new ExistingProjectPage(page);
    await flow.goto();
    const intakeId = await flow.analyze(FIXTURE_REPOSITORIES.hrScreening);

    // Progress streamed line by line before the findings replaced it.
    const watched = await readWatch(page);
    expect(watched.logLines.length, watched.logLines.join(" | ")).toBeGreaterThanOrEqual(2);

    // Findings: enough rows, every one with evidence, matching what the API stored.
    const rowCount = await flow.rows.count();
    expect(rowCount).toBeGreaterThanOrEqual(BOUNDS.minFindings);
    const withEvidence = await page
      .locator('[data-testid="finding-row"]:has([data-testid="evidence-snippet"])')
      .count();
    expect(withEvidence).toBe(rowCount);
    if (!LIVE) expect(rowCount).toBe(await getFindingsCount(request, intakeId));
    await expect(flow.row(DOMAINS_FIELD)).toBeVisible();
    await expect(flow.interview.confirm).toBeEnabled();

    // Correct exactly one row inline: the domains are not HR after all.
    await flow.correctRow(DOMAINS_FIELD, { select: ["None of these"], unselect: ["HR and employment"] });
    expect(await page.locator('[data-testid="finding-row"][data-state="corrected"]').count()).toBe(1);

    const next = await flow.confirmFindings();
    expect(next.kind).toBe("step");
    const run = await flow.completeGapQuestions();

    const record = await getRecord(request, intakeId);
    expect(fieldValue(record, DOMAINS_FIELD)).toEqual(["other"]);
    expect(record.assessment.eu_ai_act.classification).not.toBe("high_risk");
    const classification = await run.review.classificationValue();
    expect(classification).not.toBe("high_risk");
    expect(classification).toBe(record.assessment.eu_ai_act.classification);
    await expect(run.review.mode).toHaveAttribute("data-mode", "existing");
    await expect(run.review.repoUrl).toBeVisible();
    await expect(run.review.repoUrl).toHaveAttribute("href", FIXTURE_REPOSITORIES.hrScreening);
    await expect(run.review.repoUrl).toContainText("intake-fixtures/hr-screening");
    expect(record.meta.repo_url).toBe(FIXTURE_REPOSITORIES.hrScreening);
    expect(record.meta.mode).toBe("existing");
  });

  test("confirming every finding without corrections keeps the high-risk classification", async ({ page, request }) => {
    const flow = new ExistingProjectPage(page);
    await flow.goto();
    const intakeId = await flow.analyze(FIXTURE_REPOSITORIES.hrScreening);
    expect(await flow.rows.count()).toBeGreaterThanOrEqual(BOUNDS.minFindings);
    expect(await page.locator('[data-testid="finding-row"][data-state="corrected"]').count()).toBe(0);

    await flow.confirmFindings();
    const run = await flow.completeGapQuestions();

    const record = await getRecord(request, intakeId);
    expect(fieldValue(record, DOMAINS_FIELD)).toContain("hr_employment");
    await expect(run.review.classification).toHaveAttribute("data-classification", "high_risk");
    expect(record.assessment.eu_ai_act.classification).toBe("high_risk");
    await expect(run.review.mode).toHaveAttribute("data-mode", "existing");
  });
});
