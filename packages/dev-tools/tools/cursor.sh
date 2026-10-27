#!/bin/bash
# Cursor editor (.deb) + Cursor agent CLI.
# Bump CURSOR_VERSION when a new stable lands (see https://cursor.com/download).
set -euo pipefail
. "$(dirname "$0")/common.sh"
CURSOR_VERSION="${CURSOR_VERSION:-3.22}"
if [[ ${AGENTIC_DESKTOP:-false} == true ]]; then
fetch_to_file \
  "https://api2.cursor.sh/updates/download/golden/linux-x64-deb/cursor/$CURSOR_VERSION" \
  "${AGENTIC_TMP}/cursor.deb"
sudo apt-get install -y "${AGENTIC_TMP}/cursor.deb"
rm -f "${AGENTIC_TMP}/cursor.deb"
cursor --version | head -1
fi
# Agent CLI (provides the `agent` command T3 Code uses as its Cursor provider)
fetch_to_file https://cursor.com/install "${AGENTIC_TMP}/cursor-cli.sh"
bash "${AGENTIC_TMP}/cursor-cli.sh"
rm -f "${AGENTIC_TMP}/cursor-cli.sh"
agent --version
