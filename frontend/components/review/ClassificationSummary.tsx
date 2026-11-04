"use client";

import * as React from "react";
import { ArrowUpRight, ChevronDown, CircleHelp } from "lucide-react";

import { TierBadge } from "@/components/intake/TierBadge";
import { Badge } from "@/components/ui/badge";
import { getFieldMeta } from "@/components/review/recordFields";
import { formatValue } from "@/lib/formatters";
import type { ControlEffect, IntakeRecord, Obligation, RiskDriver, RiskLens, RiskProfile } from "@/lib/intakeTypes";
import {
  annexLabel,
  CONTROL_STATUS_LABELS,
  CONTROL_STATUS_ORDER,
  type ControlStatus,
  fieldLabel,
  frameworkLabel,
  optionLabel,
  RISK_PROFILE_EXPLANATIONS,
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
      className={cn(
        "group/link -mx-2 flex w-[calc(100%+1rem)] min-h-11 items-start gap-2 rounded-md px-2 py-2 text-left outline-none transition-colors hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
        className,
      )}
    >
      {/* Named from content so the visible text is part of the accessible name (WCAG 2.5.3). */}
      <span className="sr-only">Go to {fieldLabel(path)}: </span>
      <span className="min-w-0 flex-1">{children}</span>
      <ArrowUpRight
        className="mt-1 size-4 shrink-0 text-muted-foreground/60 transition-colors group-hover/link:text-accent group-focus-visible/link:text-accent"
        aria-hidden="true"
      />
    </button>
  );
}

function groupControls(controls: readonly ControlEffect[]): [ControlStatus, ControlEffect[]][] {
  return CONTROL_STATUS_ORDER.map((status) => [status, controls.filter((c) => c.status === status)] as const)
    .filter(([, items]) => items.length > 0)
    .map(([status, items]) => [status, items]);
}

/** A declared control is an option of `controls.in_place`; anything else is an answer's field path. */
function controlLabel(effect: ControlEffect): string {
  const asOption = optionLabel("controls.in_place", effect.control);
  return asOption === effect.control ? fieldLabel(effect.control) : asOption;
}

function sentenceCase(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function Points({ value, sign }: { value: number; sign: "+" | "−" }) {
  return (
    <span className="tabular shrink-0 text-sm text-muted-foreground">
      {sign}
      {Math.abs(value)}
      <span className="sr-only"> points</span>
    </span>
  );
}

function RiskTierCard({ kind, profile }: { kind: "inherent" | "residual"; profile: RiskProfile }) {
  return (
    <div
      data-testid={`risk-${kind}`}
      data-tier={profile.tier}
      className="flex min-w-0 flex-col gap-1 rounded-md border border-hairline bg-background/40 px-3 py-2.5"
    >
      <span className="text-sm text-muted-foreground">{kind === "inherent" ? "Inherent" : "Residual"}</span>
      <span className="flex flex-wrap items-baseline gap-x-2">
        <span className={cn("text-lg font-medium", RISK_CLASS[profile.tier])}>{RISK_TIER_LABELS[profile.tier]}</span>
        <span className="tabular text-sm text-muted-foreground">Score {profile.score}</span>
      </span>
      <p className="text-sm text-muted-foreground text-pretty">{RISK_PROFILE_EXPLANATIONS[kind]}</p>
      {profile.floor_reason && (
        <p className="mt-1 text-sm text-foreground/90 text-pretty" data-testid="risk-floor">
          {profile.floor ? `Cannot go below ${RISK_TIER_LABELS[profile.floor].toLowerCase()}: ` : ""}
          {profile.floor_reason}
        </p>
      )}
    </div>
  );
}

function LensTier({ kind, profile }: { kind: "inherent" | "residual"; profile: RiskProfile }) {
  return (
    <span className="flex items-baseline gap-1.5 text-sm">
      {/* Visible below sm where there is no column header; the header carries the name on wider screens. */}
      <span className="text-muted-foreground sm:sr-only">{kind === "inherent" ? "Inherent" : "Residual"}</span>
      <span className={cn("font-medium", RISK_CLASS[profile.tier])}>{RISK_TIER_LABELS[profile.tier]}</span>
      <span className="tabular text-muted-foreground">
        {profile.score}
        <span className="sr-only"> points</span>
      </span>
    </span>
  );
}

const LENS_COLUMNS = "sm:grid-cols-[minmax(0,1fr)_7.5rem_7.5rem] sm:gap-x-3";

/** One row per enterprise risk lens, in the order the backend fixed; stacks below sm. */
function RiskLensList({ lenses }: { lenses: readonly RiskLens[] }) {
  return (
    <div className="flex flex-col gap-1 pt-1" data-testid="risk-lenses">
      <h4 id="risk-lenses-title" className="text-sm font-medium">
        By lens
      </h4>
      <div className={cn("hidden text-sm text-muted-foreground sm:grid", LENS_COLUMNS)} aria-hidden="true">
        <span />
        <span>Inherent</span>
        <span>Residual</span>
      </div>
      <ul className="flex flex-col divide-y divide-hairline" aria-labelledby="risk-lenses-title">
        {lenses.map((lens) => (
          <li
            key={lens.lens}
            data-lens={lens.lens}
            data-inherent={lens.inherent.tier}
            data-residual={lens.residual.tier}
            className={cn("flex min-w-0 flex-col gap-0.5 py-1.5 sm:grid sm:items-baseline", LENS_COLUMNS)}
          >
            <span className="text-sm text-foreground">{lens.label}</span>
            <span className="flex flex-wrap gap-x-4 gap-y-0.5 sm:contents">
              <LensTier kind="inherent" profile={lens.inherent} />
              <LensTier kind="residual" profile={lens.residual} />
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function RiskProfileSection({
  inherent,
  residual,
  lenses,
  onGoToField,
}: {
  inherent: RiskProfile;
  residual: RiskProfile;
  lenses: readonly RiskLens[];
  onGoToField: (path: string) => void;
}) {
  const drivers: readonly RiskDriver[] = inherent.drivers.length > 0 ? inherent.drivers : residual.drivers;
  const controls = groupControls(residual.controls.length > 0 ? residual.controls : inherent.controls);

  return (
    <section
      data-testid="risk-profile"
      data-inherent={inherent.tier}
      data-residual={residual.tier}
      aria-labelledby="risk-profile-title"
      className="flex flex-col gap-3 border-t border-hairline pt-5"
    >
      <SectionTitle id="risk-profile-title">Inherent and residual risk</SectionTitle>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <RiskTierCard kind="inherent" profile={inherent} />
        <RiskTierCard kind="residual" profile={residual} />
      </div>

      {lenses.length > 0 && <RiskLensList lenses={lenses} />}

      {drivers.length > 0 && (
        <div className="flex flex-col gap-1 pt-1">
          <h4 id="risk-drivers-title" className="text-sm font-medium">
            Drivers
          </h4>
          <ul className="flex flex-col" aria-labelledby="risk-drivers-title" data-testid="risk-drivers">
            {drivers.map((driver, index) => (
              <li key={`${driver.field}-${index}`}>
                <FieldLink path={driver.field} onGoToField={onGoToField}>
                  <span className="flex items-baseline justify-between gap-3">
                    <span className="min-w-0 text-sm text-foreground">{driver.text}</span>
                    <Points value={driver.points} sign="+" />
                  </span>
                  <span className="mt-0.5 block text-sm text-muted-foreground">
                    {fieldLabel(driver.field)}: {formatValue(driver.field, driver.value)}
                    {driver.category && (
                      <>
                        <span aria-hidden="true"> · </span>
                        {sentenceCase(driver.category)}
                      </>
                    )}
                  </span>
                </FieldLink>
              </li>
            ))}
          </ul>
        </div>
      )}

      {controls.length > 0 && (
        <div className="flex flex-col gap-2 pt-1">
          <h4 id="risk-controls-title" className="text-sm font-medium">
            Controls
          </h4>
          {controls.map(([status, items]) => (
            <div key={status} className="flex flex-col gap-0.5" data-testid="risk-control-group" data-status={status}>
              <p className="text-sm text-muted-foreground">
                {CONTROL_STATUS_LABELS[status]}
                <span className="tabular ml-2">{items.length}</span>
              </p>
              <ul className="flex flex-col">
                {items.map((effect, index) => (
                  <li key={`${effect.control}-${index}`}>
                    <FieldLink path={effect.field} onGoToField={onGoToField}>
                      <span className="flex items-baseline justify-between gap-3">
                        <span className="min-w-0 text-sm text-foreground">{controlLabel(effect)}</span>
                        {status === "applied" && <Points value={effect.points} sign="−" />}
                      </span>
                      <span className="mt-0.5 block text-sm text-muted-foreground">{effect.text}</span>
                    </FieldLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/** The right-hand panel: tier, risk profiles, why, obligations, next steps and open questions. */
export function ClassificationSummary({ record, onGoToField, className }: ClassificationSummaryProps) {
  const assessment = record.assessment;
  const eu = assessment?.eu_ai_act;
  const classification: TierKey = eu?.classification ?? "minimal";
  const annex = eu?.annex_iii_categories ?? [];
  const rationale = eu?.rationale ?? [];
  const riskTier = assessment?.overall_risk_tier;
  const inherent: RiskProfile | undefined = assessment?.inherent_risk;
  const residual: RiskProfile | undefined = assessment?.residual_risk;
  // Older records predate the lenses; the list renders nothing for them.
  const lenses: readonly RiskLens[] = assessment?.risk_lenses ?? [];
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

      {inherent && residual && (
        <RiskProfileSection inherent={inherent} residual={residual} lenses={lenses} onGoToField={onGoToField} />
      )}

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
