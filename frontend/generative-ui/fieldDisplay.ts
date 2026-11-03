/**
 * How a record field is edited and displayed inside the generative UI: the control kind,
 * its options and the label for a (possibly edited) value. Shared by assumption chips and
 * repository findings.
 */
import type { ChoiceOption } from "@/generative-ui/components/ChoiceQuestion";
import { NOT_SURE } from "@/generative-ui/interviewForm";
import { type ControlKind, FIELD_CONTROLS, FIELD_OPTIONS } from "@/lib/fieldCatalog";

/** The part of an assumption or finding that labelling needs. */
export interface DisplayedField {
  field: string;
  value: unknown;
  displayValue: string;
}

export function controlFor(field: string): ControlKind {
  return FIELD_CONTROLS[field] ?? "text";
}

export function optionsFor(field: string): ChoiceOption[] {
  return (FIELD_OPTIONS[field] ?? []).map((option) => ({ value: option.value, label: option.label }));
}

/** The label for `value`: the agent's display value while unchanged, otherwise derived. */
export function labelFor(item: DisplayedField, value: unknown): string {
  if (JSON.stringify(value) === JSON.stringify(item.value) && item.displayValue) return item.displayValue;
  if (value === NOT_SURE) return "Not sure";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  const labels = new Map(optionsFor(item.field).map((option) => [option.value, option.label]));
  if (Array.isArray(value))
    return value.length ? value.map((v) => labels.get(String(v)) ?? String(v)).join(", ") : "None";
  if (value === undefined || value === null) return "—";
  return labels.get(String(value)) ?? String(value);
}
