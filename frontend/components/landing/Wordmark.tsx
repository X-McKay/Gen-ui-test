import Link from "next/link";

import { cn } from "@/lib/utils";

/** A tray with something being placed into it: the intake mark. */
export function IntakeMark({ className }: { className?: string }) {
  return (
    <svg
      className={cn("size-5 shrink-0", className)}
      viewBox="0 0 20 20"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <rect width="20" height="20" rx="6" fill="var(--accent)" />
      <path
        d="M10 4.5v7.25M7.25 9l2.75 2.75L12.75 9"
        stroke="var(--accent-foreground)"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M5 12.5v1.25A1.25 1.25 0 0 0 6.25 15h7.5A1.25 1.25 0 0 0 15 13.75V12.5"
        stroke="var(--accent-foreground)"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <Link
      href="/"
      className={cn(
        "inline-flex h-11 items-center gap-2 rounded-lg px-1 text-base font-semibold tracking-tight text-foreground",
        className,
      )}
      aria-label="Intake, home"
    >
      <IntakeMark />
      <span>Intake</span>
    </Link>
  );
}
