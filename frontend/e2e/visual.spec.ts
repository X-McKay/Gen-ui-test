import { expect, test } from "@playwright/test";

import { FIXTURE_REPOSITORIES, HR_SCREENING, PROJECT_NAME, PROJECT_OWNER } from "./fixtures/descriptions";
import { LIVE } from "./fixtures/live";
import { readSeedState } from "./fixtures/state";
import { ExistingProjectPage, LandingPage, NewProjectPage, ReviewPage } from "./pages";

const SCHEMES = ["light", "dark"] as const;

test.describe("visual", () => {
  // Baselines are generated on Chromium (desktop and Pixel 7); Firefox and WebKit render
  // text differently enough that their own baselines would only add noise.
  test.skip(({ browserName }) => browserName !== "chromium", "visual baselines are chromium-only");

  for (const scheme of SCHEMES) {
    test.describe(scheme, () => {
      test.use({ colorScheme: scheme });

      test(`landing (${scheme})`, async ({ page }) => {
        const landing = new LandingPage(page);
        await landing.goto();
        await expect.poll(() => landing.colorSchemeClass()).toBe(scheme);
        await expect(page).toHaveScreenshot(`landing-${scheme}.png`, { fullPage: true });
      });

      test(`first interview step (${scheme})`, async ({ page }) => {
        test.skip(LIVE, "the step intro is written by the model and varies between runs");
        const flow = new NewProjectPage(page);
        await flow.start({ description: HR_SCREENING, name: PROJECT_NAME, owner: PROJECT_OWNER });
        await flow.interview.settle();
        await expect(flow.interview.step).toBeVisible();
        await expect(flow.interview.surface).toHaveScreenshot(`interview-${scheme}.png`, {
          mask: [flow.interview.statusLine],
        });
      });

      test(`findings table (${scheme})`, async ({ page }) => {
        test.skip(LIVE, "the step intro is written by the model and varies between runs");
        const flow = new ExistingProjectPage(page);
        await flow.goto();
        await flow.analyze(FIXTURE_REPOSITORIES.hrScreening);
        await expect(flow.findingsTable).toBeVisible();
        await expect(flow.findings).toHaveScreenshot(`findings-${scheme}.png`, {
          mask: [flow.interview.statusLine],
        });
      });

      test(`review page (${scheme})`, async ({ page }) => {
        const review = new ReviewPage(page);
        await review.goto(readSeedState().seededIntakeId);
        await expect(review.main).toHaveScreenshot(`review-${scheme}.png`, {
          mask: [review.intakeIdLabel],
        });
      });
    });
  }
});
