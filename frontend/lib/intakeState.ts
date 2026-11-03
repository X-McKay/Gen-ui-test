/** Shared agent state (AG-UI state snapshots) as the frontend reads it. */
import type { IntakeRecord } from "@/lib/intakeTypes";
import type { AssumptionDto, QuestionSpecDto, SectionProgressDto } from "@/lib/apiClient";

export const AGENT_ID = "intake";

export interface StepState {
  step_number: number;
  surface_id: string;
  previous_surface_id?: string | null;
  kind: "interview" | "findings" | "escalation" | "done";
  intro: string;
  section?: SectionProgressDto["section"] | null;
  assumptions: AssumptionDto[];
  questions: QuestionSpecDto[];
  progress: SectionProgressDto[];
}

export interface IntakeAgentState {
  intake_record?: IntakeRecord;
  intake_step?: StepState;
  intake_status?: string | null;
}

export function readAgentState(raw: unknown): IntakeAgentState {
  if (typeof raw !== "object" || raw === null) return {};
  const state = raw as Record<string, unknown>;
  const result: IntakeAgentState = {};
  if (typeof state.intake_record === "object" && state.intake_record !== null) {
    result.intake_record = state.intake_record as IntakeRecord;
  }
  if (typeof state.intake_step === "object" && state.intake_step !== null) {
    result.intake_step = state.intake_step as StepState;
  }
  if (typeof state.intake_status === "string" || state.intake_status === null) {
    result.intake_status = state.intake_status as string | null;
  }
  return result;
}
