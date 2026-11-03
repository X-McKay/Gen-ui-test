"use client";

import * as React from "react";

import { getFieldMeta } from "@/components/review/recordFields";
import { ReviewFieldRow } from "@/components/review/ReviewFieldRow";
import type { IntakeRecord } from "@/lib/intakeTypes";
import { SECTION_FIELDS, SECTION_LABELS, SECTION_ORDER } from "@/lib/fieldCatalog";
import { cn } from "@/lib/utils";

interface IntakeReviewPanelProps {
  record: IntakeRecord;
  readOnly: boolean;
  highlightedField: string | null;
  onSave: (path: string, value: unknown) => Promise<void>;
  className?: string;
}

/** The record, grouped by section, as editable definition rows. */
export function IntakeReviewPanel({ record, readOnly, highlightedField, onSave, className }: IntakeReviewPanelProps) {
  return (
    <div data-testid="intake-review-panel" className={cn("flex flex-col gap-6", className)}>
      {SECTION_ORDER.map((section) => (
        <section
          key={section}
          aria-labelledby={`review-section-${section}`}
          data-section={section}
          className="surface-enter rounded-lg border border-border bg-card px-6 py-5 shadow-1"
        >
          <h2 id={`review-section-${section}`} className="mb-2 text-lg font-medium tracking-tight">
            {SECTION_LABELS[section]}
          </h2>
          <dl className="divide-y divide-hairline">
            {SECTION_FIELDS[section].map((path) => (
              <ReviewFieldRow
                key={path}
                path={path}
                meta={getFieldMeta(record, path)}
                readOnly={readOnly}
                highlighted={highlightedField === path}
                onSave={onSave}
              />
            ))}
          </dl>
        </section>
      ))}
    </div>
  );
}
