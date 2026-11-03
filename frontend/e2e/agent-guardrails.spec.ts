import { expect, test } from "@playwright/test";

import { HR_SCREENING, INVALID_COMPONENT_MARKER, PROJECT_NAME, PROJECT_OWNER } from "./fixtures/descriptions";
import { readWatch, watchDom } from "./fixtures/dom-watch";
import { NewProjectPage } from "./pages";

const RAW_JSON = /\{\s*"[a-z_]+"\s*:/;

function sentenceCount(text: string): number {
  return text
    .trim()
    .split(/[.!?]+\s/)
    .filter((part) => part.trim().length > 0).length;
}

test.describe("agent guardrails", () => {
  test("a component outside the catalog never renders; the surface self-corrects", async ({ page }) => {
    await watchDom(page);
    const flow = new NewProjectPage(page);
    await flow.start({
      description: `${HR_SCREENING} ${INVALID_COMPONENT_MARKER}`,
      name: PROJECT_NAME,
      owner: PROJECT_OWNER,
    });

    // A valid step is on screen (the agent's second attempt).
    await expect(flow.interview.step).toBeVisible();
    await expect(flow.interview.confirm).toBeVisible();

    // Nothing forbidden shows up, now or over the next three seconds.
    await page.waitForTimeout(3000);
    expect(await page.getByTestId("Marquee").count()).toBe(0);
    expect(await page.locator("marquee").count()).toBe(0);
    expect(await page.locator("main").innerText()).not.toMatch(/<script/i);
    const watched = await readWatch(page);
    expect(watched.forbidden).toEqual([]);
    await expect(flow.interview.agentError).toHaveCount(0);
  });

  test("agent text stays short and no raw JSON leaks outside the export", async ({ page }) => {
    const flow = new NewProjectPage(page);
    await flow.start({ description: HR_SCREENING, name: PROJECT_NAME, owner: PROJECT_OWNER });
    const intros: string[] = [];
    const run = await flow.completeInterview({
      onStep: async ({ helper }) => {
        const intro = (await helper.intro.textContent()) ?? "";
        intros.push(intro);
        expect(intro.trim().length).toBeGreaterThan(0);
        expect(sentenceCount(intro), intro).toBeLessThanOrEqual(2);
        const text = await page.locator("main").innerText();
        expect(text).not.toMatch(RAW_JSON);
      },
    });
    expect(intros.length).toBeGreaterThan(0);
    const reviewText = await run.review.mainText();
    expect(reviewText).not.toMatch(RAW_JSON);
    expect(reviewText).not.toMatch(/<script/i);
  });
});
