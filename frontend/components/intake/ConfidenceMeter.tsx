import { confidenceLevel, formatConfidence } from "@/lib/formatters";
import { cn } from "@/lib/utils";

interface ConfidenceMeterProps {
  confidence: number;
  /** Hide the percentage and keep only the segments. */
  compact?: boolean;
  className?: string;
}

const LEVEL_COLOR = {
  low: "bg-confidence-low",
  medium: "bg-confidence-medium",
  high: "bg-confidence-high",
} as const;

const LEVEL_TEXT = {
  low: "text-confidence-low",
  medium: "text-confidence-medium",
  high: "text-confidence-high",
} as const;

/** Three segments light up with the level; the percentage is a tabular numeral. */
export function ConfidenceMeter({ confidence, compact = false, className }: ConfidenceMeterProps) {
  const level = confidenceLevel(confidence);
  const lit = level === "high" ? 3 : level === "medium" ? 2 : 1;
  const percent = formatConfidence(confidence);

  return (
    <span
      role="img"
      aria-label={`Confidence ${percent}`}
      data-testid="confidence-meter"
      data-level={level}
      className={cn("inline-flex items-center gap-1.5", className)}
    >
      <span aria-hidden="true" className="inline-flex items-center gap-0.5">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className={cn(
              "h-2 w-1.5 rounded-[2px] transition-colors duration-200",
              i < lit ? LEVEL_COLOR[level] : "bg-foreground/12 dark:bg-foreground/18",
            )}
          />
        ))}
      </span>
      {!compact && (
        <span aria-hidden="true" className={cn("tabular text-sm font-medium", LEVEL_TEXT[level])}>
          {percent}
        </span>
      )}
    </span>
  );
}
