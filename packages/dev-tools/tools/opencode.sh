#!/bin/bash
# opencode (v1 stable channel)
set -euo pipefail
. "$(dirname "$0")/common.sh"
fetch_to_file https://opencode.ai/install "$AGENTIC_TMP/opencode.sh"
bash "$AGENTIC_TMP/opencode.sh"
opencode --version
