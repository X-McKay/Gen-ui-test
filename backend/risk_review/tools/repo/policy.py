"""Tool policies for the repository toolset."""

from __future__ import annotations

from risk_review.tools.common.policy import ToolPolicy

OWNER = "platform"

REPO_TOOL_POLICIES: dict[str, ToolPolicy] = {
    name: ToolPolicy(
        name=name,
        owner=OWNER,
        effect="read",
        retry_safety="safe",
        timeout_seconds=10,
        data_classification="internal",
        max_output_bytes=32 * 1024,
    )
    for name in ("list_files", "read_file", "search_text")
}
