#!/bin/bash
# Tailscale (official apt repo via upstream installer).
# Non-interactive join when TAILSCALE_AUTHKEY is set (see .env.example).
set -u
curl -fsSL https://tailscale.com/install.sh | sh
tailscale --version | head -1
if [ -n "${TAILSCALE_AUTHKEY:-}" ]; then
  sudo tailscale up --auth-key "$TAILSCALE_AUTHKEY"
else
  echo "Next: run 'sudo tailscale up' and log in."
fi
