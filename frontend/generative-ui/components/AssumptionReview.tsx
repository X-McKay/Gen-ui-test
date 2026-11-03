"use client";

import { useGenerativeUIAccessibility } from "@copilotkit/react-core/v2/generative-ui";
import { Check, Info, Pencil } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { NOT_SURE, useInterviewForm } from "@/generative-ui/interviewForm";
import { cn } from "@/lib/utils";

import type { ChoiceOption } from "./ChoiceQuestion";
import { ConfidenceDots } from "./ConfidenceDots";
import { SegmentedChoice } from "./QuestionShell";

export interface AssumptionItem {
  field: string;
  label: string;
  value: unknown;
  displayValue: string;
  confidence: number;
  source: string;
  mustConfirm?: boolean;
  control?: "choice" | "multi" | "yes_no" | "text";
  options?: ChoiceOption[];
}

export interface AssumptionReviewProps {
  title?: string;
  assumptions: AssumptionItem[];
}

function sourceLabel(source: string): string {
  if (source === "user") return "You told us";
  if (source.startsWith("repo:")) return `Repository: ${source.slice(5)}`;
  return "Inferred from your description";
}

function labelFor(item: AssumptionItem, value: unknown): string {
  if (value === NOT_SURE) return "Not sure";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  const labels = new Map((item.options ?? []).map((option) => [option.value, option.label]));
  if (Array.isArray(value)) return value.length ? value.map((v) => labels.get(String(v)) ?? String(v)).join(", ") : "None";
  if (value === undefined || value === null) return "—";
  return labels.get(String(value)) ?? String(value);
}

/** One editable chip: value, confidence, provenance, confirm and edit. */
function Chip({ item }: { item: AssumptionItem }) {
  const form = useInterviewForm();
  const [editing, setEditing] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const value = form?.assumptions[item.field] ?? item.value;
  const edited = JSON.stringify(value) !== JSON.stringify(item.value);
  const state = editing ? "editing" : confirmed || edited ? "confirmed" : "pending";

  useEffect(() => {
    // Every chip is part of the bulk confirmation; register its current value.
    form?.setAssumption(item.field, item.value);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- register once per chip
  }, [item.field]);

  const setValue = (next: unknown) => {
    form?.setAssumption(item.field, next);
  };

  const editor = useMemo(() => {
    if (!editing) return null;
    const control = item.control ?? "text";
    if (control === "yes_no") {
      return (
        <SegmentedChoice
          ariaLabel={`Edit ${item.label}`}
          options={[
            { value: "yes", label: "Yes" },
            { value: "no", label: "No" },
            { value: NOT_SURE, label: "Not sure" },
          ]}
          value={value === true ? "yes" : value === false ? "no" : value === NOT_SURE ? NOT_SURE : undefined}
          onChange={(next) => setValue(next === NOT_SURE ? NOT_SURE : next === "yes")}
        />
      );
    }
    if (control === "choice") {
      return (
        <SegmentedChoice
          ariaLabel={`Edit ${item.label}`}
          options={[...(item.options ?? []), { value: NOT_SURE, label: "Not sure" }]}
          value={typeof value === "string" ? value : undefined}
          onChange={(next) => setValue(next)}
        />
      );
    }
    if (control === "multi") {
      return (
        <SegmentedChoice
          multiple
          ariaLabel={`Edit ${item.label}`}
          options={item.options ?? []}
          value={Array.isArray(value) ? value.map(String) : []}
          onChange={(next) => setValue(next)}
        />
      );
    }
    return (
      <Input
        aria-label={`Edit ${item.label}`}
        className="h-11 max-w-[60ch]"
        value={typeof value === "string" && value !== NOT_SURE ? value : ""}
        onChange={(event) => setValue(event.target.value)}
      />
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps -- setValue is stable per chip
  }, [editing, item, value]);

  return (
    <li
      className={cn(
        "surface-enter grid gap-2 rounded-[var(--radius)] border bg-card p-2 pl-3 transition-colors",
        state === "confirmed" && "border-primary/50 bg-primary/5",
        state === "editing" && "border-ring",
      )}
      data-testid="assumption-chip"
      data-field={item.field}
      data-state={state}
    >
      <div className="flex items-center gap-2 flex-wrap">
        <Popover>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="flex min-h-9 items-center gap-2 rounded-md px-1 text-left text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label={`Provenance for ${item.label}`}
            >
              <span className="text-muted-foreground">{item.label}</span>
              <span className="font-medium text-foreground">{labelFor(item, value)}</span>
              <ConfidenceDots confidence={item.confidence} />
              <Info className="size-3.5 text-muted-foreground" aria-hidden="true" />
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-72 text-sm" align="start">
            <p className="font-medium">{item.label}</p>
            <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-muted-foreground">
              <dt>Source</dt>
              <dd className="text-foreground">{sourceLabel(item.source)}</dd>
              <dt>Confidence</dt>
              <dd className="text-foreground tabular-nums">{Math.round(item.confidence * 100)}%</dd>
              <dt>Confirmed</dt>
              <dd className="text-foreground">{state === "confirmed" ? "Yes" : "Not yet"}</dd>
            </dl>
            {item.mustConfirm ? (
              <p className="mt-2 text-xs text-muted-foreground">This value changes the classification, so we ask you to confirm it.</p>
            ) : null}
          </PopoverContent>
        </Popover>
        <span className="ml-auto inline-flex items-center gap-1">
          <Button
            type="button"
            size="icon"
            variant={state === "confirmed" ? "default" : "ghost"}
            className={cn("size-9 transition-transform", state === "confirmed" && "chip-confirmed")}
            aria-label={`Confirm ${item.label}`}
            aria-pressed={state === "confirmed"}
            onClick={() => {
              setConfirmed(true);
              setEditing(false);
            }}
          >
            <Check className="size-4" aria-hidden="true" />
          </Button>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="size-9"
            aria-label={`Edit ${item.label}`}
            aria-pressed={editing}
            onClick={() => {
              setEditing((open) => !open);
              setConfirmed(false);
            }}
          >
            <Pencil className="size-4" aria-hidden="true" />
          </Button>
        </span>
      </div>
      {editor ? (
        <div className="pb-1" data-testid="assumption-editor">
          {editor}
        </div>
      ) : null}
    </li>
  );
}

export function AssumptionReview({ title = "What we understood", assumptions }: AssumptionReviewProps) {
  const accessibility = useGenerativeUIAccessibility();
  if (assumptions.length === 0) return null;
  return (
    <section {...accessibility} data-testid="AssumptionReview" aria-label={title} className="grid gap-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">{title}</h2>
        <p className="text-xs text-muted-foreground">Confirming the step confirms every chip. Edit anything that is off.</p>
      </div>
      <ul className="grid gap-2 sm:grid-cols-2" role="list">
        {assumptions.map((item) => (
          <Chip key={item.field} item={item} />
        ))}
      </ul>
    </section>
  );
}
