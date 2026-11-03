import type { IntakeRecord } from "@/lib/intakeTypes";
import { sectionOf } from "@/lib/fieldCatalog";

/** The shape every record leaf shares. */
export interface FieldMetaLike {
  value: unknown;
  confidence: number;
  source: string;
  confirmed: boolean;
}

type Leaf = { value?: unknown; confidence?: number; source?: string; confirmed?: boolean };

/** Read `section.field` out of a record, normalising a missing leaf to an unset field. */
export function getFieldMeta(record: IntakeRecord, path: string): FieldMetaLike {
  const section = sectionOf(path);
  const key = path.split(".")[1];
  if (!section || !key) return { value: null, confidence: 0, source: "", confirmed: false };
  const group = (record as unknown as Record<string, unknown>)[section] as Record<string, Leaf | undefined> | undefined;
  const leaf = group?.[key];
  return {
    value: leaf?.value ?? null,
    confidence: typeof leaf?.confidence === "number" ? leaf.confidence : 0,
    source: leaf?.source ?? "",
    confirmed: Boolean(leaf?.confirmed),
  };
}

export function isUnset(meta: FieldMetaLike): boolean {
  return meta.value === null || meta.value === undefined;
}

export function isUnknown(meta: FieldMetaLike): boolean {
  return meta.value === "unknown";
}

/** Return a new record with `path` set as a confirmed user value (optimistic update). */
export function setFieldValue(record: IntakeRecord, path: string, value: unknown): IntakeRecord {
  const section = sectionOf(path);
  const key = path.split(".")[1];
  if (!section || !key) return record;
  const current = (record as unknown as Record<string, unknown>)[section] as Record<string, Leaf> | undefined;
  const next = {
    ...record,
    [section]: {
      ...(current ?? {}),
      [key]: { value, confidence: 1, source: "user", confirmed: true },
    },
  };
  return next as IntakeRecord;
}

/** Fields whose stored value is "unknown", in record order. */
export function unknownFields(record: IntakeRecord, paths: readonly string[]): string[] {
  return paths.filter((p) => isUnknown(getFieldMeta(record, p)));
}

/** A stable DOM id for a review row. */
export function fieldRowId(path: string): string {
  return `review-field-${path.replace(/\./g, "-")}`;
}
