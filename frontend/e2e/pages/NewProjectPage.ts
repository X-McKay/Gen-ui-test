import { expect, type Locator, type Page } from "@playwright/test";

import { waitForHydration } from "../fixtures/hydration";
import { type Advance, InterviewStepHelper } from "./InterviewStep";
import { type InterviewRun, type RunOptions, runInterview } from "./interviewFlow";

export interface DescribeInput {
  description: string;
  name?: string;
  owner?: string;
}

/** `/intake/new`: the describe form, then the agent-driven interview. */
export class NewProjectPage {
  readonly interview: InterviewStepHelper;
  readonly form: Locator;
  readonly description: Locator;
  readonly name: Locator;
  readonly owner: Locator;
  readonly analyzeButton: Locator;

  constructor(readonly page: Page) {
    this.interview = new InterviewStepHelper(page);
    this.form = page.getByTestId("describe-form");
    this.description = page.getByTestId("project-description");
    this.name = page.getByTestId("project-name");
    this.owner = page.getByTestId("project-owner");
    this.analyzeButton = page.getByTestId("analyze");
  }

  async goto(): Promise<void> {
    await this.page.goto("/intake/new");
    await waitForHydration(this.page);
    await expect(this.form).toBeVisible();
  }

  async describe(input: DescribeInput): Promise<void> {
    await this.description.fill(input.description);
    if (input.name !== undefined) await this.name.fill(input.name);
    if (input.owner !== undefined) await this.owner.fill(input.owner);
  }

  /** Submit the form and wait for the first interview step. */
  async analyze(): Promise<{ intakeId: string; first: Advance }> {
    await expect(this.analyzeButton).toBeEnabled();
    await this.analyzeButton.click();
    await this.page.waitForURL(/\/intake\/new\?id=/);
    const intakeId = this.intakeId();
    const first = await this.interview.waitForAdvance(0);
    return { intakeId, first };
  }

  intakeId(): string {
    const id = new URL(this.page.url()).searchParams.get("id");
    if (!id) throw new Error(`No intake id in ${this.page.url()}`);
    return id;
  }

  async start(input: DescribeInput): Promise<{ intakeId: string; first: Advance }> {
    await this.goto();
    await this.describe(input);
    return this.analyze();
  }

  /** The same interview in another tab or context: `/intake/new?id=<id>`. */
  static resumeUrl(intakeId: string): string {
    return `/intake/new?id=${encodeURIComponent(intakeId)}`;
  }

  /** Drive the interview from the current step to the review page. */
  completeInterview(options: RunOptions = {}): Promise<InterviewRun> {
    return runInterview(this.page, options);
  }
}
