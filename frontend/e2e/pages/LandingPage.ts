import { expect, type Locator, type Page } from "@playwright/test";

/** `/`: the two mode cards and the theme toggle. */
export class LandingPage {
  readonly newCard: Locator;
  readonly existingCard: Locator;
  readonly themeToggle: Locator;
  readonly heading: Locator;

  constructor(readonly page: Page) {
    this.newCard = page.getByTestId("mode-card-new");
    this.existingCard = page.getByTestId("mode-card-existing");
    this.themeToggle = page.getByTestId("theme-toggle");
    this.heading = page.getByRole("heading", { level: 1 });
  }

  async goto(): Promise<void> {
    await this.page.goto("/");
    await expect(this.newCard).toBeVisible();
    await expect(this.existingCard).toBeVisible();
  }

  /** Press Tab until the element with `testId` has focus. Keyboard only. */
  async tabTo(testId: string, maxTabs = 20): Promise<void> {
    for (let i = 0; i < maxTabs; i += 1) {
      await this.page.keyboard.press("Tab");
      const focused = await this.page.evaluate(() => (document.activeElement as HTMLElement | null)?.dataset.testid ?? null);
      if (focused === testId) return;
    }
    throw new Error(`Tab never reached [data-testid="${testId}"] within ${maxTabs} presses`);
  }

  async colorSchemeClass(): Promise<"dark" | "light" | null> {
    return this.page.evaluate(() => {
      const list = document.documentElement.classList;
      if (list.contains("dark")) return "dark";
      if (list.contains("light")) return "light";
      return null;
    });
  }
}
