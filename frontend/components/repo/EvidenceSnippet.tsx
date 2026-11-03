import { FileCode2 } from "lucide-react";

import { truncatePath } from "@/lib/formatters";
import { cn } from "@/lib/utils";

const LINE_CLAMP = { 2: "line-clamp-2", 3: "line-clamp-3", 4: "line-clamp-4" } as const;

interface EvidenceSnippetProps {
  path: string;
  snippet: string;
  /** Lines of the snippet shown before it is clamped with an ellipsis. */
  maxLines?: keyof typeof LINE_CLAMP;
  /** Overrides the default `data-testid` when one row renders the snippet twice. */
  testId?: string;
  /** Text size and spacing; the path and snippet inherit the figure's font size. */
  className?: string;
}

/** A file path and the lines that support a finding, kept to a few lines. */
export function EvidenceSnippet({
  path,
  snippet,
  maxLines = 4,
  testId = "evidence-snippet",
  className,
}: EvidenceSnippetProps) {
  return (
    <figure data-testid={testId} className={cn("flex min-w-0 flex-col gap-1 text-[0.8125rem] leading-5", className)}>
      <figcaption className="flex min-w-0 items-center gap-1.5 text-muted-foreground">
        <FileCode2 className="size-3.5 shrink-0" aria-hidden="true" />
        <code className="min-w-0 truncate font-mono text-foreground" title={path}>
          {truncatePath(path, 48)}
        </code>
      </figcaption>
      <pre
        className={cn(
          "whitespace-pre-wrap rounded-md border border-hairline bg-muted/60 px-1.5 py-1 font-mono text-foreground/90 [overflow-wrap:anywhere] dark:bg-muted/40",
          LINE_CLAMP[maxLines],
        )}
      >
        <code>{snippet.trimEnd()}</code>
      </pre>
    </figure>
  );
}
