"use client";

import * as React from "react";
import { Check, FileCode2, Sparkles, UserRound } from "lucide-react";

import { ConfidenceMeter } from "@/components/intake/ConfidenceMeter";
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover";
import { formatSource } from "@/lib/formatters";
import { cn } from "@/lib/utils";

export interface ProvenanceInfo {
  label: string;
  displayValue: string;
  confidence: number;
  source: string;
  confirmed: boolean;
}

interface FieldProvenancePopoverProps extends ProvenanceInfo {
  /** The element that opens the popover; rendered via Base UI's `render`. */
  children: React.ReactElement;
  align?: "start" | "center" | "end";
  side?: "top" | "bottom";
  className?: string;
}

function SourceIcon({ source, confirmed }: { source: string; confirmed: boolean }) {
  const cls = "size-4 text-muted-foreground";
  if (confirmed || source === "user") return <UserRound className={cls} aria-hidden="true" />;
  if (source.startsWith("repo:")) return <FileCode2 className={cls} aria-hidden="true" />;
  return <Sparkles className={cls} aria-hidden="true" />;
}

/**
 * Where a value came from, one click away. Reused by assumption chips, repository
 * findings and the review page.
 */
export function FieldProvenancePopover({
  label,
  displayValue,
  confidence,
  source,
  confirmed,
  children,
  align = "start",
  side = "bottom",
  className,
}: FieldProvenancePopoverProps) {
  const sourceText = formatSource(source, confirmed);
  const repoPath = source.startsWith("repo:") ? source.slice("repo:".length) : null;

  return (
    <Popover>
      <PopoverTrigger render={children} />
      <PopoverContent
        align={align}
        side={side}
        className={cn("w-80 max-w-[calc(100vw-2rem)] gap-3", className)}
        data-testid="field-provenance"
      >
        <PopoverHeader>
          <PopoverTitle className="text-base">{label}</PopoverTitle>
          <PopoverDescription className="text-foreground">{displayValue}</PopoverDescription>
        </PopoverHeader>
        <dl className="grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-2 text-sm">
          <dt className="sr-only">Source</dt>
          <dd className="col-span-2 flex items-start gap-2">
            <SourceIcon source={source} confirmed={confirmed} />
            {repoPath ? (
              <span className="min-w-0">
                <span className="text-muted-foreground">Repository </span>
                <code className="rounded-sm bg-muted px-1 py-0.5 font-mono text-[0.8125rem] break-all">{repoPath}</code>
              </span>
            ) : (
              <span>{sourceText}</span>
            )}
          </dd>
          <dt className="text-muted-foreground">Confidence</dt>
          <dd>
            <ConfidenceMeter confidence={confidence} />
          </dd>
          <dt className="text-muted-foreground">Confirmed</dt>
          <dd className="flex items-center gap-1.5">
            {confirmed ? (
              <>
                <Check className="size-4 text-accent" aria-hidden="true" />
                Yes
              </>
            ) : (
              "No"
            )}
          </dd>
        </dl>
      </PopoverContent>
    </Popover>
  );
}
