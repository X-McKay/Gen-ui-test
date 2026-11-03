#!/bin/sh
# PostToolUse hook (Edit|Write): format the file Claude just changed with the project's own
# formatter so diffs never carry formatting noise. Always exits 0; formatting is advisory.
set -u
root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
file=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))' 2>/dev/null) || exit 0
[ -n "$file" ] && [ -f "$file" ] || exit 0
case "$file" in
  "$root"/backend/*.py)
    (cd "$root/backend" && uv run --quiet ruff format "$file" >/dev/null 2>&1; uv run --quiet ruff check --fix --quiet "$file" >/dev/null 2>&1) ;;
  "$root"/frontend/lib/intakeTypes.ts) ;;   # generated, never reformatted
  "$root"/frontend/*.ts|"$root"/frontend/*.tsx|"$root"/frontend/*.mjs|"$root"/frontend/*.css|"$root"/frontend/*.json|"$root"/frontend/*.md)
    [ -x "$root/frontend/node_modules/.bin/prettier" ] && (cd "$root/frontend" && node_modules/.bin/prettier --log-level silent --write "$file" >/dev/null 2>&1) ;;
esac
exit 0
