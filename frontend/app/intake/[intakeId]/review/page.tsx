"use client";

import * as React from "react";
import { useParams } from "next/navigation";
import { toast } from "sonner";

import { ClassificationSummary } from "@/components/review/ClassificationSummary";
import { EscalationBanner } from "@/components/review/EscalationBanner";
import { IntakeReviewPanel } from "@/components/review/IntakeReviewPanel";
import { fieldRowId, setFieldValue } from "@/components/review/recordFields";
import { ReviewActions } from "@/components/review/ReviewActions";
import { ReviewErrorState } from "@/components/review/ReviewErrorState";
import { ReviewHeader } from "@/components/review/ReviewHeader";
import { ReviewSkeleton } from "@/components/review/ReviewSkeleton";
import { apiClient, ApiError } from "@/lib/apiClient";
import type { IntakeRecord, IntakeStatus } from "@/lib/intakeTypes";
import { fieldLabel } from "@/lib/fieldCatalog";

type LoadState =
  | { status: "loading" }
  | { status: "error"; kind: "not-found" | "unavailable"; detail?: string }
  | { status: "ready"; record: IntakeRecord };

async function fetchIntake(intakeId: string): Promise<LoadState> {
  try {
    const response = await apiClient.getIntake(intakeId);
    return { status: "ready", record: response.record };
  } catch (error) {
    // The proxy answers 404 with no JSON body when the backend itself is unreachable;
    // only a backend 404 (which carries a JSON `detail`) means the intake does not exist.
    if (error instanceof ApiError && error.status === 404 && error.detail !== undefined) {
      return { status: "error", kind: "not-found" };
    }
    const detail = error instanceof ApiError ? `${error.status} ${error.message}` : undefined;
    return { status: "error", kind: "unavailable", detail };
  }
}

export default function ReviewPage() {
  const params = useParams<{ intakeId: string }>();
  const intakeId = params.intakeId;

  const [state, setState] = React.useState<LoadState>({ status: "loading" });
  const [retrying, setRetrying] = React.useState(false);
  const [highlighted, setHighlighted] = React.useState<string | null>(null);
  const highlightTimer = React.useRef<number | null>(null);

  React.useEffect(() => {
    let active = true;
    fetchIntake(intakeId).then((next) => {
      if (active) setState(next);
    });
    return () => {
      active = false;
    };
  }, [intakeId]);

  React.useEffect(() => {
    if (state.status !== "ready") return;
    const name = state.record.project?.name?.value;
    const title = typeof name === "string" && name !== "unknown" && name.trim() ? name : "Review";
    document.title = `${title} · AI Governance Intake`;
  }, [state]);

  const retry = async () => {
    setRetrying(true);
    setState(await fetchIntake(intakeId));
    setRetrying(false);
  };

  const goToField = React.useCallback((path: string) => {
    const row = document.getElementById(fieldRowId(path));
    if (!row) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    row.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "center" });
    row.focus({ preventScroll: true });
    setHighlighted(null);
    if (highlightTimer.current) window.clearTimeout(highlightTimer.current);
    requestAnimationFrame(() => setHighlighted(path));
    highlightTimer.current = window.setTimeout(() => setHighlighted(null), 1800);
  }, []);

  const saveField = React.useCallback(
    async (path: string, value: unknown) => {
      if (state.status !== "ready") return;
      const previous = state.record;
      setState({ status: "ready", record: setFieldValue(previous, path, value) });
      try {
        const updated = await apiClient.updateFields(intakeId, [{ path, value }]);
        setState({ status: "ready", record: updated });
        toast.success(`${fieldLabel(path)} saved`);
      } catch (error) {
        setState({ status: "ready", record: previous });
        const message = error instanceof ApiError ? error.message : "The server did not respond.";
        toast.error(`Could not save ${fieldLabel(path)}`, { description: message });
        throw error;
      }
    },
    [intakeId, state],
  );

  const onSubmitted = (status: string) => {
    if (state.status !== "ready") return;
    const next: IntakeStatus = status === "submitted" ? "submitted" : (state.record.meta.status ?? "completed");
    setState({ status: "ready", record: { ...state.record, meta: { ...state.record.meta, status: next } } });
  };

  return (
    <div className="mx-auto w-full max-w-[1200px] px-4 py-8 md:px-6 md:py-10">
      {state.status === "loading" && <ReviewSkeleton />}

      {state.status === "error" && (
        <div className="flex min-h-[60vh] items-center py-8">
          <ReviewErrorState
            kind={state.kind}
            intakeId={intakeId}
            detail={state.detail}
            onRetry={() => void retry()}
            retrying={retrying}
          />
        </div>
      )}

      {state.status === "ready" && (
        <ReviewContent
          intakeId={intakeId}
          record={state.record}
          highlighted={highlighted}
          onGoToField={goToField}
          onSave={saveField}
          onSubmitted={onSubmitted}
        />
      )}
    </div>
  );
}

function ReviewContent({
  intakeId,
  record,
  highlighted,
  onGoToField,
  onSave,
  onSubmitted,
}: {
  intakeId: string;
  record: IntakeRecord;
  highlighted: string | null;
  onGoToField: (path: string) => void;
  onSave: (path: string, value: unknown) => Promise<void>;
  onSubmitted: (status: string) => void;
}) {
  const prohibited = record.assessment?.eu_ai_act?.classification === "prohibited";
  const readOnly = prohibited || record.meta.status === "submitted";

  return (
    <div className="flex flex-col gap-8">
      {prohibited && <EscalationBanner />}
      <ReviewHeader record={record} />
      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-8">
        <IntakeReviewPanel record={record} readOnly={readOnly} highlightedField={highlighted} onSave={onSave} />
        <div className="flex flex-col gap-4 lg:sticky lg:top-[88px] lg:max-h-[calc(100vh-104px)] lg:overflow-y-auto lg:pr-2 lg:[scrollbar-color:var(--border)_transparent] lg:[scrollbar-width:thin]">
          <ClassificationSummary record={record} onGoToField={onGoToField} />
          <ReviewActions intakeId={intakeId} record={record} readOnly={prohibited} onSubmitted={onSubmitted} />
        </div>
      </div>
    </div>
  );
}
