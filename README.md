# agentic-box-setup

Configurable provisioning for a Linux machine used for remote development and AI agents. Choose a machine profile, a package, an individual tool, or one setting. Plans are read-only; installation requires `--apply`.

Adapters cover Linux Mint, Ubuntu and Debian with systemd and Python 3.10+. Mint/Ubuntu x86_64 is the existing deployment; other supported combinations have planning and fixture coverage, not a completed fresh-OS installation test. [Start from a new OS](docs/NEW-MACHINE.md) or [configure an existing machine](docs/CONFIGURATION.md).

```bash
git clone https://github.com/aashishsingla567/agentic-box-setup.git
cd agentic-box-setup
./install.sh --wizard --output machine.local.json
./install.sh --config machine.local.json --plan
./install.sh --config machine.local.json --apply
```

The wizard chooses OS, profile and packages and saves a private JSON override. It does not install an OS. `--os-guide` provides the official installer handoff. Provider login, T3 Connect enrollment, SSH keys and encrypted-disk recovery remain explicit steps.

Granular use:

```bash
./install.sh --list
./install.sh --profile minimal --plan
./install.sh --only dev-tools.codex --apply                  # existing Node required
./install.sh --only storage.audit --set storage.profile=heavy --apply
./install.sh --only startup.ssh --stage configure --apply    # mounted home + SSH key required
./install.sh --only runtime --stage verify                  # read-only probes
./install.sh --set machine.os=linuxmint --os-guide
./install.sh --config team.json --config host.local.json --set runtime.t3_port=4773 --show-config
```

Configuration precedence is **defaults → profile → config files in order → `--set` in order**. Objects merge; arrays replace. `--only package.component` overrides the package selection without silently installing unrelated components. Dependencies must already exist or be selected explicitly. Selection is additive: excluding something does not uninstall it. Completed actions remain if a later action fails; rerun the failed scope after fixing its prerequisites.

| Package | Components | Purpose |
| --- | --- | --- |
| `base` | `packages`, `node` | apt prerequisites and verified user-local Node |
| `dev-tools` | `opencode`, `codex`, `claude-code`, `cursor`, `antigravity`, `t3code`, `tailscale` | Individual CLIs; optional desktop apps |
| `runtime` | `proxy`, `t3` | Fresh local proxy and supported T3 service launcher |
| `startup` | `ssh`, `home`, `workspace`, `health` | Boot keys, mount safety, reconciliation and local readiness |
| `storage` | `audit`, `system`, `limits` | Adaptive budgets/timers, optional system policy, agent CPU/I/O fairness |
| `sleepless` | `cli`, `power` | On-demand inhibitor and explicit persistent power policy |
| `rig-panel` | `ui` | Optional GTK desktop control panel |

The default selection keeps storage cleanup off and leaves power policy unchanged. `minimal`, `headless-heavy`, `desktop` and `existing-machine` profiles are in [config/profiles](config/profiles). Headless/desktop profiles explicitly permit starting fresh runtime services; startup remains opt-in until runtime, authentication and SSH keys are ready.

Existing repositories, agent conversations, credentials, databases, volumes and recovery snapshots are preserved. Unknown proxy configuration and modified managed files cause an actionable stop instead of being overwritten. Runtime installation never copies this machine's credentials to another host. `.env` accepts only an optional Tailscale auth key; it is never executed as shell code.

Read the [configuration reference](docs/CONFIGURATION.md), [new-machine checklist](docs/NEW-MACHINE.md), [runtime guide](packages/runtime/README.md), [startup/recovery runbook](packages/startup/README.md), and [storage guide](packages/storage/README.md). The current eCryptfs installation needs **one remote home unlock per boot**. Fully automatic encrypted startup remains a separately qualified migration requiring off-machine backup and recovery testing.
