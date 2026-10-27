#!/bin/bash
# Install without replacing an existing identity or changing its routes.
set -euo pipefail
. "$(dirname "$0")/common.sh"
if ! have tailscale; then
  fetch_to_file https://tailscale.com/install.sh "$AGENTIC_TMP/tailscale.sh"
  sh "$AGENTIC_TMP/tailscale.sh"
fi
tailscale --version
sudo systemctl enable --now tailscaled.service
if [[ ${AGENTIC_TAILSCALE_JOIN:-false} != true ]]; then
  echo "Installed. Joining is explicit: network.join=true or sudo tailscale up."
  exit 0
fi
state=$(tailscale status --json | python3 -c 'import sys,json; print(json.load(sys.stdin).get("BackendState",""))')
if [[ $state == Running ]]; then
  echo "Existing tailnet identity preserved."
  exit 0
fi
if [[ $state != NeedsLogin && $state != NoState ]]; then
  echo "Existing identity needs attention; inspect tailscale status and recover it explicitly." >&2
  exit 1
fi
args=()
[[ -z ${TAILSCALE_LOGIN_SERVER:-} ]] || args+=(--login-server "$TAILSCALE_LOGIN_SERVER")
if [[ -n ${TAILSCALE_AUTHKEY:-} ]]; then
  umask 077
  printf '%s' "$TAILSCALE_AUTHKEY" > "$AGENTIC_TMP/authkey"
  sudo tailscale up "${args[@]}" --auth-key="file:$AGENTIC_TMP/authkey"
else
  sudo tailscale up "${args[@]}"
fi
