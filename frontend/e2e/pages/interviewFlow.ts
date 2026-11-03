import type { Page } from "@playwright/test";

import { BOUNDS } from "../fixtures/live";
import {
  type Advance,
  type AnswerStrategy,
  type GivenAnswer,
  InterviewStepHelper,
  type QuestionOnScreen,
} from "./InterviewStep";
import { ReviewPage } from "./ReviewPage";

export interface StepRecord {
  step: number;
  questions: QuestionOnScreen[];
  chips: number;
  answers: GivenAnswer[];
}

export interface StepContext {
  /** 1 for the first interview step the runner saw. */
  index: number;
  step: number;
  questions: QuestionOnScreen[];
  helper: InterviewStepHelper;
}

export interface InterviewRun {
  intakeId: string;
  steps: StepRecord[];
  answers: GivenAnswer[];
  questionsAnswered: number;
  notSureFields: string[];
  review: ReviewPage;
}

export interface RunOptions {
  /** Decide how to answer a given step; defaults to first option / Yes / sample text. */
  strategyFor?: (context: StepContext) => AnswerStrategy | Promise<AnswerStrategy>;
  /** Runs before the step is answered (assertions about the rendered step). */
  onStep?: (context: StepContext) => Promise<void>;
  /** Runs right after a step was confirmed and the next one rendered. */
  afterConfirm?: (context: StepContext, answers: GivenAnswer[]) => Promise<void>;
  maxSteps?: number;
}

function intakeIdFromUrl(page: Page): string {
  const url = new URL(page.url());
  const fromQuery = url.searchParams.get("id");
  if (fromQuery) return fromQuery;
  const fromPath = /\/intake\/([^/]+)\/review/.exec(url.pathname);
  if (fromPath) return decodeURIComponent(fromPath[1]);
  throw new Error(`No intake id in ${page.url()}`);
}

/** Drive the interview from the step currently on screen to the review page. */
export async function runInterview(page: Page, options: RunOptions = {}): Promise<InterviewRun> {
  const helper = new InterviewStepHelper(page);
  const intakeId = intakeIdFromUrl(page);
  const maxSteps = options.maxSteps ?? BOUNDS.maxSteps;
  const steps: StepRecord[] = [];
  const answers: GivenAnswer[] = [];
  let index = 0;
  let advance: Advance = { kind: "step", step: await helper.stepNumber() };
  while (advance.kind === "step") {
    index += 1;
    if (index > maxSteps) throw new Error(`Interview did not finish within ${maxSteps} steps`);
    await helper.settle();
    const questions = await helper.listQuestions();
    const context: StepContext = { index, step: advance.step, questions, helper };
    await options.onStep?.(context);
    const strategy = (await options.strategyFor?.(context)) ?? {};
    const stepAnswers = await helper.answerAll(strategy);
    steps.push({ step: advance.step, questions, chips: await helper.chips.count(), answers: stepAnswers });
    answers.push(...stepAnswers);
    advance = await helper.confirmAndWait();
    await options.afterConfirm?.(context, stepAnswers);
  }
  const review = new ReviewPage(page);
  await review.waitForLoaded();
  return {
    intakeId,
    steps,
    answers,
    questionsAnswered: answers.length,
    notSureFields: answers.filter((answer) => answer.value === "unknown").map((answer) => answer.field),
    review,
  };
}
