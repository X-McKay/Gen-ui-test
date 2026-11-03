import { expect, test } from "@playwright/test";

import { fieldValue, getRecord } from "./fixtures/api";
import { HR_SCREENING, LOG_SEARCH, PROJECT_NAME, PROJECT_OWNER } from "./fixtures/descriptions";
import { BOUNDS, LIVE } from "./fixtures/live";
import { validateIntakeDocument } from "./fixtures/schema";
import { NewProjectPage } from "./pages";

interface ExportLike {
  meta: { intake_id: string; question_count: number; mode: string };
  assessment: {
    open_questions: string[];
    eu_ai_act: { classification: string; annex_iii_categories: string[]; rationale: { field: string }[] };
  };
}

test.describe("new project", () => {
  test("HR screening: chips first, few questions, Not sure, high risk, valid exports", async ({ page, request }) => {
    const flow = new NewProjectPage(page);
    const { intakeId, first } = await flow.start({ description: HR_SCREENING, name: PROJECT_NAME, owner: PROJECT_OWNER });
    expect(first.kind).toBe("step");

    // Assumption chips are on screen before a single question has been answered.
    await flow.interview.settle();
    expect(await flow.interview.chips.count()).toBeGreaterThan(0);
    await expect(flow.interview.chips.first()).toHaveAttribute("data-state", /pending|confirmed/);
    await expect(flow.interview.step).toBeVisible();

    const run = await flow.completeInterview({
      // Not sure on the first question of the second step, whatever the model asks there.
      strategyFor: ({ index }) => (index === 2 ? { notSure: "first" } : {}),
    });
    expect(run.intakeId).toBe(intakeId);
    // The scripted model always leaves a question for step 2; the live model may infer it all.
    if (!LIVE) expect(run.notSureFields.length).toBeGreaterThanOrEqual(1);
    const notSureField: string | undefined = run.notSureFields[0];

    // At most eight questions, in the DOM and in the record.
    const record = await getRecord(request, intakeId);
    expect(run.questionsAnswered).toBeLessThanOrEqual(BOUNDS.hrMaxQuestions);
    expect(record.meta.question_count).toBeLessThanOrEqual(BOUNDS.hrMaxQuestions);
    if (!LIVE) expect(record.meta.question_count).toBe(run.questionsAnswered);
    expect(record.meta.status).toBe("completed");

    // High risk, with the employment domain in the rationale.
    const review = run.review;
    await expect(review.classification).toHaveAttribute("data-classification", "high_risk");
    await expect(review.tierBadge.first()).toHaveAttribute("data-tier", "high_risk");
    await expect(review.whyLinks("Domains").first()).toBeVisible();
    expect(record.assessment.eu_ai_act.rationale.map((entry) => entry.field)).toContain("use_case.domains");
    expect(record.assessment.eu_ai_act.annex_iii_categories.length).toBeGreaterThan(0);
    if (notSureField) await expect(review.openQuestions).toBeVisible();

    // The JSON export carries the Not sure answer as "unknown" and validates against the schema.
    const { document, filename } = await review.downloadJson();
    expect(filename).toMatch(/\.json$/);
    const exported = document as ExportLike;
    expect(exported.meta.intake_id).toBe(intakeId);
    if (notSureField) {
      expect(fieldValue(exported, notSureField)).toBe("unknown");
      expect(exported.assessment.open_questions).toContain(notSureField);
    }
    expect(exported.assessment.eu_ai_act.classification).toBe("high_risk");
    const validation = validateIntakeDocument(document);
    expect(validation.errors).toEqual([]);
    expect(validation.valid).toBe(true);

    // The PDF download fires and is a PDF.
    const pdf = await review.downloadPdf();
    expect(pdf.subarray(0, 5).toString("latin1")).toBe("%PDF-");
  });

  test("log search: at most four questions and a minimal classification", async ({ page, request }) => {
    const flow = new NewProjectPage(page);
    const { intakeId } = await flow.start({ description: LOG_SEARCH, name: "Log search assistant", owner: PROJECT_OWNER });
    const run = await flow.completeInterview();
    const record = await getRecord(request, intakeId);
    expect(run.questionsAnswered).toBeLessThanOrEqual(BOUNDS.logMaxQuestions);
    expect(record.meta.question_count).toBeLessThanOrEqual(BOUNDS.logMaxQuestions);
    await expect(run.review.classification).toHaveAttribute("data-classification", "minimal");
    expect(record.assessment.eu_ai_act.classification).toBe("minimal");
    expect(record.assessment.open_questions).toEqual([]);
  });
});
