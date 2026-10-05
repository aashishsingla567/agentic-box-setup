#!/bin/bash
# OpenAI Codex CLI (npm)
set -u
. "$(dirname "$0")/common.sh"
need_node || exit 1
npm install -g @openai/codex@latest
codex --version
