import type { Page } from "@playwright/test";

/**
 * Press Tab until the focused element matches `selector` (or sits inside an element that
 * does, when `within` is set). Keyboard only; throws after `maxTabs` presses.
 */
export async function tabUntil(page: Page, selector: string, options: { maxTabs?: number; within?: boolean } = {}): Promise<void> {
  const maxTabs = options.maxTabs ?? 150;
  for (let i = 0; i < maxTabs; i += 1) {
    await page.keyboard.press("Tab");
    const hit = await page.evaluate(
      ([sel, within]) => {
        const active = document.activeElement;
        if (!active || active === document.body) return false;
        if (active.matches(sel)) return true;
        return within ? Boolean(active.closest(sel)) : false;
      },
      [selector, Boolean(options.within)] as const,
    );
    if (hit) return;
  }
  throw new Error(`Tab never reached ${selector} within ${maxTabs} presses`);
}

export async function activeTestId(page: Page): Promise<string | null> {
  return page.evaluate(() => (document.activeElement as HTMLElement | null)?.dataset.testid ?? null);
}
