import { expect, type Page } from "@playwright/test";

/**
 * React handlers are attached only after hydration; a `fill()` before that updates the DOM
 * but not React state (WebKit in dev mode makes this race visible). The theme toggle
 * announces "Switch to … mode" only once it has mounted, which makes it a page-wide marker.
 */
export async function waitForHydration(page: Page, timeout = 30_000): Promise<void> {
  await expect(page.getByTestId("theme-toggle")).toHaveAttribute("aria-label", /^Switch to /, { timeout });
}
