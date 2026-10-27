#!/bin/bash
# T3 Code: `t3` terminal CLI + desktop app (.deb, latest GitHub release).
set -euo pipefail
. "$(dirname "$0")/common.sh"

echo "--- t3 CLI ---"
fetch_to_file https://t3.codes/install.sh "${AGENTIC_TMP}/t3-install.sh"
sh "${AGENTIC_TMP}/t3-install.sh"
rm -f "${AGENTIC_TMP}/t3-install.sh"
t3 --version

[[ ${AGENTIC_DESKTOP:-false} == true ]] || exit 0

echo "--- T3 Code desktop ---"
VER=$(curl -fsSL https://api.github.com/repos/pingdotgg/t3code/releases/latest \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'])")
fetch_to_file \
  "https://github.com/pingdotgg/t3code/releases/download/${VER}/T3-Code-${VER#v}-amd64.deb" \
  "${AGENTIC_TMP}/t3code.deb"
sudo apt-get install -y "${AGENTIC_TMP}/t3code.deb"
rm -f "${AGENTIC_TMP}/t3code.deb"
dpkg-query -W -f='t3code ${Version}\n' t3code
