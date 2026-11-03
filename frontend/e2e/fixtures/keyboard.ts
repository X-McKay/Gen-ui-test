import type { Page } from "@playwright/test";

/**
 * Press Tab until the focused element matches `selector` (or sits inside an element that
 * does, when `within` is set). Keyboard only; throws after `maxTabs` presses.
 */
export async function tabUntil(
  page: Page,
  selector: string,
  options: { maxTabs?: number; within?: boolean } = {},
): Promise<void> {
  const maxTabs = options.maxTabs ?? 150;
  for (let i = 0; i < maxTabs; i += 1) {
    await page.keyboard.press("Tab");
    let hit = false;
    try {
      hit = await page.evaluate(
        ([sel, within]) => {
          const active = document.activeElement;
          if (!active || active === document.body) return false;
          if (active.matches(sel)) return true;
          return within ? Boolean(active.closest(sel)) : false;
        },
        [selector, Boolean(options.within)] as const,
      );
    } catch (error) {
      // `next dev` performs a full reload after a cold compile; the document is replaced and
      // focus starts over. Wait for the new document to hydrate and keep counting.
      if (!(error instanceof Error && error.message.includes("Execution context was destroyed"))) throw error;
      await page.waitForLoadState("domcontentloaded");
      await page.getByTestId("theme-toggle").waitFor({ timeout: 30_000 });
    }
    if (hit) return;
  }
  throw new Error(`Tab never reached ${selector} within ${maxTabs} presses`);
}

export async function activeTestId(page: Page): Promise<string | null> {
  return page.evaluate(() => (document.activeElement as HTMLElement | null)?.dataset.testid ?? null);
}
