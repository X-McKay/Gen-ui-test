"use client";

import Link from "next/link";
import { Home, RotateCw, SearchX, Unplug } from "lucide-react";

import { Button } from "@/components/ui/button";

interface ReviewErrorStateProps {
  kind: "not-found" | "unavailable";
  intakeId: string;
  detail?: string;
  onRetry: () => void;
  retrying?: boolean;
}

/** Explains what went wrong and offers the two useful moves: try again or go home. */
export function ReviewErrorState({ kind, intakeId, detail, onRetry, retrying = false }: ReviewErrorStateProps) {
  const notFound = kind === "not-found";
  const Icon = notFound ? SearchX : Unplug;

  return (
    <div
      role="region"
      aria-labelledby="review-error-title"
      data-testid="review-error"
      data-kind={kind}
      className="surface-enter mx-auto flex w-full max-w-[520px] flex-col items-start gap-5 rounded-lg border border-border bg-card p-8 shadow-1"
    >
      <span className="inline-flex size-11 items-center justify-center rounded-lg bg-muted text-muted-foreground">
        <Icon className="size-5" aria-hidden="true" />
      </span>
      <div className="flex flex-col gap-2">
        <h1 id="review-error-title" className="text-lg font-medium tracking-tight">
          {notFound ? "No intake with this id" : "The intake could not be loaded"}
        </h1>
        <p className="measure text-base text-muted-foreground text-pretty">
          {notFound ? (
            <>
              Nothing is stored under{" "}
              <code className="rounded-sm bg-muted px-1.5 py-0.5 font-mono text-[0.8125rem] text-foreground">
                {intakeId}
              </code>
              . The link may be out of date, or the intake was started on another server.
            </>
          ) : (
            <>The server did not answer. Check that the backend is running, then try again.</>
          )}
        </p>
        {detail && !notFound && <p className="font-mono text-sm text-muted-foreground">{detail}</p>}
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="button" onClick={onRetry} disabled={retrying} data-testid="review-retry">
          <RotateCw className={retrying ? "animate-spin motion-reduce:animate-none" : undefined} aria-hidden="true" />
          Try again
        </Button>
        <Button variant="outline" nativeButton={false} render={<Link href="/" />} data-testid="review-home">
          <Home aria-hidden="true" />
          Start a new intake
        </Button>
      </div>
    </div>
  );
}
