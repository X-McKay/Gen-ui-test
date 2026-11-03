"use client";

import { useGenerativeUIAccessibility } from "@copilotkit/react-core/v2/generative-ui";
import { Pencil, Undo2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NOT_SURE, useInterviewForm } from "@/generative-ui/interviewForm";
import { FIELD_CONTROLS, FIELD_OPTIONS } from "@/lib/labels";
import { cn } from "@/lib/utils";

import type { ChoiceOption } from "./ChoiceQuestion";

function controlFor(field: string): "choice" | "multi" | "yes_no" | "text" {
  return FIELD_CONTROLS[field] ?? "text";
}

function optionsFor(field: string): ChoiceOption[] {
  return (FIELD_OPTIONS[field] ?? []).map((option) => ({ value: option.value, label: option.label }));
}
import { ConfidenceDots } from "./ConfidenceDots";
import { SegmentedChoice } from "./QuestionShell";

export interface FindingItem {
  field: string;
  label: string;
  value: unknown;
  displayValue: string;
  confidence: number;
  evidencePath: string;
  snippet: string;
}

export interface FindingsReviewProps {
  title?: string;
  findings: FindingItem[];
}

function labelFor(item: FindingItem, value: unknown): string {
  if (JSON.stringify(value) === JSON.stringify(item.value) && item.displayValue) return item.displayValue;
  if (value === NOT_SURE) return "Not sure";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  const labels = new Map(optionsFor(item.field).map((option) => [option.value, option.label]));
  if (Array.isArray(value)) return value.length ? value.map((v) => labels.get(String(v)) ?? String(v)).join(", ") : "None";
  if (value === undefined || value === null) return "—";
  return labels.get(String(value)) ?? String(value);
}

function Evidence({ item }: { item: FindingItem }) {
  return (
    <div className="grid gap-1 text-xs">
      <code className="truncate font-mono text-[11px] text-muted-foreground" title={item.evidencePath}>
        {item.evidencePath}
      </code>
      <code className="line-clamp-2 whitespace-pre-wrap break-words rounded bg-muted px-1.5 py-1 font-mono text-[11px] text-foreground/80">
        {item.snippet}
      </code>
    </div>
  );
}

function Row({ item }: { item: FindingItem }) {
  const form = useInterviewForm();
  const [editing, setEditing] = useState(false);
  const value = form?.assumptions[item.field] ?? item.value;
  const corrected = JSON.stringify(value) !== JSON.stringify(item.value);
  useEffect(() => {
    form?.setAssumption(item.field, item.value);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- register once per row
  }, [item.field]);
  const setValue = (next: unknown) => form?.setAssumption(item.field, next);
  const control = controlFor(item.field);
  return (
    <tr
      data-testid="finding-row"
      data-field={item.field}
      data-state={editing ? "editing" : corrected ? "corrected" : "pending"}
      className={cn("align-top", corrected && "bg-primary/5")}
    >
      <th scope="row" className="py-3 pr-3 text-left text-sm font-medium text-foreground break-words">
        {item.label}
      </th>
      <td className="py-3 pr-3 text-sm">
        {editing ? (
          <div className="grid gap-2" data-testid="finding-editor">
            {control === "yes_no" ? (
              <SegmentedChoice
                ariaLabel={`Correct ${item.label}`}
                options={[
                  { value: "yes", label: "Yes" },
                  { value: "no", label: "No" },
                  { value: NOT_SURE, label: "Not sure" },
                ]}
                value={value === true ? "yes" : value === false ? "no" : value === NOT_SURE ? NOT_SURE : undefined}
                onChange={(next) => setValue(next === NOT_SURE ? NOT_SURE : next === "yes")}
              />
            ) : control === "choice" ? (
              <SegmentedChoice
                ariaLabel={`Correct ${item.label}`}
                options={[...optionsFor(item.field), { value: NOT_SURE, label: "Not sure" }]}
                value={typeof value === "string" ? value : undefined}
                onChange={(next) => setValue(next)}
              />
            ) : control === "multi" ? (
              <SegmentedChoice
                multiple
                ariaLabel={`Correct ${item.label}`}
                options={optionsFor(item.field)}
                value={Array.isArray(value) ? value.map(String) : []}
                onChange={(next) => setValue(next)}
              />
            ) : (
              <Input
                aria-label={`Correct ${item.label}`}
                className="h-11"
                value={typeof value === "string" && value !== NOT_SURE ? value : ""}
                onChange={(event) => setValue(event.target.value)}
              />
            )}
            <div>
              <Button type="button" size="sm" variant="secondary" className="h-9" onClick={() => setEditing(false)}>
                Done
              </Button>
            </div>
          </div>
        ) : (
          <span className="font-medium break-words">{labelFor(item, value)}</span>
        )}
        <div className="mt-2 sm:hidden" data-testid="evidence-snippet-compact">
          <Evidence item={item} />
        </div>
      </td>
      <td className="py-3 pr-3 text-xs max-sm:hidden">
        <div data-testid="evidence-snippet">
          <Evidence item={item} />
        </div>
      </td>
      <td className="py-3 pr-2 text-sm">
        <ConfidenceDots confidence={item.confidence} />
      </td>
      <td className="py-2 text-right">
        <span className="inline-flex gap-1">
          {corrected ? (
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="size-9"
              aria-label={`Restore ${item.label}`}
              onClick={() => {
                setValue(item.value);
                setEditing(false);
              }}
            >
              <Undo2 className="size-4" aria-hidden="true" />
            </Button>
          ) : null}
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="size-9"
            aria-label={`Correct ${item.label}`}
            aria-pressed={editing}
            onClick={() => setEditing((open) => !open)}
          >
            <Pencil className="size-4" aria-hidden="true" />
          </Button>
        </span>
      </td>
    </tr>
  );
}

export function FindingsReview({ title = "What we found in the repository", findings }: FindingsReviewProps) {
  const accessibility = useGenerativeUIAccessibility();
  return (
    <section {...accessibility} data-testid="FindingsReview" aria-label={title} className="grid gap-3">
      <div className="flex items-baseline justify-between gap-3 flex-wrap">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">{title}</h2>
        <p className="text-xs text-muted-foreground">Confirming the step accepts every row. Correct anything that is wrong.</p>
      </div>
      <div className="min-w-0 overflow-x-auto rounded-[var(--radius)] border bg-card [contain:inline-size]">
        <table className="w-full table-fixed border-collapse text-left sm:min-w-[640px] sm:table-auto" data-testid="findings-table">
          <colgroup>
            <col className="w-[34%] sm:w-auto" />
            <col />
            <col className="max-sm:hidden" />
            <col className="w-13 sm:w-auto" />
            <col className="w-10 sm:w-auto" />
          </colgroup>
          <caption className="sr-only">Repository findings: field, inferred value, evidence and confidence</caption>
          <thead>
            <tr className="border-b text-xs uppercase tracking-wide text-muted-foreground">
              <th scope="col" className="px-3 py-2 font-medium">Field</th>
              <th scope="col" className="px-3 py-2 font-medium">Inferred value</th>
              <th scope="col" className="px-3 py-2 font-medium max-sm:hidden">Evidence</th>
              <th scope="col" className="px-3 py-2 font-medium"><span className="max-sm:sr-only">Confidence</span></th>
              <th scope="col" className="px-3 py-2 font-medium"><span className="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody className="[&>tr]:border-b [&>tr:last-child]:border-0 [&>tr>*]:px-3">
            {findings.map((item) => (
              <Row key={item.field} item={item} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
