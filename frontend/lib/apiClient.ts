/**
 * Typed client for the backend REST API. Every call goes through the same-origin
 * `/api/backend` proxy configured in `next.config.ts`, so the browser never talks to the
 * backend host directly (CSP `connect-src 'self'`).
 */
import type { IntakeRecord, IntakeMode } from "@/lib/intakeTypes";

export const API_BASE = "/api/backend";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    let detail: unknown;
    try {
      detail = await response.json();
    } catch {
      detail = undefined;
    }
    const message =
      typeof detail === "object" && detail !== null && "detail" in detail
        ? String((detail as { detail: unknown }).detail)
        : response.statusText;
    throw new ApiError(response.status, message, detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** A question spec as returned by the backend (mirrors `question_bank.QuestionSpec`). */
export interface QuestionSpecDto {
  field: string;
  section: "project" | "ai_system" | "data" | "use_case" | "controls";
  label: string;
  prompt: string;
  control: "choice" | "multi" | "yes_no" | "text";
  options: { value: string; label: string; description?: string | null }[];
  required: boolean;
  must_confirm: boolean;
  is_gate: boolean;
  why_asked?: string | null;
  sensitive: boolean;
  placeholder?: string | null;
  suggested?: unknown;
}

export interface AssumptionDto {
  field: string;
  label: string;
  value: unknown;
  display_value: string;
  confidence: number;
  source: string;
  must_confirm: boolean;
  section: "project" | "ai_system" | "data" | "use_case" | "controls";
}

export interface SectionProgressDto {
  section: "project" | "ai_system" | "data" | "use_case" | "controls";
  label: string;
  total: number;
  done: number;
  active: boolean;
}

/** The step the interview is on; persisted so a reload can restore it. */
export interface CurrentStepDto {
  step_number: number;
  surface_id: string;
  kind: "interview" | "findings" | "escalation" | "done";
  intro?: string;
  section?: "project" | "ai_system" | "data" | "use_case" | "controls";
  assumptions: AssumptionDto[];
  questions: QuestionSpecDto[];
  progress: SectionProgressDto[];
}

export interface RepositoryFindingDto {
  field: string;
  label: string;
  value: unknown;
  display_value: string;
  confidence: number;
  evidence_path: string;
  snippet: string;
}

export interface IntakeResponse {
  record: IntakeRecord;
  current_step: CurrentStepDto | null;
}

export interface FieldUpdateDto {
  path: string;
  value: unknown;
}

export const apiClient = {
  createIntake(body: {
    mode: IntakeMode;
    owner?: string;
    name?: string;
    description?: string;
    repo_url?: string;
  }): Promise<IntakeRecord> {
    return request<IntakeRecord>("/intakes", { method: "POST", body: JSON.stringify(body) });
  },
  getIntake(intakeId: string): Promise<IntakeResponse> {
    return request<IntakeResponse>(`/intakes/${encodeURIComponent(intakeId)}`);
  },
  updateFields(intakeId: string, updates: FieldUpdateDto[]): Promise<IntakeRecord> {
    return request<IntakeRecord>(`/intakes/${encodeURIComponent(intakeId)}/fields`, {
      method: "PATCH",
      body: JSON.stringify({ updates }),
    });
  },
  submitIntake(intakeId: string): Promise<{ status: string; delivered: boolean; message: string }> {
    return request(`/intakes/${encodeURIComponent(intakeId)}/submit`, { method: "POST" });
  },
  getFindings(intakeId: string): Promise<RepositoryFindingDto[]> {
    return request<RepositoryFindingDto[]>(`/intakes/${encodeURIComponent(intakeId)}/findings`);
  },
  startRepositoryAnalysis(body: {
    intake_id: string;
    repo_url: string;
    access_token?: string;
  }): Promise<{ job_id: string }> {
    return request(`/repositories/analyze`, { method: "POST", body: JSON.stringify(body) });
  },
  exportJsonUrl(intakeId: string): string {
    return `${API_BASE}/intakes/${encodeURIComponent(intakeId)}/export.json`;
  },
  exportPdfUrl(intakeId: string): string {
    return `${API_BASE}/intakes/${encodeURIComponent(intakeId)}/export.pdf`;
  },
  analysisEventsUrl(jobId: string): string {
    return `${API_BASE}/repositories/analyze/${encodeURIComponent(jobId)}/events`;
  },
  defaults(): Promise<{ owner: string | null }> {
    return request(`/intakes/defaults`);
  },
};
