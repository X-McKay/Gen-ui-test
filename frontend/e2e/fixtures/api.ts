import type { APIRequestContext } from "@playwright/test";

import type { IntakeResponse } from "../../lib/apiClient";
import type { IntakeRecord } from "../../lib/intakeTypes";

export type { IntakeRecord, IntakeResponse };

/** Every REST call goes through the same-origin proxy, exactly as the browser does. */
export const API_PREFIX = "/api/backend";

export interface FieldMetaLike {
  value: unknown;
  confidence: number;
  source: string;
  confirmed: boolean;
}

export async function getIntake(request: APIRequestContext, intakeId: string): Promise<IntakeResponse> {
  const response = await request.get(`${API_PREFIX}/intakes/${encodeURIComponent(intakeId)}`);
  if (!response.ok()) throw new Error(`GET /intakes/${intakeId} → ${response.status()}`);
  return (await response.json()) as IntakeResponse;
}

export async function getRecord(request: APIRequestContext, intakeId: string): Promise<IntakeRecord> {
  return (await getIntake(request, intakeId)).record;
}

export async function createIntake(
  request: APIRequestContext,
  body: { mode: "new" | "existing"; description?: string; name?: string; owner?: string; repo_url?: string },
): Promise<IntakeRecord> {
  const response = await request.post(`${API_PREFIX}/intakes`, { data: body });
  if (!response.ok()) throw new Error(`POST /intakes → ${response.status()} ${await response.text()}`);
  return (await response.json()) as IntakeRecord;
}

export async function getFindingsCount(request: APIRequestContext, intakeId: string): Promise<number> {
  const response = await request.get(`${API_PREFIX}/intakes/${encodeURIComponent(intakeId)}/findings`);
  if (!response.ok()) throw new Error(`GET /intakes/${intakeId}/findings → ${response.status()}`);
  const findings = (await response.json()) as unknown[];
  return findings.length;
}

/** Read `<section>.<field>` from any record-shaped object (record or JSON export). */
export function fieldMeta(record: unknown, path: string): FieldMetaLike {
  const [section, field] = path.split(".");
  const sectionValue = (record as Record<string, unknown>)[section];
  if (typeof sectionValue !== "object" || sectionValue === null) {
    throw new Error(`Record has no section "${section}"`);
  }
  const meta = (sectionValue as Record<string, unknown>)[field];
  if (typeof meta !== "object" || meta === null || !("value" in meta)) {
    throw new Error(`Record has no field "${path}"`);
  }
  return meta as FieldMetaLike;
}

export function fieldValue(record: unknown, path: string): unknown {
  return fieldMeta(record, path).value;
}

/** `true` when two answers mean the same thing (arrays compare as sets). */
export function sameAnswer(stored: unknown, given: unknown): boolean {
  if (Array.isArray(stored) && Array.isArray(given)) {
    const a = [...stored].map(String).sort();
    const b = [...given].map(String).sort();
    return a.length === b.length && a.every((item, index) => item === b[index]);
  }
  if (typeof stored === "string" && typeof given === "string") return stored.trim() === given.trim();
  return stored === given;
}
