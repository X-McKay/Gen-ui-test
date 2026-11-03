import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ALLOWED_HOSTS, RepositoryUrlForm, validateRepoUrl } from "@/components/repo/RepositoryUrlForm";

describe("validateRepoUrl", () => {
  it("requires a value", () => {
    expect(validateRepoUrl("")).toBe("Enter the repository URL.");
    expect(validateRepoUrl("   ")).toBe("Enter the repository URL.");
  });

  it("requires a full https URL", () => {
    expect(validateRepoUrl("github.com/org/repo")).toBe("Enter a full URL, starting with https://");
    expect(validateRepoUrl("http://github.com/org/repo")).toBe("Only https:// URLs are accepted.");
    expect(validateRepoUrl("ssh://git@github.com/org/repo")).toBe("Only https:// URLs are accepted.");
  });

  it("rejects hosts outside the allow-list with the exact message", () => {
    expect(validateRepoUrl("https://example.com/org/repo")).toBe(
      `Host example.com is not allowed. Allowed: ${ALLOWED_HOSTS.join(", ")}`,
    );
    expect(validateRepoUrl("https://github.com.evil.io/org/repo")).toContain("is not allowed");
  });

  it("requires an organisation and a repository segment", () => {
    expect(validateRepoUrl("https://github.com/org")).toBe(
      "Include the organisation and repository, for example https://github.com/org/repo",
    );
    expect(validateRepoUrl("https://github.com/org/")).toContain("Include the organisation");
  });

  it("accepts every allowed host, trailing slashes, .git and mixed case", () => {
    expect(validateRepoUrl("https://github.com/intake-fixtures/hr-screening")).toBeNull();
    expect(validateRepoUrl("https://gitlab.com/group/subgroup/project/")).toBeNull();
    expect(validateRepoUrl("https://dev.azure.com/org/project/_git/repo")).toBeNull();
    expect(validateRepoUrl("https://GitHub.com/org/repo.git")).toBeNull();
    expect(validateRepoUrl("  https://github.com/org/repo  ")).toBeNull();
  });
});

describe("RepositoryUrlForm", () => {
  it("shows the host error inline after blur and keeps the button disabled", () => {
    const onSubmit = vi.fn();
    render(<RepositoryUrlForm onSubmit={onSubmit} />);
    const input = screen.getByTestId("repo-url");
    fireEvent.change(input, { target: { value: "https://example.com/org/repo" } });
    fireEvent.blur(input);
    expect(screen.getByTestId("repo-url-error")).toHaveTextContent(
      "Host example.com is not allowed. Allowed: github.com, gitlab.com, dev.azure.com",
    );
    expect(screen.getByTestId("repo-url-error")).toHaveAttribute("role", "alert");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByTestId("analyze-repository")).toBeDisabled();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("enables the button for a valid URL and submits the trimmed values", () => {
    const onSubmit = vi.fn();
    render(<RepositoryUrlForm onSubmit={onSubmit} />);
    fireEvent.change(screen.getByTestId("repo-url"), { target: { value: " https://github.com/org/repo " } });
    expect(screen.getByTestId("analyze-repository")).toBeEnabled();
    fireEvent.change(screen.getByTestId("repo-token"), { target: { value: "ghp_token " } });
    fireEvent.submit(screen.getByTestId("repository-url-form"));
    expect(onSubmit).toHaveBeenCalledWith({ repoUrl: "https://github.com/org/repo", accessToken: "ghp_token" });
  });
});
