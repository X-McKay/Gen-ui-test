import { cn } from "@/lib/utils";

/** A three-segment confidence meter plus a tabular-numeral percentage. */
export function ConfidenceDots({ confidence, className }: { confidence: number; className?: string }) {
  const percent = Math.round(confidence * 100);
  const level = confidence >= 0.8 ? "high" : confidence >= 0.5 ? "medium" : "low";
  const filled = level === "high" ? 3 : level === "medium" ? 2 : 1;
  const colour =
    level === "high"
      ? "var(--confidence-high, #15803d)"
      : level === "medium"
        ? "var(--confidence-medium, #b45309)"
        : "var(--confidence-low, #b42318)";
  return (
    <span
      className={cn("inline-flex items-center gap-1.5 text-xs text-muted-foreground tabular-nums", className)}
      aria-label={`Confidence ${percent}%`}
      title={`Confidence ${percent}%`}
      data-confidence={level}
    >
      <span className="inline-flex items-end gap-0.5" aria-hidden="true">
        {[0, 1, 2].map((index) => (
          <span
            key={index}
            className="block w-1 rounded-sm"
            style={{
              height: `${6 + index * 3}px`,
              backgroundColor: index < filled ? colour : "var(--border)",
            }}
          />
        ))}
      </span>
      <span>{percent}%</span>
    </span>
  );
}
