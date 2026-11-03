"use client";

import { useGenerativeUIAccessibility } from "@copilotkit/react-core/v2/generative-ui";
import { useId, useMemo } from "react";

import { Input } from "@/components/ui/input";
import { NOT_SURE, useInterviewField } from "@/generative-ui/interviewForm";

import { QuestionShell } from "./QuestionShell";

export interface TextChecks {
  required?: boolean;
  minLength?: number;
  maxLength?: number;
  pattern?: string;
  message?: string;
}

export interface ShortTextQuestionProps {
  field: string;
  prompt: string;
  placeholder?: string;
  whyAsked?: string;
  suggested?: string;
  checks?: TextChecks;
}

function violation(value: string, checks: TextChecks | undefined): string | null {
  if (!checks) return null;
  const trimmed = value.trim();
  if (checks.required && trimmed.length === 0) return "This answer is required.";
  if (checks.minLength !== undefined && trimmed.length < checks.minLength) {
    return `Use at least ${checks.minLength} characters.`;
  }
  if (checks.maxLength !== undefined && trimmed.length > checks.maxLength) {
    return `Use at most ${checks.maxLength} characters.`;
  }
  if (checks.pattern) {
    try {
      if (!new RegExp(checks.pattern).test(trimmed)) return checks.message ?? "That does not look right.";
    } catch {
      return null;
    }
  }
  return null;
}

export function ShortTextQuestion({ field, prompt, placeholder, whyAsked, suggested, checks }: ShortTextQuestionProps) {
  const accessibility = useGenerativeUIAccessibility();
  const required = checks?.required ?? true;
  const [value, setValue] = useInterviewField<string>(field, {
    required,
    validate: (candidate) => typeof candidate === "string" && violation(candidate, checks) === null,
  });
  const inputId = useId();
  const notSure = value === NOT_SURE;
  const text = typeof value === "string" && value !== NOT_SURE ? value : "";
  const error = useMemo(() => (text.length > 0 ? violation(text, checks) : null), [text, checks]);
  return (
    <div {...accessibility}>
      <QuestionShell
        field={field}
        prompt={prompt}
        whyAsked={whyAsked}
        testId="ShortTextQuestion"
        notSure={notSure}
        onNotSure={() => setValue(notSure ? undefined : NOT_SURE)}
        error={error}
      >
        <Input
          id={inputId}
          aria-label={prompt}
          aria-invalid={error !== null}
          placeholder={placeholder ?? suggested ?? ""}
          value={text}
          disabled={notSure}
          maxLength={checks?.maxLength ?? 500}
          className="h-11 max-w-[70ch] text-base"
          onChange={(event) => setValue(event.target.value)}
          onBlur={() => {
            if (text.trim().length === 0 && !notSure) setValue(undefined);
          }}
        />
      </QuestionShell>
    </div>
  );
}
