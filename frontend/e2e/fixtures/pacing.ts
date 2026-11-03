import type { Page } from "@playwright/test";

/**
 * In mock mode the whole analysis SSE stream arrives in one network chunk (~25 ms), so
 * React batches every progress event into the final `done` render and the log lines are
 * never painted. This shim delivers `EventSource` events to the page's listeners one at a
 * time, `gapMs` apart, so the UI shows what a real clone shows over several seconds.
 * The app code is untouched: only the delivery pace changes.
 */
export async function paceEventSource(page: Page, gapMs = 150): Promise<void> {
  await page.addInitScript((gap: number) => {
    const prototype = window.EventSource?.prototype;
    if (!prototype) return;
    const original = prototype.addEventListener;
    const queues = new WeakMap<EventSource, Promise<void>>();
    const paced = function (
      this: EventSource,
      type: string,
      listener: EventListenerOrEventListenerObject | null,
      options?: boolean | AddEventListenerOptions,
    ): void {
      if (!listener) return;
      const wrapped = (event: Event) => {
        const queue = (queues.get(this) ?? Promise.resolve())
          .then(() => new Promise<void>((resolve) => window.setTimeout(resolve, gap)))
          .then(() => {
            // Once the page closed the source (after `done`), drop whatever is still queued.
            if (this.readyState === EventSource.CLOSED) return;
            if (typeof listener === "function") listener.call(this, event);
            else listener.handleEvent(event);
          });
        queues.set(this, queue);
      };
      original.call(this, type, wrapped, options);
    };
    prototype.addEventListener = paced as typeof prototype.addEventListener;
  }, gapMs);
}
