"use client";

import { useGenerativeUIAccessibility } from "@copilotkit/react-core/v2/generative-ui";
import { useEffect } from "react";

import { NOT_SURE, useInterviewField } from "@/generative-ui/interviewForm";

import { QuestionShell, SegmentedChoice } from "./QuestionShell";

export interface YesNoQuestionProps {
  field: string;
  prompt: string;
  whyAsked?: string;
  suggested?: "yes" | "no";
  required?: boolean;
}

export function YesNoQuestion({ field, prompt, whyAsked, suggested, required = true }: YesNoQuestionProps) {
  const accessibility = useGenerativeUIAccessibility();
  const [value, setValue] = useInterviewField<boolean>(field, { required });
  useEffect(() => {
    // A confident guess is pre-filled so the user only has to confirm it.
    if (value === undefined && suggested !== undefined) setValue(suggested === "yes");
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only on mount
  }, []);
  const current = value === undefined && suggested ? suggested === "yes" : value;
  const notSure = current === NOT_SURE;
  const selected = current === true ? "yes" : current === false ? "no" : undefined;
  return (
    <div {...accessibility}>
      <QuestionShell
        field={field}
        prompt={prompt}
        whyAsked={whyAsked}
        testId="YesNoQuestion"
        notSure={notSure}
        onNotSure={() => setValue(notSure ? undefined : NOT_SURE)}
        hint={value === undefined && suggested ? "Our best guess is preselected. Change it if needed." : undefined}
      >
        <SegmentedChoice
          ariaLabel={prompt}
          options={[
            { value: "yes", label: "Yes" },
            { value: "no", label: "No" },
          ]}
          value={notSure ? undefined : selected}
          onChange={(next) => setValue(next === "yes")}
        />
      </QuestionShell>
    </div>
  );
}
