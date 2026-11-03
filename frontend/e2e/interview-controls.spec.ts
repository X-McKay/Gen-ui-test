import { expect, test, type APIRequestContext } from "@playwright/test";

import { fieldValue, getRecord, sameAnswer } from "./fixtures/api";
import { FIXTURE_REPOSITORIES, HR_SCREENING } from "./fixtures/descriptions";
import { LIVE } from "./fixtures/live";
import { ExistingProjectPage, type GivenAnswer, type InterviewStepHelper, NewProjectPage, type QuestionKind, type StepContext } from "./pages";

/** Chips that carry a single-choice editor in the HR scenario, most likely first. */
const CHOICE_CHIP_CANDIDATES = ["project.lifecycle_stage", "ai_system.model_source", "project.target_users", "ai_system.autonomy_level"];

async function expectRoundTrip(request: APIRequestContext, intakeId: string, answers: readonly GivenAnswer[]): Promise<void> {
  const record = await getRecord(request, intakeId);
  for (const answer of answers) {
    const stored = fieldValue(record, answer.field);
    expect(sameAnswer(stored, answer.value), `${answer.field}: stored ${JSON.stringify(stored)}, given ${JSON.stringify(answer.value)}`).toBe(true);
  }
}

/** True when none of the questions is pre-filled (so confirm has to be disabled). */
async function nothingPreAnswered(helper: InterviewStepHelper, context: StepContext): Promise<boolean> {
  for (const question of context.questions) {
    const current = await helper.readAnswer(question);
    const empty = current === null || current === "" || (Array.isArray(current) && current.length === 0);
    if (!empty) return false;
  }
  return context.questions.length > 0;
}

/** The confirm gate: disabled until every required question has an answer; clearing text re-disables it. */
async function checkConfirmGate(helper: InterviewStepHelper, context: StepContext): Promise<void> {
  if (await nothingPreAnswered(helper, context)) {
    await expect(helper.confirm).toBeDisabled();
  }
  const textQuestions = context.questions.filter((question) => question.kind === "ShortTextQuestion");
  if (textQuestions.length === 0) return;
  for (const question of context.questions) await helper.answer(question);
  await expect(helper.confirm).toBeEnabled();
  const textbox = helper.question(textQuestions[0].field).getByRole("textbox");
  await textbox.fill("");
  await textbox.blur();
  await expect(helper.confirm).toBeDisabled();
  await textbox.fill("Sample text");
  await expect(helper.confirm).toBeEnabled();
}

test.describe("interview controls", () => {
  test("choice, yes/no and text questions round-trip, the confirm gate holds, and an edited chip is stored", async ({ page, request }) => {
    const flow = new NewProjectPage(page);
    const { intakeId } = await flow.start({ description: HR_SCREENING });
    const helper = flow.interview;
    await helper.settle();

    // Edit one confirmed chip through its editor and remember the new value.
    let chipEdit: { field: string; value: string } | null = null;
    for (const field of CHOICE_CHIP_CANDIDATES) {
      if ((await helper.chip(field).count()) === 0) continue;
      const editor = await helper.openChipEditor(field);
      const unchecked = editor.locator('[role="radio"][aria-checked="false"]:not([data-value="unknown"])');
      if ((await unchecked.count()) === 0) continue;
      const value = await unchecked.first().getAttribute("data-value");
      if (!value) continue;
      // Pin the option by value: the "unchecked" locator would re-resolve after the click.
      const option = editor.locator(`[role="radio"][data-value="${value}"]`);
      await option.click();
      await expect(option).toHaveAttribute("aria-checked", "true");
      await expect(helper.chip(field)).toHaveAttribute("data-state", "editing");
      chipEdit = { field, value };
      break;
    }
    if (!LIVE) expect(chipEdit, "no editable choice chip found in the first step").not.toBeNull();

    const kinds = new Set<QuestionKind>();
    const run = await flow.completeInterview({
      onStep: async (context) => {
        for (const question of context.questions) kinds.add(question.kind);
        await checkConfirmGate(helper, context);
      },
      afterConfirm: async (_context, answers) => {
        await expectRoundTrip(request, intakeId, answers);
      },
    });

    if (chipEdit) {
      const record = await getRecord(request, intakeId);
      expect(fieldValue(record, chipEdit.field)).toBe(chipEdit.value);
      await expect(run.review.field(chipEdit.field)).toBeVisible();
    }
    // The live model may infer every field from the description and ask nothing.
    if (!LIVE) expect(run.answers.length).toBeGreaterThan(0);
    if (!LIVE) {
      expect([...kinds].sort()).toEqual(["ChoiceQuestion", "ShortTextQuestion", "YesNoQuestion"]);
    }
  });

  test("multi-select questions round-trip through the repository gap steps", async ({ page, request }) => {
    const flow = new ExistingProjectPage(page);
    await flow.goto();
    const intakeId = await flow.analyze(FIXTURE_REPOSITORIES.hrScreening);
    await flow.confirmFindings();

    const kinds = new Set<QuestionKind>();
    await flow.completeGapQuestions({
      onStep: async (context) => {
        for (const question of context.questions) kinds.add(question.kind);
        if (await nothingPreAnswered(flow.interview, context)) await expect(flow.interview.confirm).toBeDisabled();
      },
      afterConfirm: async (_context, answers) => {
        await expectRoundTrip(request, intakeId, answers);
      },
    });
    if (!LIVE) expect(kinds.has("MultiSelectQuestion")).toBe(true);
  });
});
