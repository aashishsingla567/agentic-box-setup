#!/bin/bash
# Claude Code (native installer -> ~/.local/bin/claude)
set -u
. "$(dirname "$0")/common.sh"
fetch_to_file https://claude.ai/install.sh /tmp/agentic-claude-install.sh
bash /tmp/agentic-claude-install.sh
rm -f /tmp/agentic-claude-install.sh
claude --version
