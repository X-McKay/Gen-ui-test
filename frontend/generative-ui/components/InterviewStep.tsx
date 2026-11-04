"use client";

import { useGenerativeUIAccessibility } from "@copilotkit/react-core/v2/generative-ui";
import { ArrowRight, Loader2 } from "lucide-react";
import { useCallback, useId, useMemo, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { InterviewFormProvider, NOT_SURE, clearDraft, useInterviewForm } from "@/generative-ui/interviewForm";
import { cn } from "@/lib/utils";

export type InterviewSection = "project" | "ai_system" | "data" | "use_case" | "controls" | "summary";

export interface InterviewStepSubmission {
  answers: Record<string, unknown>;
  assumptions: Record<string, unknown>;
  notSure: string[];
}

export interface InterviewStepProps {
  intro: string;
  section: InterviewSection;
  confirmLabel?: string;
  assumptions?: ReactNode;
  questions?: ReactNode;
  findings?: ReactNode;
  onSubmit?: (args: InterviewStepSubmission) => Promise<{ ok: boolean; error?: Error } | unknown>;
}

const SECTION_LABELS: Record<InterviewSection, string> = {
  project: "Project",
  ai_system: "AI system",
  data: "Data",
  use_case: "Use case",
  controls: "Controls",
  summary: "Summary",
};

function SubmitBar({
  confirmLabel,
  complete,
  submitting,
  error,
}: {
  confirmLabel: string;
  complete: boolean;
  submitting: boolean;
  error: string | null;
}) {
  const form = useInterviewForm();
  const questionCount = Object.keys(form?.answers ?? {}).length;
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-4">
      <p className="text-xs text-muted-foreground" aria-live="polite">
        {error ? (
          <span className="text-destructive" role="alert" data-testid="step-error">
            {error}
          </span>
        ) : !complete ? (
          "Answer every question, or choose Not sure, to continue."
        ) : (
          "Everything here is saved when you confirm."
        )}
      </p>
      <Button
        type="submit"
        className="h-11 min-w-44 gap-2"
        disabled={!complete || submitting}
        data-testid="confirm-step"
        data-answers={questionCount}
      >
        {submitting ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
        {confirmLabel}
        {!submitting ? <ArrowRight className="size-4" aria-hidden="true" /> : null}
      </Button>
    </div>
  );
}

/** One interview step: intro, optional assumptions/findings, up to three questions, one confirm. */
export function InterviewStep({
  intro,
  section,
  confirmLabel = "Confirm and continue",
  assumptions,
  questions,
  findings,
  onSubmit,
}: InterviewStepProps) {
  const accessibility = useGenerativeUIAccessibility();
  const headingId = useId();
  const [complete, setComplete] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const stepKey = useMemo(() => `${section}:${intro.slice(0, 40)}`, [section, intro]);
  const handleChange = useCallback((state: { complete: boolean }) => setComplete(state.complete), []);

  return (
    <InterviewFormProvider stepKey={stepKey} submitting={submitting} onChange={handleChange}>
      <StepBody
        accessibility={accessibility}
        headingId={headingId}
        intro={intro}
        section={section}
        assumptions={assumptions}
        questions={questions}
        findings={findings}
        confirmLabel={confirmLabel}
        complete={complete}
        submitting={submitting}
        error={error}
        onSubmit={async (submission) => {
          if (!onSubmit) return;
          setSubmitting(true);
          setError(null);
          try {
            const result = (await onSubmit(submission)) as { ok?: boolean; error?: Error } | undefined;
            if (result && result.ok === false) {
              setError(result.error?.message ?? "Could not send your answers. Try again.");
              setSubmitting(false);
              return;
            }
            clearDraft(stepKey);
          } catch (cause) {
            setError(cause instanceof Error ? cause.message : "Could not send your answers. Try again.");
            setSubmitting(false);
          }
        }}
      />
    </InterviewFormProvider>
  );
}

function StepBody({
  accessibility,
  headingId,
  intro,
  section,
  assumptions,
  questions,
  findings,
  confirmLabel,
  complete,
  submitting,
  error,
  onSubmit,
}: {
  accessibility: ReturnType<typeof useGenerativeUIAccessibility>;
  headingId: string;
  intro: string;
  section: InterviewSection;
  assumptions?: ReactNode;
  questions?: ReactNode;
  findings?: ReactNode;
  confirmLabel: string;
  complete: boolean;
  submitting: boolean;
  error: string | null;
  onSubmit: (submission: InterviewStepSubmission) => Promise<void>;
}) {
  const form = useInterviewForm();
  const submit = () => {
    if (!form) return;
    const answers: Record<string, unknown> = {};
    const notSure: string[] = [];
    for (const [field, value] of Object.entries(form.answers)) {
      if (value === undefined) continue;
      answers[field] = value;
      if (value === NOT_SURE) notSure.push(field);
    }
    const assumptionsOut: Record<string, unknown> = {};
    for (const [field, value] of Object.entries(form.assumptions)) {
      assumptionsOut[field] = value;
      if (value === NOT_SURE) notSure.push(field);
    }
    void onSubmit({ answers, assumptions: assumptionsOut, notSure });
  };
  const hasQuestions = Boolean(questions);
  return (
    <form
      {...accessibility}
      data-testid="InterviewStep"
      data-section={section}
      aria-labelledby={headingId}
      className={cn(
        "surface-enter grid grid-cols-1 gap-6 rounded-[var(--radius)] border bg-card p-5 shadow-sm sm:p-6",
        submitting && "opacity-80",
      )}
      onSubmit={(event) => {
        event.preventDefault();
        if (complete && !submitting) submit();
      }}
    >
      <header className="grid gap-1">
        <p className="text-xs font-medium uppercase tracking-wide text-primary">{SECTION_LABELS[section]}</p>
        <h1 id={headingId} className="text-lg font-semibold leading-snug max-w-[70ch]" data-testid="step-intro">
          {intro}
        </h1>
      </header>
      {findings}
      {assumptions}
      {hasQuestions ? (
        <div className="grid gap-6" data-testid="step-questions">
          {questions}
        </div>
      ) : null}
      <SubmitBar confirmLabel={confirmLabel} complete={complete} submitting={submitting} error={error} />
    </form>
  );
}
