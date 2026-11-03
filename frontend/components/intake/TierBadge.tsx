import { TIER_LABELS, type TierKey } from "@/lib/labels";
import { cn } from "@/lib/utils";

interface TierBadgeProps {
  classification: TierKey;
  size?: "sm" | "lg";
  className?: string;
}

const TIER_CLASS: Record<TierKey, string> = {
  prohibited: "bg-tier-prohibited text-tier-prohibited-foreground",
  high_risk: "bg-tier-high-risk text-tier-high-risk-foreground",
  limited_transparency: "bg-tier-limited text-tier-limited-foreground",
  minimal: "bg-tier-minimal text-tier-minimal-foreground",
};

/** EU AI Act tier with its semantic colour and a human label. */
export function TierBadge({ classification, size = "sm", className }: TierBadgeProps) {
  return (
    <span
      data-testid="tier-badge"
      data-tier={classification}
      className={cn(
        "inline-flex w-fit items-center gap-2 rounded-full font-medium whitespace-nowrap",
        size === "lg" ? "h-10 px-4 text-base" : "h-6 px-2.5 text-sm",
        TIER_CLASS[classification],
        className,
      )}
    >
      <span aria-hidden="true" className={cn("rounded-full bg-current", size === "lg" ? "size-2.5" : "size-2")} />
      {TIER_LABELS[classification]}
    </span>
  );
}
