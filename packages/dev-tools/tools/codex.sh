#!/bin/bash
# OpenAI Codex CLI (npm)
set -euo pipefail
. "$(dirname "$0")/common.sh"
need_node || exit 1
npm install -g "@openai/codex@${CODEX_VERSION:-latest}"
codex --version
