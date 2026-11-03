import { expect, test } from "@playwright/test";

import { HR_SCREENING } from "./fixtures/descriptions";
import { InterviewStepHelper, NewProjectPage } from "./pages";

test.describe("resume", () => {
  test("a reload keeps the step and the unsent selection; a fresh context renders the same step", async ({ page, browser }) => {
    const flow = new NewProjectPage(page);
    const { intakeId } = await flow.start({ description: HR_SCREENING });
    const helper = flow.interview;

    // Step 1 → step 2.
    const { next } = await helper.answerCurrentStep();
    expect(next.kind).toBe("step");
    if (next.kind !== "step") return;
    const stepBefore = next.step;
    const questionsBefore = await helper.listQuestions();
    expect(questionsBefore.length).toBeGreaterThan(0);

    // Select an answer without confirming.
    const given = await helper.answer(questionsBefore[0]);
    await expect.poll(() => helper.readAnswer(questionsBefore[0])).toEqual(given.value);

    await page.reload();
    const afterReload = await helper.waitForAdvance(stepBefore - 1);
    expect(afterReload).toEqual({ kind: "step", step: stepBefore });
    const questionsAfter = await helper.listQuestions();
    expect(questionsAfter.map((question) => question.field).sort()).toEqual(questionsBefore.map((question) => question.field).sort());
    expect(await helper.readAnswer(questionsBefore[0])).toEqual(given.value);
    await expect(page).toHaveURL(new RegExp(`id=${intakeId}`));

    // A new browser context has no localStorage: the same step renders, the draft is not required.
    const context = await browser.newContext();
    try {
      const fresh = await context.newPage();
      await fresh.goto(NewProjectPage.resumeUrl(intakeId));
      const freshHelper = new InterviewStepHelper(fresh);
      const freshAdvance = await freshHelper.waitForAdvance(stepBefore - 1);
      expect(freshAdvance).toEqual({ kind: "step", step: stepBefore });
      const freshQuestions = await freshHelper.listQuestions();
      expect(freshQuestions.map((question) => question.field).sort()).toEqual(questionsBefore.map((question) => question.field).sort());
      await expect(freshHelper.confirm).toBeVisible();
    } finally {
      await context.close();
    }
  });
});
