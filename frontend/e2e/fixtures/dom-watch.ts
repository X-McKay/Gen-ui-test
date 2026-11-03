import type { Page } from "@playwright/test";

declare global {
  interface Window {
    __e2eWatch?: {
      logLines: string[];
      forbidden: string[];
    };
  }
}

/**
 * Records, from the first paint onwards, every analysis log line that ever rendered and
 * every forbidden node (`Marquee`, `<marquee>`, script text) that ever appeared. Reads the
 * DOM only; it never changes what the page does.
 */
export async function watchDom(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const watch = { logLines: [] as string[], forbidden: [] as string[] };
    window.__e2eWatch = watch;
    const scan = () => {
      for (const element of document.querySelectorAll('[data-testid="analysis-log-line"]')) {
        const text = (element.textContent ?? "").trim();
        if (text && !watch.logLines.includes(text)) watch.logLines.push(text);
      }
      for (const element of document.querySelectorAll('[data-testid="Marquee"], marquee')) {
        watch.forbidden.push(element.outerHTML.slice(0, 200));
      }
      const main = document.querySelector("main");
      if (main && /<script/i.test(main.textContent ?? "")) watch.forbidden.push("script text in main");
    };
    const start = () => {
      scan();
      new MutationObserver(scan).observe(document.documentElement, {
        childList: true,
        subtree: true,
        characterData: true,
      });
    };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
    else start();
  });
}

export async function readWatch(page: Page): Promise<{ logLines: string[]; forbidden: string[] }> {
  return page.evaluate(() => window.__e2eWatch ?? { logLines: [], forbidden: [] });
}
