# Configuration and scopes

The complete default schema is [config/defaults.json](../config/defaults.json). Unknown keys, malformed types, invalid ports, unsupported OS/architecture and empty stages fail before installers run. JSON contains nonsecret settings only. Private host overrides matching `*.local.json` are gitignored. The wizard creates its output with mode 0600 and refuses to overwrite an existing file.

Resolution: defaults, optional `--profile`, repeatable `--config` files, repeatable `--set key=value`. Later values win. Objects merge, arrays replace. JSON literals preserve numbers/booleans; unquoted strings such as `heavy` are accepted. `--show-config` prints the fully resolved nonsecret configuration without reading `.env` or running installers.

```bash
./install.sh --config config/examples/team.json --config machine.local.json --show-config
./install.sh --only runtime.t3 --set runtime.t3_port=4773 --plan
./install.sh --only storage.audit --set 'storage.budgets_gib.project-dependencies=60' --apply
```

| Key | Meaning |
| --- | --- |
| `version` | Schema version; currently 1 |
| `machine.os` | `auto`, `linuxmint`, `ubuntu`, `debian`; an explicit OS must match the installed host before apply |
| `machine.role` | `headless` or `desktop`; descriptive role, use a profile or `dev-tools.desktop` to select desktop software |
| `packages` | Default package selection; does not uninstall omitted packages |
| `PACKAGE.components` | Default component list for that package |
| `base.node_version` | Major line (default `24`) or exact `X.Y.Z`; Node 22.16+, 24.10+ or newer |
| `dev-tools.desktop` | Include Cursor, Antigravity and T3 desktop apps when those tools are selected; default false |
| `dev-tools.versions.codex` | npm version/tag, default `latest` |
| `dev-tools.versions.cursor` | Cursor desktop version |
| `dev-tools.versions.antigravity_app`, `antigravity_app_build`, `antigravity_ide`, `antigravity_ide_build` | Antigravity desktop asset version/build pairs |
| `runtime.proxy_version` | Exact CLIProxyAPI release, verified against the upstream SHA-256 asset digest |
| `runtime.proxy_port`, `runtime.t3_port` | Distinct unprivileged ports, default 8317 and 3773 |
| `runtime.start_services` | Allow starting services; a missing T3 service requires true because `t3 service install` starts it |
| `runtime.limits.memory_high_gib`, `memory_max_gib`, `tasks_max`, `cpu_quota_percent` | Optional systemd limits on the T3 server service. Zero omits our override and retains native/admin settings. Agent scopes are separate. |
| `startup.home_policy` | `auto`, `ecryptfs`, `mounted`; see mount rules below |
| `startup.poll_interval` | Home/user-manager poll seconds, 5–300, default 15 |
| `startup.health_interval` | Functional status interval seconds, 30–3600, default 300 |
| `startup.keep_unlocked` | Disable eCryptfs logout auto-unmount, with backup. Required for a persistent eCryptfs workspace. |
| `startup.authorized_keys` | Existing public authorization file, default `~/.ssh/authorized_keys`; complete entries/restrictions are copied unchanged |
| `storage.profile` | Adaptive workload guidance: `balanced` or `heavy` |
| `storage.timers` | Install/enable user audit/check/maintenance timers, or disable these managed timers when false |
| `storage.cleanup` | Default false. Selected audit setup explicitly updates the utility's cleanup switch. True permits only its allowlisted expired caches/logs, subject to busy checks. |
| `storage.budgets_gib` | Overrides to selected allocation envelopes; omitted categories keep adaptive defaults. See storage guide for category names. These are warnings, not deletion quotas. |
| `storage.agent_limits.cpu_quota_percent` | Aggregate native T3 agent slice CPU quota; zero computes `(online CPU threads − 1) × 100`, minimum 100 |
| `storage.agent_limits.cpu_weight`, `io_weight` | Native T3 agent slice fairness, defaults 80; range 1–10000. Memory limits remain T3-managed. |
| `sleepless.mode` | `unchanged`, `always-on`, `normal`; power changes require selecting `sleepless.power` |
| `network.join` | Explicitly allow joining a tailnet; default false. A Running identity is preserved. Other existing states require manual recovery. |
| `network.login_server` | Optional HTTPS Headscale origin; empty uses Tailscale's default on initial enrollment |

`--only base,storage.audit` selects packages/components; `--tools codex,t3code` is shorthand for individual dev-tool selectors. Component selection replaces the default package list for this invocation. Prerequisites are not silently expanded: e.g. a Codex-only installation needs Node already available; `storage.limits` needs a native T3 agent slice, created by starting an agent.

Stages execute globally in order: install all selected binaries, configure selected services/policy, then verify selected components. `--stage install` limits work to binaries; `--stage configure` applies service/configuration only; `--stage verify` runs read-only diagnostic checks without `--apply`. Add `--plan` to preview even verification. Other stages require `--apply`. Some packages have no install stage because their scope is configuration; an empty stage is rejected.

Verification distinguishes presence/configuration from functional readiness. Runtime verification checks installed files; startup status probes local apps, network, tailnet expiry and T3 tunnel edge health. Locked/degraded startup or a storage-budget warning is reported as a condition, without restarting applications or making the provisioning command replay installation. An authenticated connection from another device remains explicitly unverified until tested there.

Startup components share one installer transaction. Adding components preserves the original file backups and earlier selected components. SSH-only does not require runtime units, home-only does not install applications, and health-only reports missing apps. `workspace` always includes mount guards. Partial startup apply reconciles the retained components as well; changed root monitor code/config may restart that lightweight monitor while healthy application services remain running.

`auto` detects the distro eCryptfs metadata first. `ecryptfs` supports the established Ubuntu/Mint `/home/.ecryptfs/USER` layout and verifies the decrypted mount/backing inode identity. `mounted` enrolls a local block filesystem UUID, mount target/root/type and home inode/owner. It supports an ordinary home on root or an OS-unlocked LUKS/ext4 filesystem. A substituted/nested mount is rejected, and an existing eCryptfs home cannot select `mounted`. Network homes, containers/overlay filesystems, Btrfs subvolume layouts and other unlock mechanisms need separately tested adapters; no generic fallback is attempted.

Most scoped adapters require a working systemd user session. Run the frontend as the intended non-root workspace user. Selected system actions use sudo. File hash stamps permit updates to files generated by this setup; unmanaged or locally modified files are preserved and the scope stops. Review existing configurations before adopting them; do not delete arbitrary files to force setup through. Applying changed ports/limits reloads unit definitions and starts missing services; restart an already-running service only after saving its work and deciding to activate that change.

Profiles:

| Profile | Default intent |
| --- | --- |
| `minimal` | Base packages/Node plus Codex and T3 CLI |
| `headless-heavy` | Base, selected CLI tools, runtime, heavy storage guidance; runtime service start permitted |
| `desktop` | Adds desktop apps and Rig Panel; runtime service start permitted |
| `existing-machine` | Storage audit/timers only, heavy guidance, cleanup off |

None enrolls SSH keys, enables unattended decryption, changes Headscale server policy or reinstalls the OS. To extend the provisioner, add a package/component registry entry in `provision.py`, defaults in the schema, and an adapter implementing its stages. Add fixture tests and document OS/architecture prerequisites before claiming support.
