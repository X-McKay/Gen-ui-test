"use client";

import * as React from "react";
import { Check, Info, Loader2, Pencil, X } from "lucide-react";

import { FieldProvenancePopover } from "@/components/review/FieldProvenancePopover";
import { fieldRowId, type FieldMetaLike } from "@/components/review/recordFields";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { formatValue, UNKNOWN_VALUE } from "@/lib/formatters";
import { FIELD_SPECS_BY_PATH, type FieldSpec } from "@/lib/labels";
import { cn } from "@/lib/utils";

interface ReviewFieldRowProps {
  path: string;
  meta: FieldMetaLike;
  readOnly: boolean;
  highlighted: boolean;
  onSave: (path: string, value: unknown) => Promise<void>;
}

const UNKNOWN = "unknown";

function toDraft(spec: FieldSpec, value: unknown): string[] | string {
  if (spec.control === "text") return typeof value === "string" && value !== UNKNOWN ? value : "";
  if (value === UNKNOWN) return [UNKNOWN];
  if (spec.control === "yes_no") return typeof value === "boolean" ? [String(value)] : [];
  if (spec.control === "multi") return Array.isArray(value) ? value.map(String) : [];
  return typeof value === "string" ? [value] : [];
}

function fromDraft(spec: FieldSpec, draft: string[] | string): unknown {
  if (typeof draft === "string") return draft.trim() === "" ? null : draft.trim();
  if (draft.includes(UNKNOWN)) return UNKNOWN;
  if (spec.control === "yes_no") return draft[0] === "true" ? true : draft[0] === "false" ? false : null;
  if (spec.control === "multi") return draft;
  return draft[0] ?? null;
}

/**
 * One definition row: label, value, provenance, edit. Editing swaps the value for the
 * control that matches the question (yes/no, single choice, multi-select, text).
 */
export function ReviewFieldRow({ path, meta, readOnly, highlighted, onSave }: ReviewFieldRowProps) {
  const spec = FIELD_SPECS_BY_PATH[path];
  const label = spec?.label ?? path;
  const display = formatValue(path, meta.value);
  const unset = meta.value === null || meta.value === undefined;
  const unknown = meta.value === UNKNOWN;

  const [editing, setEditing] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [draft, setDraft] = React.useState<string[] | string>(() => (spec ? toDraft(spec, meta.value) : ""));
  const editButtonRef = React.useRef<HTMLButtonElement>(null);
  const controlId = React.useId();

  const startEditing = () => {
    if (!spec) return;
    setDraft(toDraft(spec, meta.value));
    setEditing(true);
  };

  const stopEditing = () => {
    setEditing(false);
    requestAnimationFrame(() => editButtonRef.current?.focus());
  };

  const save = async () => {
    if (!spec) return;
    setSaving(true);
    try {
      await onSave(path, fromDraft(spec, draft));
      stopEditing();
    } finally {
      setSaving(false);
    }
  };

  const multiChange = (next: string[]) => {
    const prev = Array.isArray(draft) ? draft : [];
    const added = next.find((v) => !prev.includes(v));
    if (added === UNKNOWN) setDraft([UNKNOWN]);
    else setDraft(next.filter((v) => v !== UNKNOWN));
  };

  const dirty = spec ? JSON.stringify(fromDraft(spec, draft)) !== JSON.stringify(meta.value ?? null) : false;

  return (
    <div
      id={fieldRowId(path)}
      data-testid="review-field"
      data-field={path}
      data-editing={editing || undefined}
      data-unknown={unknown || undefined}
      tabIndex={-1}
      className={cn(
        "grid scroll-mt-28 grid-cols-1 gap-x-6 gap-y-0 rounded-md px-3 py-1.5 outline-none sm:grid-cols-[minmax(10rem,13rem)_1fr] sm:gap-y-1 sm:py-2.5",
        "-mx-3 transition-colors duration-150",
        highlighted && "row-flash",
      )}
    >
      <dt className="-mb-1.5 flex min-h-11 items-center gap-1 text-sm text-muted-foreground sm:mb-0">
        <span id={`${controlId}-label`}>{label}</span>
        <FieldProvenancePopover
          label={label}
          displayValue={display}
          confidence={meta.confidence}
          source={meta.source}
          confirmed={meta.confirmed}
        >
          <button
            type="button"
            aria-label={`Provenance for ${label}`}
            className="inline-flex size-11 shrink-0 items-center justify-center rounded-md text-muted-foreground/70 outline-none transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          >
            <Info className="size-4" aria-hidden="true" />
          </button>
        </FieldProvenancePopover>
      </dt>

      <dd className="min-w-0">
        {!editing ? (
          <div className="flex min-h-11 items-start justify-between gap-3">
            <span
              className={cn(
                "flex min-w-0 flex-1 items-center py-2 text-base sm:min-h-11",
                unset && "text-muted-foreground/70",
                unknown && "text-tier-high-risk-foreground",
              )}
            >
              <span className="[overflow-wrap:anywhere]">
                {display}
                {meta.confirmed && !unset && (
                  <Check
                    className="ml-1.5 inline-block size-3.5 align-[-2px] text-accent"
                    aria-label="Confirmed"
                    role="img"
                  />
                )}
              </span>
            </span>
            {!readOnly && spec && (
              <Button
                ref={editButtonRef}
                type="button"
                variant="ghost"
                size="icon"
                aria-label={`Edit ${label}`}
                onClick={startEditing}
                className="shrink-0 text-muted-foreground hover:text-foreground"
              >
                <Pencil aria-hidden="true" />
              </Button>
            )}
          </div>
        ) : spec ? (
          <form
            className="surface-enter flex flex-col gap-3 py-1"
            onSubmit={(event) => {
              event.preventDefault();
              void save();
            }}
            aria-labelledby={`${controlId}-label`}
          >
            <p className="measure text-sm text-muted-foreground">{spec.prompt}</p>

            {spec.control === "text" ? (
              path === "project.description" || path === "use_case.purpose" ? (
                <Textarea
                  id={controlId}
                  value={typeof draft === "string" ? draft : ""}
                  onChange={(event) => setDraft(event.target.value)}
                  placeholder={spec.placeholder ?? undefined}
                  aria-label={label}
                  autoFocus
                  rows={3}
                />
              ) : (
                <Input
                  id={controlId}
                  value={typeof draft === "string" ? draft : ""}
                  onChange={(event) => setDraft(event.target.value)}
                  placeholder={spec.placeholder ?? undefined}
                  aria-label={label}
                  autoFocus
                />
              )
            ) : spec.control === "yes_no" ? (
              <ToggleGroup
                aria-label={label}
                value={Array.isArray(draft) ? draft : []}
                onValueChange={(next) => setDraft(next.slice(-1))}
                variant="outline"
                className="flex-wrap"
              >
                <ToggleGroupItem value="true">Yes</ToggleGroupItem>
                <ToggleGroupItem value="false">No</ToggleGroupItem>
                <ToggleGroupItem value={UNKNOWN}>{UNKNOWN_VALUE}</ToggleGroupItem>
              </ToggleGroup>
            ) : spec.control === "choice" ? (
              <ToggleGroup
                aria-label={label}
                value={Array.isArray(draft) ? draft : []}
                onValueChange={(next) => setDraft(next.slice(-1))}
                variant="outline"
                className="flex-wrap"
              >
                {spec.options.map((option) => (
                  <ToggleGroupItem key={option.value} value={option.value}>
                    {option.label}
                  </ToggleGroupItem>
                ))}
                <ToggleGroupItem value={UNKNOWN}>{UNKNOWN_VALUE}</ToggleGroupItem>
              </ToggleGroup>
            ) : (
              <ToggleGroup
                aria-label={label}
                multiple
                value={Array.isArray(draft) ? draft : []}
                onValueChange={multiChange}
                variant="outline"
                className="flex-wrap"
              >
                {spec.options.map((option) => (
                  <ToggleGroupItem key={option.value} value={option.value} className="rounded-full">
                    {option.label}
                  </ToggleGroupItem>
                ))}
                <ToggleGroupItem value={UNKNOWN} className="rounded-full">
                  {UNKNOWN_VALUE}
                </ToggleGroupItem>
              </ToggleGroup>
            )}

            <div className="flex items-center gap-2">
              <Button type="submit" size="sm" disabled={saving || !dirty} aria-label={`Save ${label}`}>
                {saving ? (
                  <Loader2 className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
                ) : (
                  <Check aria-hidden="true" />
                )}
                Save
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={stopEditing}
                disabled={saving}
                aria-label={`Cancel editing ${label}`}
              >
                <X aria-hidden="true" />
                Cancel
              </Button>
            </div>
          </form>
        ) : null}
      </dd>
    </div>
  );
}
