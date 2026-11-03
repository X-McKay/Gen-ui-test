"use client";

import * as React from "react";
import { Loader2, ScanSearch } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export const ALLOWED_HOSTS = ["github.com", "gitlab.com", "dev.azure.com"] as const;

export interface RepositoryUrlFormValues {
  repoUrl: string;
  accessToken?: string;
}

interface RepositoryUrlFormProps {
  onSubmit: (values: RepositoryUrlFormValues) => Promise<void> | void;
  busy?: boolean;
  error?: string | null;
  defaultUrl?: string;
  className?: string;
}

/** Returns a message when the URL is not acceptable, otherwise null. */
export function validateRepoUrl(raw: string): string | null {
  const value = raw.trim();
  if (value === "") return "Enter the repository URL.";
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    return "Enter a full URL, starting with https://";
  }
  if (parsed.protocol !== "https:") return "Only https:// URLs are accepted.";
  const host = parsed.hostname.toLowerCase();
  if (!(ALLOWED_HOSTS as readonly string[]).includes(host)) {
    return `Host ${parsed.hostname} is not allowed. Allowed: ${ALLOWED_HOSTS.join(", ")}`;
  }
  if (parsed.pathname.replace(/\/+$/, "").split("/").filter(Boolean).length < 2) {
    return "Include the organisation and repository, for example https://github.com/org/repo";
  }
  return null;
}

export function RepositoryUrlForm({
  onSubmit,
  busy = false,
  error = null,
  defaultUrl = "",
  className,
}: RepositoryUrlFormProps) {
  const [repoUrl, setRepoUrl] = React.useState(defaultUrl);
  const [accessToken, setAccessToken] = React.useState("");
  const [touched, setTouched] = React.useState(defaultUrl !== "");

  const validation = validateRepoUrl(repoUrl);
  const showValidation = touched && repoUrl.trim() !== "" && validation !== null;
  const message = showValidation ? validation : error;
  const invalid = Boolean(message);
  const canSubmit = validation === null && !busy;

  const urlId = React.useId();
  const tokenId = React.useId();
  const errorId = `${urlId}-error`;
  const tokenHelpId = `${tokenId}-help`;

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setTouched(true);
    if (!canSubmit) return;
    const token = accessToken.trim();
    await onSubmit({ repoUrl: repoUrl.trim(), ...(token ? { accessToken: token } : {}) });
  };

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      className={cn("flex w-full flex-col gap-6", className)}
      aria-busy={busy}
      data-testid="repository-url-form"
    >
      <div className="flex flex-col gap-2">
        <Label htmlFor={urlId}>Repository URL</Label>
        <Input
          id={urlId}
          type="url"
          inputMode="url"
          name="repoUrl"
          value={repoUrl}
          onChange={(event) => setRepoUrl(event.target.value)}
          onBlur={() => setTouched(true)}
          placeholder="https://github.com/org/repo"
          autoComplete="off"
          autoCapitalize="off"
          spellCheck={false}
          required
          disabled={busy}
          aria-invalid={invalid || undefined}
          aria-describedby={message ? errorId : undefined}
          data-testid="repo-url"
          className="font-mono text-sm"
        />
        <p
          id={errorId}
          role={message ? "alert" : undefined}
          data-testid="repo-url-error"
          className={cn("min-h-5 text-sm text-destructive", !message && "sr-only")}
        >
          {message ?? ""}
        </p>
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor={tokenId}>Access token (optional)</Label>
        <Input
          id={tokenId}
          type="password"
          name="accessToken"
          value={accessToken}
          onChange={(event) => setAccessToken(event.target.value)}
          autoComplete="off"
          disabled={busy}
          aria-describedby={tokenHelpId}
          data-testid="repo-token"
          className="font-mono text-sm"
        />
        <p id={tokenHelpId} className="text-sm text-muted-foreground">
          Defaults to the server token when empty.
        </p>
      </div>

      <div>
        <Button type="submit" disabled={!canSubmit} data-testid="analyze-repository" className="w-full sm:w-auto">
          {busy ? (
            <Loader2 className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
          ) : (
            <ScanSearch aria-hidden="true" />
          )}
          {busy ? "Analyzing repository" : "Analyze repository"}
        </Button>
      </div>
    </form>
  );
}
