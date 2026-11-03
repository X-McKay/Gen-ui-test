import { expect, test } from "@playwright/test";

import { LandingPage } from "./pages";

test.describe("landing", () => {
  test("the two cards sit side by side at 1280 and stack at 390", async ({ page }) => {
    const landing = new LandingPage(page);
    await page.setViewportSize({ width: 1280, height: 800 });
    await landing.goto();
    const wide = { a: await landing.newCard.boundingBox(), b: await landing.existingCard.boundingBox() };
    if (!wide.a || !wide.b) throw new Error("Cards have no bounding box");
    expect(Math.abs(wide.a.y - wide.b.y)).toBeLessThan(2);
    expect(wide.b.x).toBeGreaterThan(wide.a.x + wide.a.width - 1);

    await page.setViewportSize({ width: 390, height: 844 });
    const narrow = { a: await landing.newCard.boundingBox(), b: await landing.existingCard.boundingBox() };
    if (!narrow.a || !narrow.b) throw new Error("Cards have no bounding box");
    expect(narrow.b.y).toBeGreaterThan(narrow.a.y + narrow.a.height - 1);
    expect(Math.abs(narrow.a.x - narrow.b.x)).toBeLessThan(2);
  });

  test("Tab and Enter reach the new-project route", async ({ page }) => {
    const landing = new LandingPage(page);
    await landing.goto();
    await landing.tabTo("mode-card-new");
    await page.keyboard.press("Enter");
    await page.waitForURL(/\/intake\/new$/);
    await expect(page.getByTestId("describe-form")).toBeVisible();
  });

  test("Tab and Enter reach the existing-project route", async ({ page }) => {
    const landing = new LandingPage(page);
    await landing.goto();
    await landing.tabTo("mode-card-existing");
    await page.keyboard.press("Enter");
    await page.waitForURL(/\/intake\/existing$/);
    await expect(page.getByTestId("repository-url-form")).toBeVisible();
  });

  test("keyboard focus draws a visible ring on a card", async ({ page }) => {
    const landing = new LandingPage(page);
    await landing.goto();
    await landing.tabTo("mode-card-new");
    const ring = await landing.newCard.evaluate((element) => {
      const style = getComputedStyle(element);
      return {
        matchesFocusVisible: element.matches(":focus-visible"),
        outlineStyle: style.outlineStyle,
        outlineWidth: Number.parseFloat(style.outlineWidth),
        boxShadow: style.boxShadow,
      };
    });
    expect(ring.matchesFocusVisible).toBe(true);
    const hasOutline = ring.outlineStyle !== "none" && ring.outlineWidth > 0;
    const hasShadow = ring.boxShadow !== "none" && ring.boxShadow !== "";
    expect(hasOutline || hasShadow, JSON.stringify(ring)).toBe(true);
  });

  test("renders in light and dark, and the toggle switches between them", async ({ page }, testInfo) => {
    const landing = new LandingPage(page);
    await page.emulateMedia({ colorScheme: "light" });
    await landing.goto();
    await expect.poll(() => landing.colorSchemeClass()).toBe("light");
    await testInfo.attach("landing-light", {
      body: await page.screenshot({ fullPage: true }),
      contentType: "image/png",
    });

    await page.emulateMedia({ colorScheme: "dark" });
    await page.reload();
    await expect(landing.newCard).toBeVisible();
    await expect.poll(() => landing.colorSchemeClass()).toBe("dark");
    await testInfo.attach("landing-dark", {
      body: await page.screenshot({ fullPage: true }),
      contentType: "image/png",
    });

    await expect(landing.themeToggle).toHaveAttribute("aria-label", "Switch to light mode");
    await landing.themeToggle.click();
    await expect.poll(() => landing.colorSchemeClass()).toBe("light");
    await expect(landing.themeToggle).toHaveAttribute("aria-label", "Switch to dark mode");
  });
});
