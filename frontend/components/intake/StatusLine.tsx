import { cn } from "@/lib/utils";

interface StatusLineProps {
  text: string | null;
  busy: boolean;
  className?: string;
}

/**
 * One line of streaming status. The dot pulses while busy; reduced motion holds it
 * steady. Announced politely so it never interrupts the person.
 */
export function StatusLine({ text, busy, className }: StatusLineProps) {
  return (
    <p
      role="status"
      aria-live="polite"
      aria-atomic="true"
      data-testid="status-line"
      data-busy={busy ? "true" : "false"}
      className={cn(
        "flex min-h-6 items-center gap-2.5 text-sm text-muted-foreground",
        !text && "invisible",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "relative inline-flex size-2 shrink-0 rounded-full",
          busy ? "status-pulse bg-accent" : "bg-confidence-high",
        )}
      />
      <span className="truncate tabular">{text ?? ""}</span>
    </p>
  );
}
