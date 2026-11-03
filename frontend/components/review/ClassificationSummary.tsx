"use client";

import * as React from "react";
import { ArrowUpRight, ChevronDown, CircleHelp } from "lucide-react";

import { TierBadge } from "@/components/intake/TierBadge";
import { Badge } from "@/components/ui/badge";
import { getFieldMeta } from "@/components/review/recordFields";
import { formatValue } from "@/lib/formatters";
import type { IntakeRecord, Obligation } from "@/lib/intakeTypes";
import {
  annexLabel,
  fieldLabel,
  frameworkLabel,
  RISK_TIER_LABELS,
  TIER_EXPLANATIONS,
  type TierKey,
} from "@/lib/fieldCatalog";
import { cn } from "@/lib/utils";

interface ClassificationSummaryProps {
  record: IntakeRecord;
  onGoToField: (path: string) => void;
  className?: string;
}

const RISK_CLASS: Record<keyof typeof RISK_TIER_LABELS, string> = {
  low: "text-tier-minimal-foreground",
  medium: "text-tier-limited-foreground",
  high: "text-tier-high-risk-foreground",
  critical: "text-tier-prohibited-foreground",
};

function groupObligations(obligations: readonly Obligation[]): [string, Obligation[]][] {
  const groups = new Map<string, Obligation[]>();
  for (const o of obligations) {
    const key = o.framework;
    groups.set(key, [...(groups.get(key) ?? []), o]);
  }
  // EU AI Act first, then the order they arrived in.
  return [...groups.entries()].sort(([a], [b]) => {
    const isEu = (k: string) => k.toLowerCase().includes("eu_ai_act") || k.toLowerCase().includes("eu ai act");
    return Number(isEu(b)) - Number(isEu(a));
  });
}

function SectionTitle({ children, id }: { children: React.ReactNode; id: string }) {
  return (
    <h3 id={id} className="text-sm font-medium text-muted-foreground">
      {children}
    </h3>
  );
}

function FieldLink({
  path,
  onGoToField,
  children,
  className,
}: {
  path: string;
  onGoToField: (path: string) => void;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={() => onGoToField(path)}
      aria-label={`Go to ${fieldLabel(path)}`}
      className={cn(
        "group/link -mx-2 flex w-[calc(100%+1rem)] min-h-11 items-start gap-2 rounded-md px-2 py-2 text-left outline-none transition-colors hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
        className,
      )}
    >
      <span className="min-w-0 flex-1">{children}</span>
      <ArrowUpRight
        className="mt-1 size-4 shrink-0 text-muted-foreground/60 transition-colors group-hover/link:text-accent group-focus-visible/link:text-accent"
        aria-hidden="true"
      />
    </button>
  );
}

/** The right-hand panel: tier, why, obligations, next steps and open questions. */
export function ClassificationSummary({ record, onGoToField, className }: ClassificationSummaryProps) {
  const assessment = record.assessment;
  const eu = assessment?.eu_ai_act;
  const classification: TierKey = eu?.classification ?? "minimal";
  const annex = eu?.annex_iii_categories ?? [];
  const rationale = eu?.rationale ?? [];
  const riskTier = assessment?.overall_risk_tier;
  const frameworks = assessment?.applicable_frameworks ?? [];
  const obligations = groupObligations(assessment?.obligations ?? []);
  const nextSteps = assessment?.recommended_next_steps ?? [];
  const openQuestions = assessment?.open_questions ?? [];

  return (
    <aside
      data-testid="classification-summary"
      data-classification={classification}
      aria-labelledby="classification-title"
      className={cn(
        "surface-enter flex flex-col gap-6 rounded-lg border border-border bg-card p-6 shadow-1",
        className,
      )}
    >
      <div className="flex flex-col gap-3">
        <h2 id="classification-title" className="text-sm font-medium text-muted-foreground">
          EU AI Act classification
        </h2>
        <TierBadge classification={classification} size="lg" />
        <p className="measure text-base text-foreground/90 text-pretty">{TIER_EXPLANATIONS[classification]}</p>
      </div>

      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
        <dt className="text-muted-foreground">Overall risk</dt>
        <dd className={cn("font-medium", riskTier ? RISK_CLASS[riskTier] : "text-muted-foreground")}>
          {riskTier ? RISK_TIER_LABELS[riskTier] : "—"}
        </dd>
        <dt className="text-muted-foreground">Annex III</dt>
        <dd>
          {annex.length === 0 ? (
            <span className="text-muted-foreground">None</span>
          ) : (
            <ul className="flex flex-col gap-1">
              {annex.map((item) => (
                <li key={item}>{annexLabel(item)}</li>
              ))}
            </ul>
          )}
        </dd>
        <dt className="text-muted-foreground">Frameworks</dt>
        <dd className="flex flex-wrap gap-1.5">
          {frameworks.length === 0 ? (
            <span className="text-muted-foreground">None yet</span>
          ) : (
            frameworks.map((f) => (
              <Badge key={f} variant="outline">
                {frameworkLabel(f)}
              </Badge>
            ))
          )}
        </dd>
      </dl>

      {rationale.length > 0 && (
        <section aria-labelledby="why-title" className="flex flex-col gap-2 border-t border-hairline pt-5">
          <SectionTitle id="why-title">Why</SectionTitle>
          <ul className="flex flex-col">
            {rationale.map((entry, index) => (
              <li key={`${entry.field}-${index}`}>
                <FieldLink path={entry.field} onGoToField={onGoToField}>
                  <span className="block text-sm text-foreground">{entry.text}</span>
                  <span className="mt-0.5 block text-sm text-muted-foreground">
                    {fieldLabel(entry.field)}: {formatValue(entry.field, entry.value)}
                    <span aria-hidden="true"> · </span>
                    {entry.article}
                  </span>
                </FieldLink>
              </li>
            ))}
          </ul>
        </section>
      )}

      {obligations.length > 0 && (
        <section aria-labelledby="obligations-title" className="flex flex-col gap-2 border-t border-hairline pt-5">
          <SectionTitle id="obligations-title">Obligations</SectionTitle>
          <div className="flex flex-col gap-1">
            {obligations.map(([framework, items], index) => (
              <details
                key={framework}
                open={index === 0}
                className="group/details rounded-md"
                data-testid="obligation-group"
                data-framework={framework}
              >
                <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-2 rounded-md px-2 -mx-2 text-sm font-medium outline-none hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring [&::-webkit-details-marker]:hidden">
                  <span>
                    {frameworkLabel(framework)}
                    <span className="tabular ml-2 font-normal text-muted-foreground">{items.length}</span>
                  </span>
                  <ChevronDown
                    className="size-4 text-muted-foreground transition-transform duration-150 group-open/details:rotate-180 motion-reduce:transition-none"
                    aria-hidden="true"
                  />
                </summary>
                <ul className="flex flex-col gap-2 pt-1 pb-2 text-sm">
                  {items.map((o, i) => (
                    <li key={i} className="flex flex-col gap-0.5 border-l-2 border-hairline pl-3">
                      <span>{o.text}</span>
                      {(o.reference || o.role) && (
                        <span className="text-muted-foreground">
                          {[
                            o.reference,
                            o.role
                              ? `${o.role === "both" ? "Provider and deployer" : o.role === "provider" ? "Provider" : "Deployer"}`
                              : null,
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </details>
            ))}
          </div>
        </section>
      )}

      {nextSteps.length > 0 && (
        <section aria-labelledby="next-steps-title" className="flex flex-col gap-2 border-t border-hairline pt-5">
          <SectionTitle id="next-steps-title">Recommended next steps</SectionTitle>
          <ol className="flex list-decimal flex-col gap-1.5 pl-5 text-sm marker:tabular marker:text-muted-foreground">
            {nextSteps.map((step, i) => (
              <li key={i} className="pl-1">
                {step}
              </li>
            ))}
          </ol>
        </section>
      )}

      <section aria-labelledby="open-questions-title" className="flex flex-col gap-2 border-t border-hairline pt-5">
        <SectionTitle id="open-questions-title">Open questions</SectionTitle>
        {openQuestions.length === 0 ? (
          <p className="text-sm text-muted-foreground">None. Every required answer is in.</p>
        ) : (
          <ul className="flex flex-col" data-testid="open-questions">
            {openQuestions.map((path) => {
              const meta = getFieldMeta(record, path);
              return (
                <li key={path}>
                  <FieldLink path={path} onGoToField={onGoToField}>
                    <span className="flex items-center gap-2 text-sm">
                      <CircleHelp className="size-4 shrink-0 text-tier-high-risk-foreground" aria-hidden="true" />
                      <span>{fieldLabel(path)}</span>
                      <span className="text-muted-foreground">{formatValue(path, meta.value)}</span>
                    </span>
                  </FieldLink>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </aside>
  );
}
