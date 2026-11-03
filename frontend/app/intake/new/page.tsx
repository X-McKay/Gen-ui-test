"use client";

import { Loader2, Sparkles } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useId, useState } from "react";

import { IntakeAgentProvider } from "@/components/intake/IntakeAgentProvider";
import { IntakeSurface } from "@/components/intake/IntakeSurface";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, apiClient } from "@/lib/apiClient";
import { RESUME_MESSAGE, START_MESSAGE } from "@/lib/intakeState";

const PLACEHOLDER =
  "An internal tool that drafts job-candidate summaries from CVs using an LLM via the OpenAI API. Recruiters read the summaries before deciding who to interview…";

function DescribeForm({ onCreated }: { onCreated: (intakeId: string) => void }) {
  const [description, setDescription] = useState("");
  const [name, setName] = useState("");
  const [owner, setOwner] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const descriptionId = useId();
  const nameId = useId();
  const ownerId = useId();

  useEffect(() => {
    apiClient
      .defaults()
      .then((defaults) => {
        if (defaults.owner) setOwner((current) => current || defaults.owner || "");
      })
      .catch(() => undefined);
  }, []);

  const tooShort = description.trim().length < 20;

  return (
    <form
      className="surface-enter grid gap-6"
      data-testid="describe-form"
      onSubmit={async (event) => {
        event.preventDefault();
        if (tooShort || busy) return;
        setBusy(true);
        setError(null);
        try {
          const record = await apiClient.createIntake({
            mode: "new",
            description: description.trim(),
            name: name.trim() || undefined,
            owner: owner.trim() || undefined,
          });
          onCreated(record.meta.intake_id);
        } catch (cause) {
          setBusy(false);
          setError(
            cause instanceof ApiError
              ? `Could not start the intake (${cause.message}).`
              : "Could not reach the server. Check that the backend is running and try again.",
          );
        }
      }}
    >
      <header className="grid gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Describe the project</h1>
        <p className="text-muted-foreground max-w-[65ch]">
          A paragraph or two is enough. We read it, infer what we can and only ask what is left.
        </p>
      </header>
      <div className="grid gap-2">
        <Label htmlFor={descriptionId}>Project description</Label>
        <Textarea
          id={descriptionId}
          data-testid="project-description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder={PLACEHOLDER}
          rows={9}
          required
          minLength={20}
          maxLength={20000}
          aria-describedby={`${descriptionId}-hint`}
          className="min-h-56 resize-y text-base leading-relaxed"
        />
        <p id={`${descriptionId}-hint`} className="text-xs text-muted-foreground">
          What it does, who uses it, what data it touches and which models are involved.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="grid gap-2">
          <Label htmlFor={nameId}>Project name (optional)</Label>
          <Input id={nameId} data-testid="project-name" value={name} onChange={(event) => setName(event.target.value)} maxLength={200} autoComplete="off" />
        </div>
        <div className="grid gap-2">
          <Label htmlFor={ownerId}>Owner (optional)</Label>
          <Input id={ownerId} data-testid="project-owner" value={owner} onChange={(event) => setOwner(event.target.value)} maxLength={200} autoComplete="off" />
        </div>
      </div>
      {error ? (
        <p role="alert" className="text-sm text-destructive" data-testid="describe-error">
          {error}
        </p>
      ) : null}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <p className="text-xs text-muted-foreground">Nothing is shared outside your organisation.</p>
        <Button type="submit" className="h-11 min-w-36 gap-2" disabled={tooShort || busy} data-testid="analyze">
          {busy ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Sparkles className="size-4" aria-hidden="true" />}
          Analyze
        </Button>
      </div>
    </form>
  );
}

function NewIntake() {
  const router = useRouter();
  const params = useSearchParams();
  const intakeId = params.get("id");
  const [resume, setResume] = useState<"loading" | "fresh" | "resume" | "missing">(intakeId ? "loading" : "fresh");

  useEffect(() => {
    if (!intakeId) return;
    let cancelled = false;
    apiClient
      .getIntake(intakeId)
      .then(({ record, current_step }) => {
        if (cancelled) return;
        if (record.meta.status === "completed" || record.meta.status === "submitted") {
          router.replace(`/intake/${intakeId}/review`);
          return;
        }
        setResume(current_step ? "resume" : "fresh");
      })
      .catch(() => {
        if (!cancelled) setResume("missing");
      });
    return () => {
      cancelled = true;
    };
  }, [intakeId, router]);

  if (!intakeId) {
    return <DescribeForm onCreated={(id) => router.replace(`/intake/new?id=${id}`)} />;
  }
  if (resume === "loading") {
    return (
      <div className="grid gap-4" aria-busy="true">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (resume === "missing") {
    return (
      <div role="alert" className="grid gap-3 rounded-[var(--radius)] border p-6">
        <p className="font-medium">We could not find that intake.</p>
        <p className="text-sm text-muted-foreground">It may have been removed, or the link is incomplete.</p>
        <div>
          <Button type="button" className="h-11" onClick={() => router.replace("/intake/new")}>
            Start a new intake
          </Button>
        </div>
      </div>
    );
  }
  return (
    <IntakeAgentProvider>
      <IntakeSurface
        intakeId={intakeId}
        initialMessage={resume === "resume" ? RESUME_MESSAGE : START_MESSAGE("See the description on file.")}
        initialStatus={resume === "resume" ? "Picking up where you left off…" : "Reading your description…"}
      />
    </IntakeAgentProvider>
  );
}

export default function NewIntakePage() {
  return (
    <div className="mx-auto w-full max-w-[720px] px-4 py-8 sm:py-12">
      <Suspense fallback={<Skeleton className="h-40 w-full" />}>
        <NewIntake />
      </Suspense>
    </div>
  );
}
