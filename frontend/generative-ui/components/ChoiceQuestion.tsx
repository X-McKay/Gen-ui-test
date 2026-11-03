"use client";

import { useGenerativeUIAccessibility } from "@copilotkit/react-core/v2/generative-ui";

import { NOT_SURE, useInterviewField } from "@/generative-ui/interviewForm";

import { QuestionShell, SegmentedChoice } from "./QuestionShell";

export interface ChoiceOption {
  value: string;
  label: string;
  description?: string;
}

export interface ChoiceQuestionProps {
  field: string;
  prompt: string;
  options: ChoiceOption[];
  whyAsked?: string;
  suggested?: string;
  required?: boolean;
}

export function ChoiceQuestion({ field, prompt, options, whyAsked, suggested, required = true }: ChoiceQuestionProps) {
  const accessibility = useGenerativeUIAccessibility();
  const [value, setValue] = useInterviewField<string>(field, {
    required,
    validate: (candidate) => options.some((option) => option.value === candidate),
  });
  const current = value === undefined && suggested ? suggested : value;
  const notSure = current === NOT_SURE;
  return (
    <div {...accessibility}>
      <QuestionShell
        field={field}
        prompt={prompt}
        whyAsked={whyAsked}
        testId="ChoiceQuestion"
        notSure={notSure}
        onNotSure={() => setValue(notSure ? undefined : NOT_SURE)}
        hint={value === undefined && suggested ? "Our best guess is preselected. Change it if needed." : undefined}
      >
        <SegmentedChoice
          ariaLabel={prompt}
          options={options}
          value={notSure ? undefined : (current as string | undefined)}
          onChange={(next) => setValue(next)}
        />
      </QuestionShell>
    </div>
  );
}
