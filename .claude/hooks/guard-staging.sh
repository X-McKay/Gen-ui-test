#!/bin/sh
# PreToolUse hook (Bash): refuse git commands that would stage secrets or local artefacts.
# Exit 2 blocks the call and returns the message to Claude. Everything else passes.
set -u
cmd=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null) || exit 0
case "$cmd" in
  *"git add"*|*"git commit"*|*"git stage"*) ;;
  *) exit 0 ;;
esac
if printf '%s' "$cmd" | grep -Eq '(^|[[:space:]/])\.env([[:space:]]|$|\.local|\.production|\.development)|[[:alnum:]_./-]+\.db([[:space:]]|$)|\.playwright-mcp|git add[^|;&]* (-f|--force)'; then
  printf 'Blocked: this command would stage a .env file, a SQLite database, Playwright MCP artefacts or force-add an ignored file. Secrets live only in the environment; see CLAUDE.md.\n' >&2
  exit 2
fi
exit 0
