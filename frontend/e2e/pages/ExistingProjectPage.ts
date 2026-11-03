import { expect, type Locator, type Page } from "@playwright/test";

import { InterviewStepHelper } from "./InterviewStep";
import { type InterviewRun, type RunOptions, runInterview } from "./interviewFlow";

export interface RowCorrection {
  /** Checkbox labels to turn on (multi controls). */
  select?: readonly string[];
  /** Checkbox labels to turn off (multi controls). */
  unselect?: readonly string[];
  /** Radio label to choose (choice / yes-no controls). */
  choose?: string;
  /** Text for text controls. */
  text?: string;
}

/** `/intake/existing`: repository form, analysis progress, findings review, gap questions. */
export class ExistingProjectPage {
  readonly interview: InterviewStepHelper;
  readonly form: Locator;
  readonly url: Locator;
  readonly urlError: Locator;
  readonly token: Locator;
  readonly analyzeButton: Locator;
  readonly progress: Locator;
  readonly logLines: Locator;
  readonly findings: Locator;
  readonly findingsTable: Locator;
  readonly rows: Locator;
  readonly analysisError: Locator;

  constructor(readonly page: Page) {
    this.interview = new InterviewStepHelper(page);
    this.form = page.getByTestId("repository-url-form");
    this.url = page.getByTestId("repo-url");
    this.urlError = page.getByTestId("repo-url-error");
    this.token = page.getByTestId("repo-token");
    this.analyzeButton = page.getByTestId("analyze-repository");
    this.progress = page.getByTestId("analysis-progress");
    this.logLines = page.getByTestId("analysis-log-line");
    this.findings = page.getByTestId("FindingsReview");
    this.findingsTable = page.getByTestId("findings-table");
    this.rows = page.getByTestId("finding-row");
    this.analysisError = page.getByTestId("analysis-error");
  }

  async goto(): Promise<void> {
    await this.page.goto("/intake/existing");
    await expect(this.form).toBeVisible();
  }

  async enterUrl(url: string): Promise<void> {
    await this.url.fill(url);
    await this.url.blur();
  }

  /** Submit the URL and wait until the findings surface is on screen. */
  async analyze(url: string, timeout = 120_000): Promise<string> {
    await this.enterUrl(url);
    await expect(this.analyzeButton).toBeEnabled();
    await this.analyzeButton.click();
    await expect(this.findings.or(this.analysisError)).toBeVisible({ timeout });
    if (await this.analysisError.count()) {
      throw new Error(`Repository analysis failed: ${await this.analysisError.innerText()}`);
    }
    await this.page.waitForURL(/\/intake\/existing\?id=/);
    await this.interview.settle();
    return this.intakeId();
  }

  intakeId(): string {
    const id = new URL(this.page.url()).searchParams.get("id");
    if (!id) throw new Error(`No intake id in ${this.page.url()}`);
    return id;
  }

  row(field: string): Locator {
    return this.page.locator(`[data-testid="finding-row"][data-field="${field}"]`);
  }

  /** Correct one row inline through its `Correct <label>` button, then press Done. */
  async correctRow(field: string, correction: RowCorrection): Promise<void> {
    const row = this.row(field);
    await row.getByRole("button", { name: /^Correct / }).click();
    const editor = row.getByTestId("finding-editor");
    await expect(editor).toBeVisible();
    for (const label of correction.select ?? []) {
      const box = editor.getByRole("checkbox", { name: label, exact: true });
      if ((await box.getAttribute("aria-checked")) !== "true") await box.click();
    }
    for (const label of correction.unselect ?? []) {
      const box = editor.getByRole("checkbox", { name: label, exact: true });
      if ((await box.getAttribute("aria-checked")) === "true") await box.click();
    }
    if (correction.choose) await editor.getByRole("radio", { name: correction.choose, exact: true }).click();
    if (correction.text !== undefined) await editor.getByRole("textbox").fill(correction.text);
    await editor.getByRole("button", { name: "Done" }).click();
    await expect(editor).toBeHidden();
    await expect(row).toHaveAttribute("data-state", "corrected");
  }

  /** Confirm the findings step and wait for the first gap step (or the review). */
  confirmFindings() {
    return this.interview.confirmAndWait();
  }

  /** Answer the gap steps that follow the findings until the review page opens. */
  completeGapQuestions(options: RunOptions = {}): Promise<InterviewRun> {
    return runInterview(this.page, options);
  }
}
