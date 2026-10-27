#!/bin/bash
# Claude Code (native installer -> ~/.local/bin/claude)
set -euo pipefail
. "$(dirname "$0")/common.sh"
fetch_to_file https://claude.ai/install.sh "${AGENTIC_TMP}/claude-install.sh"
bash "${AGENTIC_TMP}/claude-install.sh"
rm -f "${AGENTIC_TMP}/claude-install.sh"
claude --version
