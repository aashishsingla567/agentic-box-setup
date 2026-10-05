# dev-tools

One script per tool in `tools/` (each runs standalone), plus `install.sh`
for the full set. Versions are pinned at the top of each script — bump the
`CURSOR_VERSION` / `ANTIGRAVITY_*` vars as new stables land; t3code and the
opencode/codex/claude installers track latest automatically.

| script | installs |
|---|---|
| `opencode.sh` | opencode v1 stable |
| `codex.sh` | OpenAI Codex CLI (needs node) |
| `claude-code.sh` | Claude Code native |
| `cursor.sh` | Cursor editor .deb + `agent` CLI |
| `antigravity.sh` | agy CLI + app + IDE in /opt |
| `t3code.sh` | `t3` CLI + desktop .deb |
| `tailscale.sh` | Tailscale + optional key-based join |
