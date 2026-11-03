import { confidenceLevel, formatConfidence } from "@/lib/formatters";
import { cn } from "@/lib/utils";

interface ConfidenceMeterProps {
  confidence: number;
  className?: string;
}

const LEVEL_COLOR = {
  low: "bg-confidence-low",
  medium: "bg-confidence-medium",
  high: "bg-confidence-high",
} as const;

const SEGMENT_HEIGHT = ["h-1.5", "h-[9px]", "h-3"] as const;

/**
 * Three rising segments light up with the level, followed by the percentage as a tabular
 * numeral. Used by assumption chips, findings rows and the provenance popover.
 */
export function ConfidenceMeter({ confidence, className }: ConfidenceMeterProps) {
  const level = confidenceLevel(confidence);
  const lit = level === "high" ? 3 : level === "medium" ? 2 : 1;
  const percent = formatConfidence(confidence);

  return (
    <span
      role="img"
      aria-label={`Confidence ${percent}`}
      title={`Confidence ${percent}`}
      data-testid="confidence-meter"
      data-level={level}
      className={cn("inline-flex items-center gap-1.5 text-xs text-muted-foreground tabular-nums", className)}
    >
      <span aria-hidden="true" className="inline-flex items-end gap-0.5">
        {SEGMENT_HEIGHT.map((height, index) => (
          <span
            key={height}
            className={cn("block w-1 rounded-sm", height, index < lit ? LEVEL_COLOR[level] : "bg-border")}
          />
        ))}
      </span>
      <span aria-hidden="true">{percent}</span>
    </span>
  );
}
