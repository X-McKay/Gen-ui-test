"use client";

import { useAgent, useCopilotKit } from "@copilotkit/react-core/v2";
import { GenerativeUISurface } from "@copilotkit/react-core/v2/generative-ui";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ProgressRail } from "@/components/intake/ProgressRail";
import { StatusLine } from "@/components/intake/StatusLine";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { INTERVIEW_TARGET_ID, intakeUI } from "@/generative-ui/intakeCatalog";
import type { SectionProgressDto } from "@/lib/apiClient";
import { AGENT_ID, readAgentState, type IntakeAgentState } from "@/lib/intakeState";

const EMPTY_PROGRESS: SectionProgressDto[] = [
  { section: "project", label: "Project", total: 1, done: 0, active: false },
  { section: "ai_system", label: "AI system", total: 1, done: 0, active: false },
  { section: "data", label: "Data", total: 1, done: 0, active: false },
  { section: "use_case", label: "Use case", total: 1, done: 0, active: false },
];

function SurfaceSkeleton() {
  return (
    <div className="grid gap-6 rounded-[var(--radius)] border bg-card p-6 shadow-sm" aria-hidden="true">
      <div className="grid gap-2">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-6 w-3/4" />
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <Skeleton className="h-11 w-full" />
        <Skeleton className="h-11 w-full" />
        <Skeleton className="h-11 w-full" />
        <Skeleton className="h-11 w-full" />
      </div>
      <div className="grid gap-3">
        <Skeleton className="h-5 w-2/3" />
        <Skeleton className="h-11 w-56" />
      </div>
      <div className="flex justify-end border-t pt-4">
        <Skeleton className="h-11 w-44" />
      </div>
    </div>
  );
}

export interface IntakeSurfaceProps {
  intakeId: string;
  /** The first message to send when the thread has no history yet. */
  initialMessage: string;
  /** Shown while the first run has produced nothing yet. */
  initialStatus: string;
  /** Extra content above the surface (for example repository analysis progress). */
  children?: React.ReactNode;
  /** Do not start the agent until this is true (the repository analysis must finish first). */
  ready?: boolean;
}

/**
 * The interview column: progress rail, streaming status line and the single generative-UI
 * target the agent renders into. Starts the first run and redirects to the review page.
 */
export function IntakeSurface({ intakeId, initialMessage, initialStatus, children, ready = true }: IntakeSurfaceProps) {
  const router = useRouter();
  const { copilotkit } = useCopilotKit();
  // A thread-scoped proxy of the runtime agent, one per intake.
  const { agent, isReady } = useAgent({
    agentId: `${AGENT_ID}-${intakeId}`,
    runtimeAgentId: AGENT_ID,
    threadId: intakeId,
  });
  const [state, setState] = useState<IntakeAgentState>({});
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const startedRef = useRef(false);

  useEffect(() => {
    if (!isReady) return;
    const subscription = agent.subscribe({
      onStateChanged: ({ state: next }) => setState(readAgentState(next)),
      onRunStartedEvent: () => {
        setRunning(true);
        setError(null);
      },
      onRunFinalized: () => setRunning(false),
      onRunFailed: ({ error: cause }) => {
        setRunning(false);
        setError(cause instanceof Error ? cause.message : "The agent could not continue.");
      },
    });
    // Read the current state once the subscription is in place (outside the render pass).
    const initial = window.setTimeout(() => setState(readAgentState(agent.state)), 0);
    return () => {
      window.clearTimeout(initial);
      subscription.unsubscribe();
    };
  }, [agent, isReady]);

  const start = useCallback(async () => {
    if (!isReady || startedRef.current) return;
    startedRef.current = true;
    try {
      agent.addMessage({ id: crypto.randomUUID(), role: "user", content: initialMessage });
      await copilotkit.runAgent({ agent });
    } catch (cause) {
      startedRef.current = false;
      setError(cause instanceof Error ? cause.message : "The agent could not start.");
    }
  }, [agent, copilotkit, initialMessage, isReady]);

  useEffect(() => {
    if (!(ready && isReady) || agent.isRunning || agent.messages.length > 0) return;
    const timer = window.setTimeout(() => void start(), 0);
    return () => window.clearTimeout(timer);
  }, [ready, isReady, agent, start]);

  const step = state.intake_step;
  const status = state.intake_record?.meta.status;
  useEffect(() => {
    if (step?.kind === "done" || status === "completed" || status === "submitted") {
      router.push(`/intake/${intakeId}/review`);
    }
  }, [step?.kind, status, intakeId, router]);

  const statusText = useMemo(() => {
    if (error) return null;
    if (running) return state.intake_status ?? (step ? "Working…" : initialStatus);
    return null;
  }, [error, running, state.intake_status, step, initialStatus]);

  return (
    <div className="grid gap-5" data-testid="intake-surface" data-step={step?.step_number ?? 0}>
      <ProgressRail sections={step?.progress ?? EMPTY_PROGRESS} />
      {children}
      <StatusLine text={statusText} busy={running} />
      {error ? (
        <div role="alert" className="grid gap-3 rounded-[var(--radius)] border border-destructive/40 bg-destructive/5 p-4" data-testid="agent-error">
          <p className="text-sm font-medium">Something went wrong while talking to the agent.</p>
          <p className="text-sm text-muted-foreground">{error}</p>
          <div>
            <Button
              type="button"
              variant="secondary"
              className="h-11"
              onClick={async () => {
                setError(null);
                try {
                  await copilotkit.runAgent({ agent });
                } catch (cause) {
                  setError(cause instanceof Error ? cause.message : "The agent could not continue.");
                }
              }}
            >
              Try again
            </Button>
          </div>
        </div>
      ) : null}
      <GenerativeUISurface
        id={INTERVIEW_TARGET_ID}
        ui={intakeUI}
        description="The interview column. Render exactly one InterviewStep (or EscalationNotice) per step here."
        fallback={running || !step ? <SurfaceSkeleton /> : null}
        autoScroll={false}
      />
    </div>
  );
}
