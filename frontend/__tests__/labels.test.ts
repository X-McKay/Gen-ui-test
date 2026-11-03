import { describe, expect, it } from "vitest";

import {
  annexLabel,
  FIELD_CONTROLS,
  FIELD_LABELS,
  FIELD_OPTIONS,
  FIELD_SPECS,
  fieldLabel,
  frameworkLabel,
  MUST_CONFIRM_FIELDS,
  optionLabel,
  SECTION_FIELDS,
  SECTION_ORDER,
  sectionOf,
  TIER_LABELS,
} from "@/lib/labels";

/** `backend/app/intake/question_bank.py`, QUESTION_BANK order. Keep in sync. */
const QUESTION_BANK_ORDER = [
  "ai_system.uses_ai",
  "data.processes_personal_data",
  "use_case.domains",
  "use_case.affects_legal_or_significant_effects",
  "project.name",
  "project.owner",
  "project.lifecycle_stage",
  "project.target_users",
  "project.description",
  "project.team",
  "project.business_unit",
  "project.deployment_regions",
  "ai_system.model_source",
  "ai_system.autonomy_level",
  "ai_system.human_oversight",
  "ai_system.gpai_model_used",
  "ai_system.fine_tuned_or_trained",
  "ai_system.model_types",
  "ai_system.model_providers",
  "data.special_category_data",
  "data.data_subjects",
  "data.biometric_identification",
  "data.pii_categories",
  "data.trains_on_personal_data",
  "data.cross_border_transfer",
  "data.retention_policy",
  "data.data_sources",
  "use_case.purpose",
  "use_case.interacts_directly_with_people",
  "use_case.generates_synthetic_content",
  "use_case.emotion_recognition",
  "use_case.social_scoring",
  "use_case.remote_biometric_id_public_spaces",
  "use_case.manipulative_or_subliminal",
  "use_case.untargeted_facial_scraping",
] as const;

const CONTROLS = new Set(["choice", "multi", "yes_no", "text"]);

describe("question bank coverage", () => {
  it.each(QUESTION_BANK_ORDER)("%s has a label and a control", (field) => {
    expect(FIELD_LABELS[field]).toEqual(expect.any(String));
    expect(FIELD_LABELS[field].trim().length).toBeGreaterThan(0);
    expect(CONTROLS.has(FIELD_CONTROLS[field])).toBe(true);
  });

  it("covers exactly the fields in the question bank", () => {
    const specFields = FIELD_SPECS.map((spec) => spec.field).sort();
    expect(specFields).toEqual([...QUESTION_BANK_ORDER].sort());
    expect(new Set(specFields).size).toBe(specFields.length);
  });

  it("gives every choice and multi field at least two options, and none to yes/no or text fields", () => {
    for (const spec of FIELD_SPECS) {
      if (spec.control === "choice" || spec.control === "multi") {
        expect(FIELD_OPTIONS[spec.field].length, spec.field).toBeGreaterThanOrEqual(2);
      } else {
        expect(FIELD_OPTIONS[spec.field], spec.field).toEqual([]);
      }
    }
  });

  it("keeps every field inside its own section, in record order", () => {
    for (const section of SECTION_ORDER) {
      const fields = SECTION_FIELDS[section];
      expect(fields.length).toBeGreaterThan(0);
      for (const field of fields) expect(sectionOf(field)).toBe(section);
      const fromSpecs = FIELD_SPECS.filter((spec) => spec.section === section).map((spec) => spec.field);
      expect(fields).toEqual(fromSpecs);
    }
    expect(sectionOf("nowhere.field")).toBeNull();
  });

  it("marks the sensitive gates as must-confirm", () => {
    expect(MUST_CONFIRM_FIELDS.has("use_case.domains")).toBe(true);
    expect(MUST_CONFIRM_FIELDS.has("data.biometric_identification")).toBe(true);
    expect(MUST_CONFIRM_FIELDS.has("project.name")).toBe(false);
  });
});

describe("label helpers", () => {
  it("falls back to a readable last segment for unknown paths", () => {
    expect(fieldLabel("use_case.domains")).toBe("Domains");
    expect(fieldLabel("assessment.overall_risk_tier")).toBe("Overall risk tier");
  });

  it("scopes option labels to the field and falls back to the raw value", () => {
    expect(optionLabel("use_case.domains", "other")).toBe("None of these");
    expect(optionLabel("ai_system.model_types", "other")).toBe("Other");
    expect(optionLabel("use_case.domains", "nonsense")).toBe("nonsense");
  });

  it("labels frameworks, tiers and Annex III categories", () => {
    expect(frameworkLabel("eu_ai_act")).toBe("EU AI Act");
    expect(frameworkLabel("GDPR")).toBe("GDPR");
    expect(frameworkLabel("custom")).toBe("custom");
    expect(TIER_LABELS.high_risk).toBe("High risk");
    expect(annexLabel("hr_employment")).toContain("Employment");
    expect(annexLabel("other")).toBe("None of these");
  });
});
