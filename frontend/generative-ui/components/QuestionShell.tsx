"use client";

import { HelpCircle } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface QuestionShellProps {
  field: string;
  prompt: string;
  whyAsked?: string;
  testId: string;
  children: ReactNode;
  notSure: boolean;
  onNotSure: () => void;
  hint?: string;
  error?: string | null;
}

/** Layout shared by every question: prompt, optional "why we ask", control, Not sure. */
export function QuestionShell({
  field,
  prompt,
  whyAsked,
  testId,
  children,
  notSure,
  onNotSure,
  hint,
  error,
}: QuestionShellProps) {
  const labelId = `${field}-label`;
  const hintId = whyAsked ? `${field}-why` : undefined;
  return (
    <fieldset
      className="surface-enter grid gap-3 border-0 p-0 m-0 min-w-0"
      data-testid={testId}
      data-field={field}
      aria-labelledby={labelId}
      aria-describedby={hintId}
    >
      <legend className="sr-only">{prompt}</legend>
      <div className="grid gap-1">
        <p id={labelId} className="text-base font-medium leading-snug text-foreground max-w-[70ch]">
          {prompt}
        </p>
        {whyAsked ? (
          <p id={hintId} className="flex items-start gap-1.5 text-sm text-muted-foreground max-w-[70ch]">
            <HelpCircle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            <span>{whyAsked}</span>
          </p>
        ) : null}
      </div>
      <div className={cn("grid gap-2", notSure && "opacity-60")}>{children}</div>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <Button
          type="button"
          variant={notSure ? "secondary" : "ghost"}
          size="sm"
          aria-pressed={notSure}
          aria-label={`Not sure: ${prompt}`}
          data-testid="not-sure"
          className={cn("h-11 min-w-11 px-3 text-sm", notSure && "ring-1 ring-ring")}
          onClick={onNotSure}
        >
          Not sure
        </Button>
        {error ? (
          <p className="text-sm text-destructive" role="alert" data-testid="question-error">
            {error}
          </p>
        ) : hint ? (
          <p className="text-xs text-muted-foreground">{hint}</p>
        ) : null}
      </div>
    </fieldset>
  );
}

interface SegmentedProps {
  options: { value: string; label: string; description?: string }[];
  value: string | undefined;
  onChange: (value: string) => void;
  ariaLabel: string;
  multiple?: false;
  disabled?: boolean;
}

interface MultiSegmentedProps {
  options: { value: string; label: string; description?: string }[];
  value: string[];
  onChange: (value: string[]) => void;
  ariaLabel: string;
  multiple: true;
  disabled?: boolean;
}

/** Segmented control (single) or chip group (multiple) with ≥ 44 px hit targets. */
export function SegmentedChoice(props: SegmentedProps | MultiSegmentedProps) {
  const { options, ariaLabel, disabled } = props;
  const isMultiple = props.multiple === true;
  const selected = new Set<string>(isMultiple ? props.value : props.value ? [props.value] : []);
  return (
    <div
      role={isMultiple ? "group" : "radiogroup"}
      aria-label={ariaLabel}
      className={cn(
        "flex flex-wrap gap-2",
        !isMultiple && options.length <= 4 && "sm:inline-flex sm:rounded-[var(--radius)] sm:bg-muted sm:p-1 sm:gap-1",
      )}
    >
      {options.map((option) => {
        const active = selected.has(option.value);
        return (
          <button
            key={option.value}
            type="button"
            role={isMultiple ? "checkbox" : "radio"}
            aria-checked={active}
            aria-label={option.label}
            disabled={disabled}
            data-state={active ? "on" : "off"}
            data-value={option.value}
            onClick={() => {
              if (isMultiple) {
                const next = new Set(selected);
                if (next.has(option.value)) next.delete(option.value);
                else next.add(option.value);
                props.onChange(Array.from(next));
              } else {
                props.onChange(option.value);
              }
            }}
            className={cn(
              "min-h-11 rounded-[calc(var(--radius)-2px)] border px-4 py-2 text-sm font-medium transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
              "disabled:opacity-50 disabled:pointer-events-none",
              active
                ? "border-primary bg-primary text-primary-foreground shadow-sm"
                : "border-border bg-background text-foreground hover:bg-accent hover:text-accent-foreground",
              !isMultiple && options.length <= 4 && "sm:border-transparent sm:bg-transparent sm:shadow-none",
              !isMultiple && options.length <= 4 && active && "sm:bg-background sm:text-foreground sm:shadow-sm",
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
