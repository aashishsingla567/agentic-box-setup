# What agentic-box-setup does

`agentic-box-setup` turns an **already installed, supported Linux system** into a configurable environment for remote AI-assisted development. OS selection is an installer handoff plus a provisioning compatibility check. The repo cannot boot a blank machine, install an OS itself, recover unsaved processes, or authenticate new accounts without their supported per-machine flow.

The end-to-end instructions are in [NEW-MACHINE.md](NEW-MACHINE.md). The schema/selection rules are in [CONFIGURATION.md](CONFIGURATION.md). [SETUP-FLOW.html](SETUP-FLOW.html) shows first setup and later boots.

## Capability contract

| Area | Automatic when selected | Still provided/configured by you |
| --- | --- | --- |
| OS | Print official installation guidance; check OS/CPU/Python compatibility | USB creation, OS installer, disk layout/encryption, firmware, drivers, locale/user |
| Base | apt prerequisites; verified user-local Node and PATH hook | Working apt/network/sudo and a real systemd user session |
| Agent tools | Individually install Codex, Claude Code, OpenCode, Cursor agent, agy, T3, Tailscale | Select tools, accept supported account flows, authenticate each needed provider |
| Desktop tools | Optional T3 desktop, Cursor editor, Antigravity app/IDE, Rig Panel | Choose an OS desktop and select those tools; `desktop=true` alone does not select all tools |
| Proxy | Pin/check/download CLIProxyAPI; create private fresh key/config; loopback user service | Authenticate its accounts; configure desired adapters to use it; review any unknown pre-existing runtime |
| T3 | Supported service launcher, port/PATH/proxy environment, local API readiness ordering and optional server limits | Provider/model setup, T3 Connect enrollment and external pairing/access test |
| Remote access | Install Tailscale; optional explicit join; preserve Running identities; opt-in root-backed SSH keys | Persistent OS network, public key entry, host fingerprint check, firewall/recovery path and OIDC enrollment |
| Home/startup | Enroll supported home identity; guard app starts; monitor mounts/user manager; reconcile workspace; linger; ordered shutdown | OS disk unlock, one remote eCryptfs unlock per boot where applicable; controlled boot acceptance |
| Health | Local `locked/starting/ready/degraded` status, model-list/UI/network/tailnet/tunnel-edge checks, expiry warning, bounded private logs | External authenticated UI check and response to expiry; no external alerts or paid generation probes |
| Storage | Read-only accounting/categories/large-file reports, adaptive advisory budgets, pressure checks, scheduled idle opportunities | Review actual workload/data; select any cleanup; configure backups/snapshot retention separately |
| Resource fairness | Optional native T3 agent slice CPU/I/O settings; bounded new command wrappers; optional T3 server cgroup settings | Choose safe limits from measured workload; memory-heavy agents/builds still need capacity planning |
| Power | Optional inhibitor CLI or selected persistent logind/desktop settings | Hardware/firmware behavior and desktop AC-suspend review; no default persistent power change |
| Preservation | Refuse unknown/modified managed-file overwrite; retain original startup rollback baseline; preserve data/identities | Verified off-machine backup/restore; select upgrades and manually recover non-managed workloads |

The default schema is not the same as an all-components production deployment. In particular, startup, system-level storage policy, agent fairness and persistent power policy are opt-in. Provider registration and Connect pairing are never inferred from this machine's private settings.

## What a fresh apply actually selects

Use the wizard's `headless-heavy` profile for the normal remote-agent path. It installs base prerequisites/Node, Codex/Claude Code/OpenCode/T3/Tailscale CLI, proxy/T3 runtime and user storage timers. It permits starting fresh services, keeps cleanup off and omits desktop apps. It does not enroll SSH keys, join a tailnet, authenticate model providers, configure Connect or enable persistent power policy by itself.

The smaller [new-headless example](../config/examples/new-headless.json) explicitly selects four CLIs and omits OpenCode. The `desktop` profile adds Rig Panel and enables desktop assets for tools actually selected; its default storage profile is balanced. The `minimal` profile omits runtime/timers. The `existing-machine` profile installs storage only.

`./install.sh` without arguments is a read-only plan. `--apply` executes selected stages. `--stage verify` runs diagnostic checks without an apply flag; `--plan` previews those too. The bare default schema has `runtime.start_services=false`, so configuring a missing T3 service stops with an explanation until its supported start-on-install behavior is explicitly allowed. Use a reviewed profile/config rather than assuming every invocation does a full setup.

## Subsequent boot behavior

After per-machine authentication and opt-in startup setup:

1. Firmware and the OS boot; the OS completes any root-disk unlock.
2. The configured system network, Tailscale and SSH start according to their OS/service policy. This repo does not change Headscale server policy or create a new control server.
3. On eCryptfs, the root guard protects locked home and root-backed SSH accepts the staged public key. The user runs `agentic-startup unlock` once. On an ordinary or OS-unlocked supported filesystem, identity verification can proceed without an eCryptfs prompt.
4. The monitor polls every 15 seconds by default, reloads the user manager on the relevant transition and starts the workspace target. Missing services start; healthy services are retained. T3 waits for its local proxy API gate.
5. T3 retries its configured remote connection through its supported launcher. Timers/health run when the workspace is available. A MacBook must reconnect its SSH/client session; this repo does not configure the client to reconnect.
6. The graphical login screen can stay displayed. Lingering workspace services do not require a desktop session and the configured eCryptfs home stays mounted after SSH logout.

For a new encrypted root without independently qualified auto-unlock, step 1 still needs the OS passphrase before SSH exists. The current eCryptfs machine instead boots SSH first and needs one remote home unlock. Neither is described as completely unattended encrypted startup.

## Budgets, cleanup and maintenance

Budgets are allocation envelopes and warning thresholds, not storage quotas. The utility adapts them to the filesystem and generates workload guidance from CPU/RAM. Default targets leave 20% free and warn critically below 10%. Installing this code does not free enough space to meet those targets, delete projects, expand a disk, or maximize agent count automatically.

The user check timer runs hourly; a daily 04:00+jitter opportunity performs a deep audit only when idle and the previous audit is at least seven days old; weekly maintenance is Sunday 05:00+jitter. Functional readiness is checked every five minutes by default. System audit/journald/writeback policy is a separate selection. Cleanup starts disabled. Opted-in cleanup is limited to the pinned utility's old allowlisted caches/logs and busy checks; repositories, dependencies, agent state, databases, volumes, downloads/personal data and recovery snapshots are outside blanket deletion.

T3 server limits and native agent scopes are different cgroups. Zero server overrides preserve native/admin settings. Optional agent fairness uses roughly all but one CPU thread by default, while retaining T3's native aggregate memory limits. `devbox-run` limits only newly launched commands that opt into it; it does not retroactively cap every process. More idle conversation tabs do not imply more concurrent heavy builds fit.

## State and boundaries

Nonsecret selections live in private host JSON; schema defaults/profiles are in Git. Per-machine provider credentials and runtime data remain private, usually under the user's config/state directories. Root startup code/config/logs live outside encrypted home so the unlock interface can function while home is locked. Storage reports are private. The repo is not an account/credential sync or backup service.

An enabled service is not full readiness. Proxy/T3 installation probes check commands/files. Startup readiness additionally requires an available home, nonempty authenticated local model list, T3 HTTP response, reachable network/control endpoint, healthy online tailnet and connected T3 tunnel edge. The external authenticated browser remains explicitly unverified until a human tests it. A machine intentionally using only SSH access can work while the missing Connect tunnel is reported degraded.

Reboot preserves saved data, conversations and persistent volume contents. It ends shell/SSH sessions and running processes. Eligible T3 continuation is application-owned, not process resurrection or blind command replay. Manual Docker/PostgreSQL/BuildKit and `/tmp` data are not made durable or permanently managed by this repo.

This is not a universal Linux image, complete unattended encrypted boot, automatic fleet updater, container/database platform, whole-machine uninstaller or disaster-recovery system. Current support is Debian-family/systemd with Python 3.10+, one non-root managed workspace account and supported local home mount layouts. New distro/hardware boot acceptance remains to be measured; see [VALIDATION.md](VALIDATION.md) and [REVIEW.md](REVIEW.md).
