#!/bin/bash
# agentic-box-setup — turn a fresh Linux box (Mint/Ubuntu) into a remote
# agentic dev machine: dev tools, 24/7 sleepless power, Tailscale, GUI panel.
#
#   ./install.sh                 install everything
#   ./install.sh --only sleepless,rig-panel
#   ./install.sh --list
set -u

ROOT="$(cd "$(dirname "$0")" && pwd)"

if [ -f "$ROOT/.env" ]; then
  set -a; . "$ROOT/.env"; set +a
  echo "Loaded .env"
else
  echo "No .env found — using interactive defaults (see .env.example)."
fi

ALL="dev-tools sleepless rig-panel"

list() { echo "packages: $ALL"; }

ONLY="$ALL"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --only) ONLY=$(echo "$2" | tr ',' ' '); shift 2 ;;
    --list) list; exit 0 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1 (try --help)"; exit 1 ;;
  esac
done

for pkg in $ONLY; do
  case "$pkg" in
    dev-tools|sleepless|rig-panel) ;;
    *) echo "unknown package: $pkg"; list; exit 1 ;;
  esac
done

for pkg in $ONLY; do
  echo "=== $pkg ==="
  bash "$ROOT/packages/$pkg/install.sh"
done
echo "All requested packages installed."
