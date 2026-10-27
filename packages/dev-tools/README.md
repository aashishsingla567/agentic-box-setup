# Development tools

Select an individual CLI with `./install.sh --only dev-tools.codex --apply`, or several with `--tools codex,claude-code,t3code`. Existing Node is required for Codex; select `base` explicitly to provision it. Direct `tools/TOOL.sh` scripts remain usable and stop on failure.

| Tool | Default installation |
| --- | --- |
| `opencode` | Upstream CLI installer |
| `codex` | npm CLI in the user's prefix; version/tag configurable |
| `claude-code` | Upstream native CLI installer |
| `cursor` | Agent CLI; editor .deb only with `dev-tools.desktop=true` |
| `antigravity` | agy CLI; app/IDE only with desktop enabled |
| `t3code` | T3 CLI; desktop .deb only with desktop enabled |
| `tailscale` | System client/daemon; enrollment requires `network.join=true` |

Vendor CLI installers generally track their current release. Cursor/Antigravity desktop assets have configurable version/build pairs; Node, proxy and the storage utility have their own verification/pinning. This is not a fully reproducible offline package mirror. Downloads run from unique temporary directories; inspect upstream installers and pin/review changes when maintaining a stricter fleet. npm uses a user-local prefix from the frontend, never `sudo npm`.

Tailscale preserves a Running identity, routing and control URL. It does not force logout/reauthentication; other existing non-login states need manual recovery. Optional auth keys are passed by a private temporary file, not in process arguments. Provider login remains the tool's own interactive flow. See the new-machine guide before enrolling remote access.
