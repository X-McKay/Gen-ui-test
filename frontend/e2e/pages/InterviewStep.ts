import { expect, type Locator, type Page } from "@playwright/test";

import { LIVE } from "../fixtures/live";

export type QuestionKind = "ChoiceQuestion" | "MultiSelectQuestion" | "YesNoQuestion" | "ShortTextQuestion";

export const QUESTION_KINDS: readonly QuestionKind[] = [
  "ChoiceQuestion",
  "MultiSelectQuestion",
  "YesNoQuestion",
  "ShortTextQuestion",
];

export interface QuestionOnScreen {
  kind: QuestionKind;
  field: string;
}

/** What the page object chose for one question; compared with the record afterwards. */
export interface GivenAnswer extends QuestionOnScreen {
  value: string | boolean | string[] | "unknown";
}

export interface AnswerStrategy {
  /** Fields to answer with Not sure; `"first"` marks the first question of the step. */
  notSure?: readonly string[] | "first";
  /** Text typed into ShortTextQuestion controls. */
  text?: string;
}

/** The result of waiting for the interview to move on. */
export type Advance = { kind: "step"; step: number } | { kind: "review"; intakeId: string };

const SAMPLE_TEXT = "Sample text";
const REVIEW_PATH = /\/intake\/([^/]+)\/review/;

function isQuestionKind(value: string | null): value is QuestionKind {
  return (QUESTION_KINDS as readonly string[]).includes(value ?? "");
}

/**
 * Helpers for one InterviewStep surface: list the questions, answer them
 * deterministically, confirm, and wait for the agent to render the next step.
 * Selectors are data-testid, roles and data-* attributes only.
 */
export class InterviewStepHelper {
  readonly surface: Locator;
  readonly step: Locator;
  readonly intro: Locator;
  readonly confirm: Locator;
  readonly chips: Locator;
  readonly questions: Locator;
  readonly statusLine: Locator;
  readonly agentError: Locator;

  constructor(readonly page: Page) {
    this.surface = page.getByTestId("intake-surface");
    this.step = page.getByTestId("InterviewStep");
    this.intro = page.getByTestId("step-intro");
    this.confirm = page.getByTestId("confirm-step");
    this.chips = page.getByTestId("assumption-chip");
    this.questions = page.locator('[data-testid="step-questions"] fieldset[data-field]');
    this.statusLine = page.getByTestId("status-line");
    this.agentError = page.getByTestId("agent-error");
  }

  question(field: string): Locator {
    return this.page.locator(`fieldset[data-field="${field}"]`);
  }

  chip(field: string): Locator {
    return this.page.locator(`[data-testid="assumption-chip"][data-field="${field}"]`);
  }

  async stepNumber(): Promise<number> {
    const value = await this.surface.getAttribute("data-step");
    return Number(value ?? 0);
  }

  /** Waits until the surface shows a step after `after`, or the review page opened. */
  // A live first step (extraction plus reasoning) takes 30–60 s on its own; workers share the model.
  async waitForAdvance(after: number, timeout = LIVE ? 180_000 : 60_000): Promise<Advance> {
    await this.page.waitForFunction(
      (previous) => {
        if (/\/intake\/[^/]+\/review/.test(location.pathname)) return true;
        if (document.querySelector('[data-testid="agent-error"]')) return true;
        const surface = document.querySelector('[data-testid="intake-surface"]');
        if (!surface) return false;
        const current = Number(surface.getAttribute("data-step") ?? 0);
        return current > previous && Boolean(document.querySelector('[data-testid="confirm-step"], [data-testid="EscalationNotice"]'));
      },
      after,
      { timeout },
    );
    const review = REVIEW_PATH.exec(new URL(this.page.url()).pathname);
    if (review) return { kind: "review", intakeId: review[1] };
    if (await this.agentError.count()) {
      throw new Error(`Agent error on screen: ${await this.agentError.innerText()}`);
    }
    await this.settle();
    const latest = REVIEW_PATH.exec(new URL(this.page.url()).pathname);
    if (latest) return { kind: "review", intakeId: latest[1] };
    return { kind: "step", step: await this.stepNumber() };
  }

  /**
   * The agent may re-render while its run finishes. Wait until the step number and the
   * busy flag have been stable for a few polls so clicks land on the final DOM.
   */
  async settle(timeout = LIVE ? 120_000 : 30_000): Promise<void> {
    const deadline = Date.now() + timeout;
    let stable = 0;
    let previous = "";
    while (Date.now() < deadline) {
      if (REVIEW_PATH.test(new URL(this.page.url()).pathname)) return;
      const snapshot = await this.page.evaluate(() => {
        const surface = document.querySelector('[data-testid="intake-surface"]');
        const status = document.querySelector('[data-testid="status-line"]');
        const fields = [...document.querySelectorAll("fieldset[data-field]")].map((element) => element.getAttribute("data-field"));
        return JSON.stringify([surface?.getAttribute("data-step"), status?.getAttribute("data-busy"), fields]);
      });
      const busy = snapshot.includes('"true"');
      if (!busy && snapshot === previous) stable += 1;
      else stable = 0;
      previous = snapshot;
      if (stable >= 4) return;
      await this.page.waitForTimeout(150);
    }
    throw new Error("The interview surface did not settle in time");
  }

  async listQuestions(): Promise<QuestionOnScreen[]> {
    const raw = await this.questions.evaluateAll((elements) =>
      elements.map((element) => [element.getAttribute("data-testid"), element.getAttribute("data-field")]),
    );
    return raw.flatMap(([kind, field]) => (isQuestionKind(kind) && field ? [{ kind, field }] : []));
  }

  /** Answer one question deterministically: first option / Yes / sample text. */
  async answer(question: QuestionOnScreen, strategy: AnswerStrategy = {}): Promise<GivenAnswer> {
    const fieldset = this.question(question.field);
    await expect(fieldset).toBeVisible();
    switch (question.kind) {
      case "ChoiceQuestion": {
        const option = fieldset.getByRole("radio").first();
        await option.click();
        const value = (await option.getAttribute("data-value")) ?? "";
        return { ...question, value };
      }
      case "YesNoQuestion": {
        await fieldset.getByRole("radio", { name: "Yes" }).click();
        return { ...question, value: true };
      }
      case "MultiSelectQuestion": {
        const boxes = fieldset.getByRole("checkbox");
        const checked = await boxes.evaluateAll((elements) =>
          elements.filter((element) => element.getAttribute("aria-checked") === "true").map((element) => element.getAttribute("data-value") ?? ""),
        );
        if (checked.length === 0) {
          const first = boxes.first();
          await first.click();
          checked.push((await first.getAttribute("data-value")) ?? "");
        }
        return { ...question, value: checked };
      }
      case "ShortTextQuestion": {
        const text = strategy.text ?? SAMPLE_TEXT;
        await fieldset.getByRole("textbox").fill(text);
        return { ...question, value: text };
      }
    }
  }

  async notSure(field: string): Promise<GivenAnswer> {
    const fieldset = this.question(field);
    const button = fieldset.getByTestId("not-sure");
    await button.click();
    await expect(button).toHaveAttribute("aria-pressed", "true");
    const kind = (await fieldset.getAttribute("data-testid")) as QuestionKind;
    return { kind, field, value: "unknown" };
  }

  /** Answer every visible question of the current step (without confirming). */
  async answerAll(strategy: AnswerStrategy = {}): Promise<GivenAnswer[]> {
    const questions = await this.listQuestions();
    const notSureFields = new Set<string>(
      strategy.notSure === "first" ? (questions[0] ? [questions[0].field] : []) : (strategy.notSure ?? []),
    );
    const answers: GivenAnswer[] = [];
    for (const question of questions) {
      answers.push(notSureFields.has(question.field) ? await this.notSure(question.field) : await this.answer(question, strategy));
    }
    return answers;
  }

  /** Click confirm and wait for the next step or the review page. */
  async confirmAndWait(): Promise<Advance> {
    const before = await this.stepNumber();
    await expect(this.confirm).toBeEnabled();
    await this.confirm.click();
    return this.waitForAdvance(before);
  }

  /** Answer all questions, confirm and advance. */
  async answerCurrentStep(strategy: AnswerStrategy = {}): Promise<{ answers: GivenAnswer[]; next: Advance }> {
    const answers = await this.answerAll(strategy);
    const next = await this.confirmAndWait();
    return { answers, next };
  }

  /** Open a confirmed chip's editor via its `Edit <label>` button. */
  async openChipEditor(field: string): Promise<Locator> {
    const chip = this.chip(field);
    await chip.getByRole("button", { name: /^Edit / }).click();
    const editor = chip.getByTestId("assumption-editor");
    await expect(editor).toBeVisible();
    await expect(chip).toHaveAttribute("data-state", "editing");
    return editor;
  }

  /** The current value of a question as the controls show it (for restore checks). */
  async readAnswer(question: QuestionOnScreen): Promise<string | boolean | string[] | null> {
    const fieldset = this.question(question.field);
    if (question.kind === "ShortTextQuestion") return fieldset.getByRole("textbox").inputValue();
    if (question.kind === "MultiSelectQuestion") {
      return fieldset.getByRole("checkbox").evaluateAll((elements) =>
        elements.filter((element) => element.getAttribute("aria-checked") === "true").map((element) => element.getAttribute("data-value") ?? ""),
      );
    }
    const checked = fieldset.locator('[role="radio"][aria-checked="true"]');
    if ((await checked.count()) === 0) return null;
    const value = await checked.first().getAttribute("data-value");
    if (question.kind === "YesNoQuestion") return value === "yes";
    return value;
  }
}
