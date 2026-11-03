import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type TestInfo } from "@playwright/test";

import { FIXTURE_REPOSITORIES, HR_SCREENING, LOG_SEARCH, PROJECT_NAME, PROJECT_OWNER } from "./fixtures/descriptions";
import { waitForHydration } from "./fixtures/hydration";
import { tabUntil } from "./fixtures/keyboard";
import { readSeedState } from "./fixtures/state";
import { ExistingProjectPage, InterviewStepHelper, LandingPage, NewProjectPage, ReviewPage } from "./pages";

/**
 * The CopilotKit inspector (`<cpk-web-inspector>`) only mounts in `next dev` and is not part
 * of the product, so it is left out of the scan. Everything else on the page is checked.
 */
const DEV_ONLY_WIDGETS = ["cpk-web-inspector"];

async function expectNoSeriousViolations(page: Page, testInfo: TestInfo, name: string): Promise<void> {
  let builder = new AxeBuilder({ page });
  for (const selector of DEV_ONLY_WIDGETS) builder = builder.exclude(selector);
  const results = await builder.analyze();
  await testInfo.attach(`axe-${name}`, {
    body: JSON.stringify(results.violations, null, 2),
    contentType: "application/json",
  });
  const serious = results.violations
    .filter((violation) => violation.impact === "critical" || violation.impact === "serious")
    .map(
      (violation) =>
        `${violation.id} (${violation.impact}): ${violation.help} → ${violation.nodes
          .slice(0, 3)
          .map((node) => node.target.join(" "))
          .join(", ")}`,
    );
  expect(serious).toEqual([]);
}

test.describe("accessibility", () => {
  // Scan the settled page: with reduced motion the entrance animations are off, so axe
  // does not measure colours half-way through a fade.
  test.use({ reducedMotion: "reduce" });

  test("landing has no critical or serious axe violations", async ({ page }, testInfo) => {
    await new LandingPage(page).goto();
    await expectNoSeriousViolations(page, testInfo, "landing");
  });

  test("the first interview surface has no critical or serious axe violations", async ({ page }, testInfo) => {
    const flow = new NewProjectPage(page);
    await flow.start({ description: HR_SCREENING, name: PROJECT_NAME, owner: PROJECT_OWNER });
    await flow.interview.settle();
    await expect(flow.interview.step).toBeVisible();
    await expectNoSeriousViolations(page, testInfo, "interview");
  });

  test("the findings table has no critical or serious axe violations", async ({ page }, testInfo) => {
    const flow = new ExistingProjectPage(page);
    await flow.goto();
    await flow.analyze(FIXTURE_REPOSITORIES.hrScreening);
    await expect(flow.findingsTable).toBeVisible();
    await expectNoSeriousViolations(page, testInfo, "findings");
  });

  test("the review page has no critical or serious axe violations", async ({ page }, testInfo) => {
    const review = new ReviewPage(page);
    await review.goto(readSeedState().seededIntakeId);
    await expectNoSeriousViolations(page, testInfo, "review");
  });

  test("the log-search flow completes with the keyboard only", async ({ page }) => {
    await page.goto("/intake/new");
    await waitForHydration(page);
    await tabUntil(page, '[data-testid="project-description"]');
    await page.keyboard.insertText(LOG_SEARCH);
    await tabUntil(page, '[data-testid="project-name"]');
    await page.keyboard.type("Log search assistant");
    await tabUntil(page, '[data-testid="project-owner"]');
    await page.keyboard.type(PROJECT_OWNER);
    await tabUntil(page, '[data-testid="analyze"]');
    await page.keyboard.press("Enter");
    await page.waitForURL(/\/intake\/new\?id=/);

    const helper = new InterviewStepHelper(page);
    let advance = await helper.waitForAdvance(0);
    let guard = 0;
    while (advance.kind === "step") {
      guard += 1;
      if (guard > 8) throw new Error("Keyboard flow did not finish within 8 steps");
      await helper.settle();
      for (const question of await helper.listQuestions()) {
        const scope = `fieldset[data-field="${question.field}"]`;
        if (question.kind === "ShortTextQuestion") {
          await tabUntil(page, `${scope} input`);
          await page.keyboard.type("Sample text");
        } else {
          await tabUntil(page, `${scope} [role="radio"], ${scope} [role="checkbox"]`);
          await page.keyboard.press("Space");
        }
      }
      await tabUntil(page, '[data-testid="confirm-step"]');
      await expect(helper.confirm).toBeEnabled();
      const before = await helper.stepNumber();
      await page.keyboard.press("Enter");
      advance = await helper.waitForAdvance(before);
    }
    const review = new ReviewPage(page);
    await review.waitForLoaded();
    await expect(review.classification).toHaveAttribute("data-classification", "minimal");
  });
});
