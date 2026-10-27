# Shared helpers. Each installer has a private temporary directory.
have() { command -v "$1" >/dev/null 2>&1; }
need_node() {
  have node || { echo "Install base.node first." >&2; return 1; }
  node -e 'const [a,b]=process.versions.node.split(".").map(Number); if (!((a===22&&b>=16)||(a===24&&b>=10)||a>24)) process.exit(1)' || {
    echo "Node 22.16+, 24.10+ or newer is required." >&2; return 1;
  }
}
fetch_to_file() { curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 "$1" -o "$2"; }
AGENTIC_TMP=$(mktemp -d -t agentic-tool.XXXXXXXX)
trap 'rm -rf -- "$AGENTIC_TMP"' EXIT
