"use client";

import { useGenerativeUIAccessibility } from "@copilotkit/react-core/v2/generative-ui";
import { useEffect } from "react";

import { NOT_SURE, useInterviewField } from "@/generative-ui/interviewForm";

import type { ChoiceOption } from "./ChoiceQuestion";
import { QuestionShell, SegmentedChoice } from "./QuestionShell";

export interface MultiSelectQuestionProps {
  field: string;
  prompt: string;
  options: ChoiceOption[];
  whyAsked?: string;
  suggested?: string[];
  required?: boolean;
  minSelected?: number;
}

export function MultiSelectQuestion({
  field,
  prompt,
  options,
  whyAsked,
  suggested,
  required = true,
  minSelected = 1,
}: MultiSelectQuestionProps) {
  const accessibility = useGenerativeUIAccessibility();
  const [value, setValue] = useInterviewField<string[]>(field, {
    required,
    validate: (candidate) => Array.isArray(candidate) && candidate.length >= minSelected,
  });
  useEffect(() => {
    // A confident guess is pre-filled so the user only has to confirm it.
    if (value === undefined && suggested !== undefined && suggested.length > 0) setValue(suggested);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only on mount
  }, []);
  const current = value === undefined && suggested && suggested.length > 0 ? suggested : value;
  const notSure = current === NOT_SURE;
  const selected = Array.isArray(current) ? current : [];
  return (
    <div {...accessibility}>
      <QuestionShell
        field={field}
        prompt={prompt}
        whyAsked={whyAsked}
        testId="MultiSelectQuestion"
        notSure={notSure}
        onNotSure={() => setValue(notSure ? undefined : NOT_SURE)}
        hint={value === undefined && suggested && suggested.length > 0 ? "Our best guess is preselected. Change it if needed." : "Select all that apply."}
      >
        <SegmentedChoice
          multiple
          ariaLabel={prompt}
          options={options}
          value={notSure ? [] : selected}
          onChange={(next) => setValue(next)}
        />
      </QuestionShell>
    </div>
  );
}
