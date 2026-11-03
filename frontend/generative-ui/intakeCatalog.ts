/**
 * The only components the agent may render. Eight conversational moves, strict props.
 * The agent describes UI as A2UI 1.0 operations; the CopilotKit runtime validates every
 * operation against this catalog before it reaches the page.
 */
import { createGenerativeUI } from "@copilotkit/react-core/v2/generative-ui";
import { z } from "zod";

import { AssumptionReview } from "./components/AssumptionReview";
import { ChoiceQuestion } from "./components/ChoiceQuestion";
import { EscalationNotice } from "./components/EscalationNotice";
import { FindingsReview } from "./components/FindingsReview";
import { InterviewStep } from "./components/InterviewStep";
import { MultiSelectQuestion } from "./components/MultiSelectQuestion";
import { ShortTextQuestion } from "./components/ShortTextQuestion";
import { YesNoQuestion } from "./components/YesNoQuestion";

export const INTAKE_CATALOG_ID = "intake/interview@1";
export const INTERVIEW_TARGET_ID = "interview";

const option = z.object({
  value: z.string().min(1).max(80),
  label: z.string().min(1).max(80),
  description: z.string().max(160).optional(),
});

const control = z.enum(["choice", "multi", "yes_no", "text"]);
const fieldPath = z.string().regex(/^(project|ai_system|data|use_case)\.[a-z_]+$/, "a dotted field path");
const questionPrompt = z.string().min(4).max(160);

export const intakeUI = createGenerativeUI({
  id: INTAKE_CATALOG_ID,
  components: {
    InterviewStep: {
      component: InterviewStep,
      description:
        "One interview step: a short intro (two sentences at most), optional assumptions or findings to confirm, and up to three questions. It owns the single confirm button; use it as the root of every step.",
      props: z.object({
        intro: z.string().min(1).max(320),
        section: z.enum(["project", "ai_system", "data", "use_case", "summary"]),
        confirmLabel: z.string().max(40).optional(),
      }),
      slots: { assumptions: "single", questions: "multiple", findings: "single" },
      events: {
        onSubmit: {
          description: "The user confirmed the step. Carries every answer and assumption value.",
          parameters: z.object({
            answers: z.record(z.string(), z.unknown()),
            assumptions: z.record(z.string(), z.unknown()),
            notSure: z.array(z.string()),
          }),
        },
      },
    },
    AssumptionReview: {
      component: AssumptionReview,
      description: "Values inferred from the description, shown as chips the user confirms in bulk or edits.",
      props: z.object({
        title: z.string().max(60).optional(),
        assumptions: z
          .array(
            z.object({
              field: fieldPath,
              label: z.string().max(60),
              value: z.unknown(),
              displayValue: z.string().max(200),
              confidence: z.number().min(0).max(1),
              source: z.string().max(200),
              mustConfirm: z.boolean().optional(),
              control: control.optional(),
              options: z.array(option).optional(),
            }),
          )
          .max(40),
      }),
    },
    ChoiceQuestion: {
      component: ChoiceQuestion,
      description: "Pick exactly one option (segmented control). Not sure is always offered.",
      props: z.object({
        field: fieldPath,
        prompt: questionPrompt,
        options: z.array(option).min(2).max(12),
        whyAsked: z.string().max(160).optional(),
        suggested: z.string().max(80).optional(),
        required: z.boolean().optional(),
      }),
    },
    MultiSelectQuestion: {
      component: MultiSelectQuestion,
      description: "Pick any number of options (chips). Not sure is always offered.",
      props: z.object({
        field: fieldPath,
        prompt: questionPrompt,
        options: z.array(option).min(2).max(14),
        whyAsked: z.string().max(160).optional(),
        suggested: z.array(z.string().max(80)).optional(),
        required: z.boolean().optional(),
        minSelected: z.number().int().min(0).max(5).optional(),
      }),
    },
    YesNoQuestion: {
      component: YesNoQuestion,
      description: "A yes / no question with Not sure. Use for every boolean field.",
      props: z.object({
        field: fieldPath,
        prompt: questionPrompt,
        whyAsked: z.string().max(160).optional(),
        suggested: z.enum(["yes", "no"]).optional(),
        required: z.boolean().optional(),
      }),
    },
    ShortTextQuestion: {
      component: ShortTextQuestion,
      description: "A short free-text answer, only when options cannot be enumerated. Client-side checks run in the browser.",
      props: z.object({
        field: fieldPath,
        prompt: questionPrompt,
        placeholder: z.string().max(120).optional(),
        whyAsked: z.string().max(160).optional(),
        suggested: z.string().max(200).optional(),
        checks: z
          .object({
            required: z.boolean().optional(),
            minLength: z.number().int().min(0).optional(),
            maxLength: z.number().int().min(1).max(2000).optional(),
            pattern: z.string().max(200).optional(),
            message: z.string().max(160).optional(),
          })
          .optional(),
      }),
    },
    FindingsReview: {
      component: FindingsReview,
      description: "Repository findings as a table: field, inferred value, evidence path and snippet, confidence. The user confirms all or corrects rows inline.",
      props: z.object({
        title: z.string().max(80).optional(),
        findings: z
          .array(
            z.object({
              field: fieldPath,
              label: z.string().max(60),
              value: z.unknown(),
              displayValue: z.string().max(200),
              confidence: z.number().min(0).max(1),
              evidencePath: z.string().max(300),
              snippet: z.string().max(400),
              control: control.optional(),
              options: z.array(option).optional(),
            }),
          )
          .max(60),
      }),
    },
    EscalationNotice: {
      component: EscalationNotice,
      description: "Stops the flow when a prohibited practice is confirmed. Use it alone as the root.",
      props: z.object({
        title: z.string().max(80),
        reasons: z.array(z.string().max(300)).max(10),
        contact: z.string().max(200),
      }),
      events: {
        onAcknowledge: {
          description: "The user acknowledged the escalation.",
          parameters: z.object({}),
        },
      },
    },
  },
});

export type IntakeUI = typeof intakeUI;
