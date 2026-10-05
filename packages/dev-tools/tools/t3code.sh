#!/bin/bash
# T3 Code: `t3` terminal CLI + desktop app (.deb, latest GitHub release).
set -u
. "$(dirname "$0")/common.sh"

echo "--- t3 CLI ---"
fetch_to_file https://t3.codes/install.sh /tmp/agentic-t3-install.sh
sh /tmp/agentic-t3-install.sh
rm -f /tmp/agentic-t3-install.sh
t3 --version

echo "--- T3 Code desktop ---"
VER=$(curl -fsSL https://api.github.com/repos/pingdotgg/t3code/releases/latest \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'])")
fetch_to_file \
  "https://github.com/pingdotgg/t3code/releases/download/${VER}/T3-Code-${VER#v}-amd64.deb" \
  /tmp/agentic-t3code.deb
sudo dpkg -i /tmp/agentic-t3code.deb
sudo apt-get install -f -y
rm -f /tmp/agentic-t3code.deb
dpkg-query -W -f='t3code ${Version}\n' t3code
