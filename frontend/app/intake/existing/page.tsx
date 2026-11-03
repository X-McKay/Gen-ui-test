"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";

import { IntakeAgentProvider } from "@/components/intake/IntakeAgentProvider";
import { IntakeSurface } from "@/components/intake/IntakeSurface";
import { StatusLine } from "@/components/intake/StatusLine";
import { RepositoryUrlForm } from "@/components/repo/RepositoryUrlForm";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, apiClient } from "@/lib/apiClient";
import { FINDINGS_MESSAGE, RESUME_MESSAGE } from "@/lib/intakeState";

type Phase =
  | { kind: "connect"; error: string | null; busy: boolean }
  | { kind: "analyzing"; intakeId: string; jobId: string; text: string; log: string[] }
  | { kind: "failed"; intakeId: string; message: string }
  | { kind: "interview"; intakeId: string; resume: boolean }
  | { kind: "loading" }
  | { kind: "missing" };

function AnalysisProgress({ text, log }: { text: string; log: string[] }) {
  return (
    <section
      className="surface-enter grid gap-3 rounded-[var(--radius)] border bg-card p-5 shadow-sm"
      aria-label="Repository analysis"
      data-testid="analysis-progress"
    >
      <StatusLine text={text} busy />
      <ol className="grid gap-1 text-xs text-muted-foreground" aria-label="Analysis steps">
        {log.map((line, index) => (
          <li key={`${index}-${line}`} data-testid="analysis-log-line">
            {line}
          </li>
        ))}
      </ol>
    </section>
  );
}

function ExistingIntake() {
  const router = useRouter();
  const params = useSearchParams();
  const intakeIdParam = params.get("id");
  const [phase, setPhase] = useState<Phase>(intakeIdParam ? { kind: "loading" } : { kind: "connect", error: null, busy: false });
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => () => sourceRef.current?.close(), []);

  useEffect(() => {
    if (!intakeIdParam) return;
    let cancelled = false;
    apiClient
      .getIntake(intakeIdParam)
      .then(({ record }) => {
        if (cancelled) return;
        if (record.meta.status === "completed" || record.meta.status === "submitted") {
          router.replace(`/intake/${intakeIdParam}/review`);
          return;
        }
        setPhase({ kind: "interview", intakeId: intakeIdParam, resume: true });
      })
      .catch(() => {
        if (!cancelled) setPhase({ kind: "missing" });
      });
    return () => {
      cancelled = true;
    };
  }, [intakeIdParam, router]);

  const analyze = useCallback(
    async ({ repoUrl, accessToken }: { repoUrl: string; accessToken?: string }) => {
      setPhase({ kind: "connect", error: null, busy: true });
      let intakeId: string;
      try {
        const record = await apiClient.createIntake({ mode: "existing", repo_url: repoUrl });
        intakeId = record.meta.intake_id;
        const { job_id: jobId } = await apiClient.startRepositoryAnalysis({
          intake_id: intakeId,
          repo_url: repoUrl,
          access_token: accessToken || undefined,
        });
        setPhase({ kind: "analyzing", intakeId, jobId, text: "Starting analysis…", log: [] });
        const source = new EventSource(apiClient.analysisEventsUrl(jobId));
        sourceRef.current = source;
        source.addEventListener("progress", (event) => {
          const data = JSON.parse((event as MessageEvent<string>).data) as { text: string };
          setPhase((current) =>
            current.kind === "analyzing" ? { ...current, text: data.text, log: [...current.log, data.text] } : current,
          );
        });
        source.addEventListener("done", () => {
          source.close();
          setPhase({ kind: "interview", intakeId, resume: false });
          router.replace(`/intake/existing?id=${intakeId}`);
        });
        source.addEventListener("error", (event) => {
          source.close();
          let message = "The analysis stopped unexpectedly.";
          try {
            const data = JSON.parse((event as MessageEvent<string>).data) as { message?: string };
            if (data.message) message = data.message;
          } catch {
            /* connection-level error */
          }
          setPhase({ kind: "failed", intakeId, message });
        });
      } catch (cause) {
        const message =
          cause instanceof ApiError
            ? cause.message
            : "Could not reach the server. Check that the backend is running and try again.";
        setPhase({ kind: "connect", error: message, busy: false });
      }
    },
    [router],
  );

  if (phase.kind === "loading") {
    return (
      <div className="grid gap-4" aria-busy="true">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (phase.kind === "missing") {
    return (
      <div role="alert" className="grid gap-3 rounded-[var(--radius)] border p-6">
        <p className="font-medium">We could not find that intake.</p>
        <div>
          <Button type="button" className="h-11" onClick={() => router.replace("/intake/existing")}>
            Connect a repository
          </Button>
        </div>
      </div>
    );
  }
  if (phase.kind === "connect") {
    return (
      <div className="surface-enter grid gap-6">
        <header className="grid gap-2">
          <h1 className="text-2xl font-semibold tracking-tight">Connect the repository</h1>
          <p className="text-muted-foreground max-w-[65ch]">
            We clone it shallowly, read the manifests, docs and code signals, and never run anything in it.
          </p>
        </header>
        <RepositoryUrlForm onSubmit={analyze} busy={phase.busy} error={phase.error} />
      </div>
    );
  }
  if (phase.kind === "analyzing") {
    return <AnalysisProgress text={phase.text} log={phase.log} />;
  }
  if (phase.kind === "failed") {
    return (
      <div role="alert" className="grid gap-3 rounded-[var(--radius)] border border-destructive/40 bg-destructive/5 p-6" data-testid="analysis-error">
        <p className="font-medium">The repository could not be analysed.</p>
        <p className="text-sm text-muted-foreground">{phase.message}</p>
        <div>
          <Button type="button" variant="secondary" className="h-11" onClick={() => setPhase({ kind: "connect", error: null, busy: false })}>
            Try another URL
          </Button>
        </div>
      </div>
    );
  }
  return (
    <IntakeAgentProvider>
      <IntakeSurface
        intakeId={phase.intakeId}
        initialMessage={phase.resume ? RESUME_MESSAGE : FINDINGS_MESSAGE}
        initialStatus={phase.resume ? "Picking up where you left off…" : "Preparing what we found…"}
      />
    </IntakeAgentProvider>
  );
}

export default function ExistingIntakePage() {
  return (
    <div className="mx-auto w-full max-w-[720px] px-4 py-8 sm:py-12">
      <Suspense fallback={<Skeleton className="h-40 w-full" />}>
        <ExistingIntake />
      </Suspense>
    </div>
  );
}
