# Shared helpers for dev-tools install scripts.
have() { command -v "$1" >/dev/null 2>&1; }

need_node() {
  if ! have node; then
    echo "node >= 22.16 (or >= 24.10) is required — install nvm/node first." >&2
    return 1
  fi
}

fetch_to_file() {
  # $1 = url, $2 = dest — always via file, never curl|bash (compressed
  # responses have broken piped installs before).
  curl -fsSL "$1" -o "$2"
}
