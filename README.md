# agentic-box-setup

Monorepo that turns a fresh Linux box (Mint / Ubuntu) into a **remote
agentic dev machine** — the exact setup this was built on.

```
packages/
  dev-tools/   opencode · codex · claude · cursor · antigravity · t3 · tailscale
  sleepless/   24/7 lid-closed power (logind + DE) + `sleepless` inhibitor
  rig-panel/   zenity control panel for all of the above
```

## Quickstart (new machine)

```bash
git clone <this-repo> && cd agentic-box-setup
cp .env.example .env   # optional; fill TAILSCALE_AUTHKEY for zero-touch join
./install.sh
```

Partial installs: `./install.sh --only sleepless,rig-panel`

Then authenticate the agent providers (interactive, by design):
`codex login`, `claude auth login`, `agent login`, `opencode auth login`.

## Secrets model (public-repo safe)

- Nothing secret lives in git. Runtime secrets go in `.env` (gitignored).
- `.env.example` documents every supported variable; unset = skipped with an
  interactive fallback.
- Only secret currently usable headlessly: `TAILSCALE_AUTHKEY` (ephemeral,
  reusable key from the Tailscale admin console). Provider logins stay
  interactive on purpose — OAuth device flows can't and shouldn't be baked in.
