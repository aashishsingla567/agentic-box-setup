#!/usr/bin/env bash
# Configurable Linux devbox provisioning. No arguments show a read-only plan.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec /usr/bin/python3 "$ROOT/provision.py" "$@"
