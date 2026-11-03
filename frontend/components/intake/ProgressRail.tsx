import { Check } from "lucide-react";

import type { SectionProgressDto } from "@/lib/apiClient";
import { SECTION_LABELS, SECTION_ORDER, type SectionKey } from "@/lib/fieldCatalog";
import { cn } from "@/lib/utils";

interface ProgressRailProps {
  sections: SectionProgressDto[];
  className?: string;
}

type RailState = "done" | "active" | "pending";

function stateOf(section: SectionProgressDto | undefined): RailState {
  if (!section) return "pending";
  if (section.active) return "active";
  if (section.total > 0 && section.done >= section.total) return "done";
  return "pending";
}

const STATE_COPY: Record<RailState, string> = {
  done: "complete",
  active: "in progress",
  pending: "not started",
};

/**
 * Four sections as a horizontal rail. No counts are shown; the fraction lives in the
 * aria-label so screen readers get the detail without the layout carrying numbers.
 */
export function ProgressRail({ sections, className }: ProgressRailProps) {
  const bySection = new Map(sections.map((s) => [s.section, s]));

  return (
    <nav aria-label="Interview progress" data-testid="progress-rail" className={cn("w-full", className)}>
      <ol className="flex flex-wrap items-stretch gap-x-2 gap-y-3 sm:flex-nowrap">
        {SECTION_ORDER.map((key: SectionKey, index) => {
          const section = bySection.get(key);
          const state = stateOf(section);
          const label = section?.label ?? SECTION_LABELS[key];
          const fraction = section ? `${section.done} of ${section.total} answered` : "no questions yet";
          return (
            <li
              key={key}
              data-state={state}
              data-section={key}
              aria-current={state === "active" ? "step" : undefined}
              aria-label={`${label}: ${STATE_COPY[state]}, ${fraction}`}
              className="group/step flex min-w-[calc(50%-0.25rem)] flex-1 flex-col gap-2 sm:min-w-0"
            >
              <span
                aria-hidden="true"
                className={cn(
                  "h-1 w-full rounded-full transition-colors duration-200",
                  state === "done" && "bg-accent",
                  state === "active" && "bg-accent/45",
                  state === "pending" && "bg-border",
                )}
              />
              <span className="flex items-center gap-1.5 text-sm">
                <span
                  aria-hidden="true"
                  className={cn(
                    "inline-flex size-4 shrink-0 items-center justify-center rounded-full border text-[10px] font-medium transition-colors duration-200",
                    state === "done" && "border-accent bg-accent text-accent-foreground",
                    state === "active" && "border-accent text-accent",
                    state === "pending" && "border-border text-muted-foreground",
                  )}
                >
                  {state === "done" ? <Check className="size-2.5" strokeWidth={3} /> : index + 1}
                </span>
                <span
                  className={cn(
                    "truncate",
                    state === "active" ? "font-medium text-foreground" : "text-muted-foreground",
                    state === "done" && "text-foreground",
                  )}
                >
                  {label}
                </span>
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
