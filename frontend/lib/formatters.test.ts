import { describe, expect, it } from "vitest";

import {
  confidenceLevel,
  EMPTY_VALUE,
  formatConfidence,
  formatDate,
  formatQuestionCount,
  formatRepoUrl,
  formatSource,
  formatValue,
  truncatePath,
  UNKNOWN_VALUE,
} from "@/lib/formatters";

describe("formatConfidence", () => {
  it("renders a fraction as a rounded percentage", () => {
    expect(formatConfidence(0.92)).toBe("92%");
    expect(formatConfidence(0.005)).toBe("1%");
  });

  it("clamps values outside 0–1 and tolerates NaN", () => {
    expect(formatConfidence(1.7)).toBe("100%");
    expect(formatConfidence(-3)).toBe("0%");
    expect(formatConfidence(Number.NaN)).toBe("0%");
  });
});

describe("confidenceLevel", () => {
  it("buckets at 0.5 and 0.8", () => {
    expect(confidenceLevel(0.2)).toBe("low");
    expect(confidenceLevel(0.5)).toBe("medium");
    expect(confidenceLevel(0.79)).toBe("medium");
    expect(confidenceLevel(0.8)).toBe("high");
  });
});

describe("formatValue", () => {
  it("shows a dash for nothing and Not sure for unknown", () => {
    expect(formatValue("project.name", null)).toBe(EMPTY_VALUE);
    expect(formatValue("project.name", undefined)).toBe(EMPTY_VALUE);
    expect(formatValue("project.name", "   ")).toBe(EMPTY_VALUE);
    expect(formatValue("project.name", "unknown")).toBe(UNKNOWN_VALUE);
  });

  it("renders booleans as Yes / No", () => {
    expect(formatValue("ai_system.uses_ai", true)).toBe("Yes");
    expect(formatValue("ai_system.uses_ai", false)).toBe("No");
  });

  it("maps option values to labels, scoped to the field", () => {
    expect(formatValue("project.lifecycle_stage", "pilot")).toBe("Pilot");
    expect(formatValue("use_case.domains", ["hr_employment", "other"])).toBe("HR and employment, None of these");
    expect(formatValue("project.target_users", "public")).toBe("The general public");
    expect(formatValue("data.data_subjects", ["public"])).toBe("Members of the public");
  });

  it("keeps free text as typed and falls back to the raw value for unknown options", () => {
    expect(formatValue("project.name", "Candidate summary assistant")).toBe("Candidate summary assistant");
    expect(formatValue("project.lifecycle_stage", "beta")).toBe("beta");
  });

  it("renders empty lists as None and unwraps rationale value wrappers", () => {
    expect(formatValue("use_case.domains", [])).toBe("None");
    expect(formatValue("use_case.domains", { value: ["education"] })).toBe("Education");
    expect(formatValue("project.name", 42)).toBe("42");
  });
});

describe("formatSource", () => {
  it("describes who set the value", () => {
    expect(formatSource(null, false)).toBe("Not set");
    expect(formatSource("user", false)).toBe("You entered");
    expect(formatSource("user", true)).toBe("You confirmed");
    expect(formatSource(null, true)).toBe("You confirmed");
    expect(formatSource("inferred", false)).toBe("Inferred from your description");
    expect(formatSource("repo:README.md", false)).toBe("Repository: README.md");
    expect(formatSource("somewhere-else", false)).toBe("somewhere-else");
  });
});

describe("formatDate", () => {
  it("returns a dash for missing or invalid dates and formats valid ones", () => {
    expect(formatDate(null)).toBe(EMPTY_VALUE);
    expect(formatDate("not a date")).toBe(EMPTY_VALUE);
    const formatted = formatDate("2026-11-03T09:30:00Z", { timeZone: "UTC" });
    expect(formatted).toContain("2026");
    expect(formatted).toContain("Nov");
    expect(formatted).toContain("09:30");
  });
});

describe("truncatePath", () => {
  it("leaves short paths alone", () => {
    expect(truncatePath("src/app.py")).toBe("src/app.py");
  });

  it("keeps the head and the file name, eliding the middle", () => {
    const result = truncatePath("src/app/services/scoring/model/weights/loader.py", 32);
    expect(result.length).toBeLessThanOrEqual(32);
    expect(result.startsWith("src/…/")).toBe(true);
    expect(result.endsWith("loader.py")).toBe(true);
  });

  it("elides two-segment paths from the front", () => {
    const result = truncatePath("averyveryverylongdirectoryname/averyveryverylongfilename.py", 20);
    expect(result.startsWith("…")).toBe(true);
    expect(result.length).toBeLessThanOrEqual(20);
  });
});

describe("formatQuestionCount", () => {
  it("pluralises correctly", () => {
    expect(formatQuestionCount(undefined)).toBe("Answered in 0 questions");
    expect(formatQuestionCount(1)).toBe("Answered in 1 question");
    expect(formatQuestionCount(6)).toBe("Answered in 6 questions");
  });
});

describe("formatRepoUrl", () => {
  it("shortens to host/org/repo and strips .git", () => {
    expect(formatRepoUrl("https://github.com/intake-fixtures/hr-screening.git")).toBe(
      "github.com/intake-fixtures/hr-screening",
    );
    expect(formatRepoUrl("https://github.com/intake-fixtures/hr-screening/")).toBe(
      "github.com/intake-fixtures/hr-screening",
    );
    expect(formatRepoUrl(null)).toBe(EMPTY_VALUE);
    expect(formatRepoUrl("not a url")).toBe("not a url");
  });
});
