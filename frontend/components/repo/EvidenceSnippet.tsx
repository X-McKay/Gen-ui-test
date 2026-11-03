import { FileCode2 } from "lucide-react";

import { truncatePath } from "@/lib/formatters";
import { cn } from "@/lib/utils";

interface EvidenceSnippetProps {
  path: string;
  snippet: string;
  className?: string;
}

/** A file path and the lines that support a finding, kept to a few lines. */
export function EvidenceSnippet({ path, snippet, className }: EvidenceSnippetProps) {
  return (
    <figure
      data-testid="evidence-snippet"
      className={cn("flex min-w-0 flex-col gap-1.5 text-sm", className)}
    >
      <figcaption className="flex min-w-0 items-center gap-1.5 text-muted-foreground">
        <FileCode2 className="size-3.5 shrink-0" aria-hidden="true" />
        <code className="truncate font-mono text-[0.8125rem] text-foreground" title={path}>
          {truncatePath(path, 48)}
        </code>
      </figcaption>
      <pre
        className="max-h-24 overflow-hidden rounded-md border border-hairline bg-muted/60 px-3 py-2 font-mono text-[0.8125rem] leading-5 text-foreground/90 [mask-image:linear-gradient(to_bottom,black_70%,transparent)] whitespace-pre-wrap [overflow-wrap:anywhere] dark:bg-muted/40"
        tabIndex={0}
        aria-label={`Evidence from ${path}`}
      >
        <code>{snippet.trimEnd()}</code>
      </pre>
    </figure>
  );
}
