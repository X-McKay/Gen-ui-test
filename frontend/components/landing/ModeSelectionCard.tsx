import Link from "next/link";
import { ArrowRight, type LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

interface ModeSelectionCardProps {
  href: string;
  title: string;
  description: string;
  icon: LucideIcon;
  testId: string;
  className?: string;
}

/**
 * The whole card is one link. Hover and focus lift it and nudge the arrow;
 * both states are visible, and reduced motion drops the translate.
 */
export function ModeSelectionCard({
  href,
  title,
  description,
  icon: Icon,
  testId,
  className,
}: ModeSelectionCardProps) {
  return (
    <Link
      href={href}
      data-testid={testId}
      className={cn(
        "group relative flex min-h-[220px] flex-col rounded-lg border border-border bg-card p-6 text-card-foreground shadow-1 outline-none",
        "transition-[transform,box-shadow,border-color] duration-150 ease-[var(--ease-out)]",
        "hover:-translate-y-0.5 hover:border-[color-mix(in_oklch,var(--border),var(--accent)_35%)] hover:shadow-2",
        "focus-visible:-translate-y-0.5 focus-visible:border-accent focus-visible:shadow-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
        "active:translate-y-0 motion-reduce:transform-none motion-reduce:transition-none",
        "md:min-h-[248px] md:p-8",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className="inline-flex size-11 items-center justify-center rounded-lg bg-accent-soft text-accent-soft-foreground"
      >
        <Icon className="size-5" strokeWidth={1.75} />
      </span>

      <span className="mt-10 flex flex-col gap-2 md:mt-12">
        <span className="text-lg font-medium tracking-tight">{title}</span>
        <span className="max-w-[34ch] text-base text-muted-foreground">{description}</span>
      </span>

      <span
        aria-hidden="true"
        className="absolute top-6 right-6 inline-flex size-9 items-center justify-center rounded-full text-muted-foreground transition-[transform,color,background-color] duration-150 ease-[var(--ease-out)] group-hover:translate-x-1 group-hover:bg-accent-soft group-hover:text-accent-soft-foreground group-focus-visible:translate-x-1 group-focus-visible:bg-accent-soft group-focus-visible:text-accent-soft-foreground motion-reduce:transition-none md:top-8 md:right-8"
      >
        <ArrowRight className="size-4" />
      </span>
    </Link>
  );
}
