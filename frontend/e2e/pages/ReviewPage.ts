import fs from "node:fs/promises";

import { expect, type Locator, type Page } from "@playwright/test";

import { waitForHydration } from "../fixtures/hydration";

/** `/intake/<id>/review`: classification, fields, provenance and exports. */
export class ReviewPage {
  readonly header: Locator;
  readonly classification: Locator;
  readonly tierBadge: Locator;
  readonly mode: Locator;
  readonly repoUrl: Locator;
  readonly intakeIdLabel: Locator;
  readonly questionCount: Locator;
  readonly openQuestions: Locator;
  readonly downloadJsonButton: Locator;
  readonly downloadPdfButton: Locator;
  readonly submitButton: Locator;
  readonly fields: Locator;
  readonly main: Locator;

  constructor(readonly page: Page) {
    this.header = page.getByTestId("review-header");
    this.classification = page.getByTestId("classification-summary");
    this.tierBadge = page.getByTestId("tier-badge");
    this.mode = page.getByTestId("review-mode");
    this.repoUrl = page.getByTestId("review-repo-url");
    this.intakeIdLabel = page.getByTestId("intake-id");
    this.questionCount = page.getByTestId("question-count");
    this.openQuestions = page.getByTestId("open-questions");
    this.downloadJsonButton = page.getByTestId("download-json");
    this.downloadPdfButton = page.getByTestId("download-pdf");
    this.submitButton = page.getByTestId("submit-intake");
    this.fields = page.getByTestId("review-field");
    this.main = page.locator("main");
  }

  async goto(intakeId: string): Promise<void> {
    await this.page.goto(`/intake/${encodeURIComponent(intakeId)}/review`);
    await this.waitForLoaded();
  }

  async waitForLoaded(): Promise<void> {
    await this.page.waitForURL(/\/intake\/[^/]+\/review/);
    await waitForHydration(this.page);
    await expect(this.classification).toBeVisible({ timeout: 30_000 });
    await expect(this.downloadJsonButton).toBeVisible();
  }

  intakeId(): string {
    const match = /\/intake\/([^/]+)\/review/.exec(new URL(this.page.url()).pathname);
    if (!match) throw new Error(`Not on a review page: ${this.page.url()}`);
    return decodeURIComponent(match[1]);
  }

  async classificationValue(): Promise<string | null> {
    return this.classification.getAttribute("data-classification");
  }

  async tier(): Promise<string | null> {
    return this.tierBadge.first().getAttribute("data-tier");
  }

  async modeValue(): Promise<string | null> {
    return this.mode.getAttribute("data-mode");
  }

  field(path: string): Locator {
    return this.page.locator(`[data-testid="review-field"][data-field="${path}"]`);
  }

  /** The rationale's `Go to <label>` buttons. */
  whyLinks(label?: string): Locator {
    return this.page.getByRole("button", { name: label ? `Go to ${label}` : /^Go to / });
  }

  editButton(label: string): Locator {
    return this.page.getByRole("button", { name: `Edit ${label}`, exact: true });
  }

  provenanceButton(label: string): Locator {
    return this.page.getByRole("button", { name: `Provenance for ${label}`, exact: true });
  }

  private async download(trigger: Locator): Promise<Buffer> {
    const [download] = await Promise.all([this.page.waitForEvent("download"), trigger.click()]);
    const path = await download.path();
    if (!path) throw new Error(`Download ${download.suggestedFilename()} has no file`);
    return fs.readFile(path);
  }

  async downloadJson(): Promise<{ document: unknown; filename: string }> {
    const [download] = await Promise.all([this.page.waitForEvent("download"), this.downloadJsonButton.click()]);
    const path = await download.path();
    if (!path) throw new Error("JSON download has no file");
    const text = await fs.readFile(path, "utf8");
    return { document: JSON.parse(text) as unknown, filename: download.suggestedFilename() };
  }

  async downloadPdf(): Promise<Buffer> {
    return this.download(this.downloadPdfButton);
  }

  async mainText(): Promise<string> {
    return this.main.innerText();
  }
}
