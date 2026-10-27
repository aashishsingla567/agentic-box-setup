#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ $(id -u) != 0 ]] || { echo 'Run as the workspace user, not root.' >&2; exit 1; }
exec sudo /usr/bin/python3 "$PKG/install.py" --user "$(id -un)" --source "$PKG"
