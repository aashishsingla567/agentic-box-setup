#!/bin/bash
# dev-tools package: every tool the agentic box ships with.
set -u
DIR="$(cd "$(dirname "$0")/tools" && pwd)"
for t in opencode codex claude-code cursor antigravity t3code tailscale; do
  echo "=== $t ==="
  bash "$DIR/$t.sh" || { echo "$t FAILED"; exit 1; }
done
echo "All dev tools installed. Authenticate providers:"
echo "  codex login | claude auth login | agent login | opencode auth login"
