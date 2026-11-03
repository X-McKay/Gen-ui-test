"use client";

import * as React from "react";
import { Check, Pencil } from "lucide-react";

import { ConfidenceMeter } from "@/components/intake/ConfidenceMeter";
import { FieldProvenancePopover } from "@/components/review/FieldProvenancePopover";
import { cn } from "@/lib/utils";

export interface AssumptionChipProps {
  field: string;
  label: string;
  displayValue: string;
  confidence: number;
  source: string;
  mustConfirm?: boolean;
  state: "pending" | "confirmed" | "editing";
  onConfirm?: () => void;
  onEdit?: () => void;
  className?: string;
}

/**
 * One inferred fact as a pill: label and value, a confidence meter, then confirm and
 * edit. The pill body opens provenance. Confirming tints the chip with the accent and
 * pops the check in 150ms; reduced motion skips the pop.
 */
export function AssumptionChip({
  field,
  label,
  displayValue,
  confidence,
  source,
  mustConfirm = false,
  state,
  onConfirm,
  onEdit,
  className,
}: AssumptionChipProps) {
  const confirmed = state === "confirmed";
  const editing = state === "editing";

  return (
    <div
      data-testid="assumption-chip"
      data-field={field}
      data-state={state}
      data-must-confirm={mustConfirm ? "true" : undefined}
      className={cn(
        "group/chip inline-flex max-w-full items-stretch rounded-lg border bg-card text-sm shadow-1 transition-[border-color,background-color,box-shadow] duration-150",
        confirmed && "border-accent/60 bg-accent-soft/60 dark:bg-accent-soft/40",
        editing && "border-accent border-dashed",
        !confirmed && !editing && "border-border",
        className,
      )}
    >
      <FieldProvenancePopover
        label={label}
        displayValue={displayValue}
        confidence={confidence}
        source={source}
        confirmed={confirmed}
      >
        <button
          type="button"
          className="flex min-h-11 min-w-0 flex-1 items-center gap-2.5 rounded-l-lg py-2 pr-2 pl-3 text-left outline-none hover:bg-muted/60 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
          aria-label={`${label}: ${displayValue}. Show provenance`}
        >
          <span className="min-w-0 truncate">
            <span className="text-muted-foreground">{label}</span>
            <span className="text-muted-foreground/70"> · </span>
            <span className="font-medium text-foreground">{displayValue}</span>
          </span>
          <ConfidenceMeter confidence={confidence} compact className="shrink-0" />
          {mustConfirm && !confirmed && (
            <span className="sr-only">Needs your confirmation</span>
          )}
        </button>
      </FieldProvenancePopover>

      <span aria-hidden="true" className="my-2 w-px bg-border" />

      <button
        type="button"
        onClick={onConfirm}
        aria-label={`Confirm ${label}`}
        aria-pressed={confirmed}
        disabled={editing}
        className={cn(
          "inline-flex size-11 shrink-0 items-center justify-center outline-none transition-colors duration-150 hover:bg-muted/60 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring disabled:pointer-events-none disabled:opacity-40",
          confirmed ? "text-accent" : "text-muted-foreground",
        )}
      >
        <span
          key={confirmed ? "on" : "off"}
          className={cn(
            "inline-flex size-6 items-center justify-center rounded-full",
            confirmed && "check-pop bg-accent text-accent-foreground",
          )}
        >
          <Check className="size-4" strokeWidth={confirmed ? 2.5 : 2} aria-hidden="true" />
        </span>
      </button>
      <button
        type="button"
        onClick={onEdit}
        aria-label={`Edit ${label}`}
        aria-pressed={editing}
        className={cn(
          "inline-flex size-11 shrink-0 items-center justify-center rounded-r-lg outline-none transition-colors duration-150 hover:bg-muted/60 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring",
          editing ? "text-accent" : "text-muted-foreground",
        )}
      >
        <Pencil className="size-4" aria-hidden="true" />
      </button>
    </div>
  );
}
