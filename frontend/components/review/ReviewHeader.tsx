import { FilePlus2, GitBranch } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { formatQuestionCount, formatRepoUrl } from "@/lib/formatters";
import type { IntakeRecord } from "@/lib/intakeTypes";

interface ReviewHeaderProps {
  record: IntakeRecord;
}

/** Project name, intake id, mode and the question count, above both columns. */
export function ReviewHeader({ record }: ReviewHeaderProps) {
  const name = record.project?.name?.value;
  const title = typeof name === "string" && name !== "unknown" && name.trim() !== "" ? name : "Untitled project";
  const mode = record.meta.mode ?? "new";
  const repoUrl = record.meta.repo_url ?? null;
  const count = record.meta.question_count;
  const status = record.meta.status;

  return (
    <header className="surface-enter flex flex-col gap-3" data-testid="review-header">
      <p className="text-sm text-muted-foreground">Review and classification</p>
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <h1 className="max-w-[28ch] text-[1.75rem] leading-tight font-medium tracking-[-0.02em] text-balance md:text-xl">
          {title}
        </h1>
        <p className="tabular text-sm text-muted-foreground" data-testid="question-count">
          {formatQuestionCount(count)}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-muted-foreground">
        <Badge variant="accent" data-testid="review-mode" data-mode={mode}>
          {mode === "existing" ? <GitBranch aria-hidden="true" /> : <FilePlus2 aria-hidden="true" />}
          {mode === "existing" ? "Existing project" : "New project"}
        </Badge>
        {mode === "existing" && repoUrl && (
          <a
            href={repoUrl}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex min-h-11 items-center rounded-md font-mono text-[0.8125rem] text-foreground underline-offset-4 hover:underline"
            data-testid="review-repo-url"
          >
            {formatRepoUrl(repoUrl)}
          </a>
        )}
        <span className="inline-flex min-h-11 items-center gap-1.5">
          <span>Intake</span>
          <code
            className="rounded-sm bg-muted px-1.5 py-0.5 font-mono text-[0.8125rem] text-foreground"
            data-testid="intake-id"
          >
            {record.meta.intake_id}
          </code>
        </span>
        {status === "submitted" && <Badge variant="muted">Submitted</Badge>}
      </div>
    </header>
  );
}
