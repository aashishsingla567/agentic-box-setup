#!/bin/bash
# Cursor editor (.deb) + Cursor agent CLI.
# Bump CURSOR_VERSION when a new stable lands (see https://cursor.com/download).
set -u
CURSOR_VERSION="${CURSOR_VERSION:-3.22}"
fetch_to_file \
  "https://api2.cursor.sh/updates/download/golden/linux-x64-deb/cursor/$CURSOR_VERSION" \
  /tmp/agentic-cursor.deb
sudo dpkg -i /tmp/agentic-cursor.deb
sudo apt-get install -f -y
rm -f /tmp/agentic-cursor.deb
cursor --version | head -1
# Agent CLI (provides the `agent` command T3 Code uses as its Cursor provider)
fetch_to_file https://cursor.com/install /tmp/agentic-cursor-cli.sh
bash /tmp/agentic-cursor-cli.sh
rm -f /tmp/agentic-cursor-cli.sh
agent --version
