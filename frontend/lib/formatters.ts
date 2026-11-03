import { fieldLabel, FIELD_CONTROLS, optionLabel } from "@/lib/fieldCatalog";

/** `0.92` → `"92%"`. Values outside 0–1 are clamped. */
export function formatConfidence(confidence: number): string {
  const clamped = Math.min(1, Math.max(0, Number.isFinite(confidence) ? confidence : 0));
  return `${Math.round(clamped * 100)}%`;
}

export type ConfidenceLevel = "low" | "medium" | "high";

export function confidenceLevel(confidence: number): ConfidenceLevel {
  if (confidence >= 0.8) return "high";
  if (confidence >= 0.5) return "medium";
  return "low";
}

export const EMPTY_VALUE = "—";
export const UNKNOWN_VALUE = "Not sure";

/**
 * Human display for a stored field value: booleans as Yes/No, `"unknown"` as Not sure,
 * lists joined with commas (option labels when known), `null`/`undefined` as a dash.
 */
export function formatValue(field: string, value: unknown): string {
  if (value === null || value === undefined) return EMPTY_VALUE;
  if (value === "unknown") return UNKNOWN_VALUE;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) {
    if (value.length === 0) return "None";
    return value.map((item) => optionLabel(field, String(item))).join(", ");
  }
  if (typeof value === "string") {
    if (value.trim() === "") return EMPTY_VALUE;
    return FIELD_CONTROLS[field] === "text" ? value : optionLabel(field, value);
  }
  if (typeof value === "number") return String(value);
  if (typeof value === "object") {
    // Rationale entries carry `{ value: … }` wrappers; unwrap one level.
    const inner = (value as { value?: unknown }).value;
    if (inner !== undefined) return formatValue(field, inner);
    return JSON.stringify(value);
  }
  return String(value);
}

/** Short, specific source copy for provenance. */
export function formatSource(source: string | null | undefined, confirmed: boolean): string {
  if (confirmed && (!source || source === "user")) return "You confirmed";
  if (!source) return "Not set";
  if (source === "user") return "You entered";
  if (source === "inferred") return "Inferred from your description";
  if (source.startsWith("repo:")) return `Repository: ${source.slice("repo:".length)}`;
  return source;
}

export function formatDate(iso: string | null | undefined, options?: Intl.DateTimeFormatOptions): string {
  if (!iso) return EMPTY_VALUE;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return EMPTY_VALUE;
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    ...options,
  }).format(date);
}

/**
 * Keep the file name and as much of the leading path as fits:
 * `src/app/services/scoring/model.py` → `src/…/scoring/model.py`.
 */
export function truncatePath(path: string, max = 40): string {
  if (path.length <= max) return path;
  const parts = path.split("/");
  if (parts.length <= 2) return `…${path.slice(-(max - 1))}`;
  const file = parts[parts.length - 1];
  const head = parts[0];
  let tail = file;
  for (let i = parts.length - 2; i > 0; i -= 1) {
    const candidate = `${parts[i]}/${tail}`;
    if (`${head}/…/${candidate}`.length > max) break;
    tail = candidate;
  }
  const result = `${head}/…/${tail}`;
  return result.length <= max ? result : `…/${file}`.slice(0, max);
}

/** "Answered in 6 questions" with a tabular numeral; singular at 1. */
export function formatQuestionCount(count: number | undefined): string {
  const n = count ?? 0;
  return `Answered in ${n} ${n === 1 ? "question" : "questions"}`;
}

/** Shorten a repository URL to `host/org/repo`. */
export function formatRepoUrl(url: string | null | undefined): string {
  if (!url) return EMPTY_VALUE;
  try {
    const parsed = new URL(url);
    const path = parsed.pathname.replace(/^\/+|\/+$/g, "").replace(/\.git$/, "");
    return `${parsed.host}/${path}`;
  } catch {
    return url;
  }
}

export { fieldLabel };
