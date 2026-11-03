import { OctagonAlert } from "lucide-react";

/** Shown at the top when the classification is prohibited; the page is read-only. */
export function EscalationBanner() {
  return (
    <div
      role="alert"
      data-testid="escalation-banner"
      className="surface-enter flex gap-3 rounded-lg border border-tier-prohibited-foreground/30 bg-tier-prohibited px-5 py-4 text-tier-prohibited-foreground"
    >
      <OctagonAlert className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
      <div className="flex flex-col gap-1">
        <p className="text-base font-medium">This project describes a prohibited practice</p>
        <p className="measure text-sm text-pretty">
          Contact the AI governance team before any further work. Answers are locked; you can still download the
          record.
        </p>
      </div>
    </div>
  );
}
