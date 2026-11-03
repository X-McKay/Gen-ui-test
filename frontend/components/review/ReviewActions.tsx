"use client";

import * as React from "react";
import { Check, Download, FileText, Loader2, Send } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { apiClient, ApiError } from "@/lib/apiClient";
import type { IntakeRecord } from "@/lib/intakeTypes";

interface ReviewActionsProps {
  intakeId: string;
  record: IntakeRecord;
  /** Prohibited intakes keep downloads and nothing else. */
  readOnly: boolean;
  onSubmitted: (status: string) => void;
}

export function ReviewActions({ intakeId, record, readOnly, onSubmitted }: ReviewActionsProps) {
  const [submitting, setSubmitting] = React.useState(false);
  const submitted = record.meta.status === "submitted";

  const submit = async () => {
    setSubmitting(true);
    try {
      const result = await apiClient.submitIntake(intakeId);
      onSubmitted(result.status);
      if (result.delivered) toast.success("Submitted", { description: result.message });
      else toast.info("Marked as submitted", { description: result.message });
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "The server did not respond.";
      toast.error("Could not submit", { description: message });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="surface-enter flex flex-col gap-2" data-testid="review-actions">
      <div className="grid grid-cols-2 gap-2">
        <Button
          variant="outline"
          nativeButton={false}
          render={<a href={apiClient.exportJsonUrl(intakeId)} download={`intake-${intakeId}.json`} />}
          data-testid="download-json"
        >
          <Download aria-hidden="true" />
          Download JSON
        </Button>
        <Button
          variant="outline"
          nativeButton={false}
          render={<a href={apiClient.exportPdfUrl(intakeId)} download={`intake-${intakeId}.pdf`} />}
          data-testid="download-pdf"
        >
          <FileText aria-hidden="true" />
          Download PDF
        </Button>
      </div>
      {!readOnly && (
        <Button
          type="button"
          onClick={() => void submit()}
          disabled={submitting || submitted}
          data-testid="submit-intake"
          data-submitted={submitted || undefined}
          aria-label={submitted ? "Submitted" : "Submit intake"}
          className="w-full"
        >
          {submitted ? (
            <Check aria-hidden="true" />
          ) : submitting ? (
            <Loader2 className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
          ) : (
            <Send aria-hidden="true" />
          )}
          {submitted ? "Submitted" : submitting ? "Submitting" : "Submit"}
        </Button>
      )}
    </div>
  );
}
