#!/usr/bin/env bash
set -euo pipefail
# Pin the reviewed Linux implementation; never execute a moving branch as root.
REV=623cd64f6692e2bba0cc862dd5b4b56afd3fa049
SOURCE="${DEV_STORAGE_SOURCE:-${XDG_DATA_HOME:-$HOME/.local/share}/agentic-box-setup/sources/dev-storage/$REV}"
if [[ -z ${DEV_STORAGE_SOURCE:-} ]]; then
  if [[ ! -d "$SOURCE/.git" ]]; then
    mkdir -p "$SOURCE"
    git -C "$SOURCE" init -q
    git -C "$SOURCE" remote add origin https://github.com/aashishsingla567/dev-storage.git
  fi
  if ! git -C "$SOURCE" cat-file -e "$REV^{commit}" 2>/dev/null; then
    git -C "$SOURCE" fetch --depth=1 origin "$REV"
  fi
  if [[ -n $(git -C "$SOURCE" status --porcelain) ]]; then
    echo "Source checkout has local changes; preserve them and use DEV_STORAGE_SOURCE explicitly." >&2
    exit 1
  fi
  git -C "$SOURCE" checkout --detach -q "$REV"
fi
[[ -f "$SOURCE/linux/install.sh" ]] || { echo "Linux dev-storage source missing: $SOURCE" >&2; exit 1; }
bash "$SOURCE/linux/install.sh" --profile heavy "$@"
echo "Storage audit installed; cleanup stays disabled unless explicitly enabled."
echo "Run dev-storage audit to capture the baseline. See packages/storage/README.md."
