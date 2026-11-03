import { describe, expect, it } from "vitest";

import { INTAKE_CATALOG_ID, intakeUI } from "@/generative-ui/intakeCatalog";

const EXPECTED_COMPONENTS = [
  "AssumptionReview",
  "ChoiceQuestion",
  "EscalationNotice",
  "FindingsReview",
  "InterviewStep",
  "MultiSelectQuestion",
  "ShortTextQuestion",
  "YesNoQuestion",
] as const;

type ComponentName = (typeof EXPECTED_COMPONENTS)[number];

/** The Standard Schema surface every props schema exposes (zod 4 implements it). */
interface StandardSchemaLike {
  "~standard": {
    validate: (input: unknown) => { issues?: readonly unknown[] } | Promise<{ issues?: readonly unknown[] }>;
  };
}

async function validate(name: ComponentName, input: unknown): Promise<boolean> {
  const component = intakeUI.components.get(name);
  if (!component?.props) throw new Error(`${name} has no props schema`);
  const schema = component.props as unknown as StandardSchemaLike;
  const result = await schema["~standard"].validate(input);
  return !(result.issues && result.issues.length > 0);
}

const OPTIONS = [
  { value: "pilot", label: "Pilot" },
  { value: "production", label: "Production" },
];

describe("intake catalog", () => {
  it("has exactly eight components under the published id", () => {
    expect(intakeUI.id).toBe(INTAKE_CATALOG_ID);
    expect(INTAKE_CATALOG_ID).toBe("intake/interview@1");
    expect([...intakeUI.components.keys()].sort()).toEqual([...EXPECTED_COMPONENTS]);
    for (const name of EXPECTED_COMPONENTS) expect(intakeUI.manifestComponents[name]).toBeDefined();
  });

  it.each([
    ["ChoiceQuestion", { prompt: "Where is the project in its lifecycle?", options: OPTIONS }],
    ["MultiSelectQuestion", { prompt: "Which areas does it operate in?", options: OPTIONS }],
    ["YesNoQuestion", { prompt: "Can a person review its outputs?" }],
    ["ShortTextQuestion", { prompt: "What is the project called?" }],
  ] as const)("%s accepts a valid field path and rejects an unknown one", async (name, props) => {
    expect(await validate(name, { ...props, field: "project.lifecycle_stage" })).toBe(true);
    expect(await validate(name, { ...props, field: "nonsense.path" })).toBe(false);
    expect(await validate(name, { ...props, field: "project" })).toBe(false);
    expect(await validate(name, { ...props, field: "project.Name" })).toBe(false);
  });

  it("AssumptionReview and FindingsReview check the field path of every item", async () => {
    const chip = {
      label: "Lifecycle stage",
      value: "pilot",
      displayValue: "Pilot",
      confidence: 0.8,
      source: "inferred",
    };
    expect(await validate("AssumptionReview", { assumptions: [{ ...chip, field: "project.lifecycle_stage" }] })).toBe(
      true,
    );
    expect(await validate("AssumptionReview", { assumptions: [{ ...chip, field: "marketing.budget" }] })).toBe(false);
    const finding = { ...chip, evidencePath: "README.md", snippet: "Pilot with two teams" };
    expect(await validate("FindingsReview", { findings: [{ ...finding, field: "project.lifecycle_stage" }] })).toBe(
      true,
    );
    expect(await validate("FindingsReview", { findings: [{ ...finding, field: "not-a-path" }] })).toBe(false);
  });

  it("InterviewStep and EscalationNotice accept valid props and reject malformed ones", async () => {
    expect(await validate("InterviewStep", { intro: "Here is what we understood.", section: "project" })).toBe(true);
    expect(await validate("InterviewStep", { intro: "", section: "project" })).toBe(false);
    expect(await validate("InterviewStep", { intro: "Hello.", section: "marketing" })).toBe(false);
    expect(
      await validate("EscalationNotice", {
        title: "Stop",
        reasons: ["Social scoring"],
        contact: "governance@example.com",
      }),
    ).toBe(true);
    expect(
      await validate("EscalationNotice", {
        title: "Stop",
        reasons: "Social scoring",
        contact: "governance@example.com",
      }),
    ).toBe(false);
  });

  it("limits the question controls to the declared option counts", async () => {
    const one = [{ value: "a", label: "A" }];
    expect(
      await validate("ChoiceQuestion", { field: "project.target_users", prompt: "Who will use it?", options: one }),
    ).toBe(false);
    const many = Array.from({ length: 15 }, (_, index) => ({ value: `v${index}`, label: `V${index}` }));
    expect(
      await validate("MultiSelectQuestion", { field: "use_case.domains", prompt: "Which areas?", options: many }),
    ).toBe(false);
  });
});
