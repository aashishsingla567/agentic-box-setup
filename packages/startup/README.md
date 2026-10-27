# Reliable startup with an encrypted Linux home

This opt-in package integrates an **existing** verified home, CLIProxyAPI,
T3-managed service and systemd user manager. It installs no agent binaries,
creates no OAuth credentials, changes no Headscale policy and stores no
password or encryption key. Linux Mint 21.3 / Python 3.10 / systemd 249 is
the tested baseline. Unified cgroups are used by the existing workload limits.

```bash
./install.sh --only startup --apply
agentic-startup status
agentic-startup status --json
```

Run installation as the workspace user with sudo available. The current
implementation supports one managed, non-root workspace account per host,
a mounted eCryptfs home at its passwd home path, and Ubuntu/Mint's
`/home/.ecryptfs/USERNAME/{.Private,.ecryptfs}` metadata layout. It refuses an
unexpected mount, missing runtime units, missing existing SSH authorized keys,
or conflicting managed files. Fresh machines need the runtime provisioned first.

## What happens on boot

1. Linux, system-wide NetworkManager, Tailscale and SSH start without desktop login.
2. A root-owned guard overlays the locked home with a read-only login surface.
   It exposes only the eCryptfs metadata/backing links needed for the distro's
   unlock helper. The legacy home remains untouched and hidden. SSH's existing
   public keys are copied verbatim, including restrictions, to
   `/etc/ssh/authorized_keys/USERNAME`; the home-based key paths and existing
   password policy remain available.
3. Connect using your existing authorized key. Run `agentic-startup unlock`
   and enter the Linux login password privately in the distro's terminal prompt.
   Password SSH/graphical login can also mount home through PAM.
4. Within 15 seconds of a verified mount, the root monitor reloads the user
   manager and starts `agentic-workspace.target`. Proxy readiness precedes T3;
   T3 recreates its managed cloud connection. Health, renewal and storage timers
   join the same target if already installed.
5. Home stays mounted after SSH logout, until shutdown. Installation backs up
   and removes only the `auto-umount` marker. Automatic mounting, encryption,
   graphical login and critical-battery protection remain unchanged.

This is **one interactive unlock per boot**, not unattended automatic decryption.
The guard is armed for the next locked boot: installation does not insert a
mount below or replace the currently active home. Reconciliation uses mount
identity/inodes and kernel read-only state; a mountpoint existence check alone
would accept the read-only login surface. Application commands have their own
identity guard. The system monitor orders shutdown before home unmounting and
the user manager; user-unit ordering cannot express cross-manager dependencies.

If the decrypted mount disappears, the previously installed read-only layer
prevents fallback writes immediately, and the monitor stops managed workspace
services on its next tick. On the current pre-install boot that lower layer
cannot be inserted safely; until a controlled boot verifies it, only the
application guards and stop-on-loss monitor apply. Do not deliberately unmount
the active home to test this.

## Commands and readiness

```bash
ssh aashish@100.64.0.32        # use your machine's own user/address
agentic-startup unlock        # interactive; never pass passwords as arguments
agentic-startup start         # after unlock; reload and start, never restart
agentic-startup status --json
```

`locked` means the expected encrypted home is unavailable. `starting` means
an application is activating. `ready` means functional local model-list/UI
checks, Internet reachability, Tailscale and the managed tunnel's edge readiness
pass. `degraded` names failed/unverified dependencies or an expiry warning.
The remote authenticated browser/UI path is always explicitly **unverified**:
a connected Cloudflare edge is not proof of an end-to-end external login.
Status returns 0 for ready, 1 for other states, 2 for execution/config errors.

Proxy checks parse the existing credential file without sourcing shell code,
use authenticated `/v1/models`, and never make paid generation requests. Probes
run as the workspace user, not root. T3's loopback UI and its own cloudflared
readiness endpoint are checked; dynamically assigned metrics ports are resolved
from that process's socket inodes. The current control-server URL is used for a
small reachability check. Service PID/process metadata alone does not mean ready.

The monitor checks mounts every 15 seconds, retries a failed user-manager
reconciliation every 30 seconds and reruns functional health checks every five
minutes. It also reconciles after a user-manager invocation change. It never
restarts healthy applications in response to Internet/provider failures.
T3/proxy retain their existing restart policies, launcher, credential sources,
provider continuation rules, resource limits and tunnel configuration.

## State, credentials and rollback

Root-owned code and configuration live outside home in `/usr/local/libexec/`
and `/etc/agentic-startup/`. The command is `/usr/local/bin/agentic-startup`.
Private installer manifests, prior file contents, status snapshots and logs are
under `/var/lib/agentic-startup/USERNAME/` (0700/0600). The manifest backs up only
managed startup/SSH files and the marker; it does not back up credentials,
wrapped encryption keys or databases. Logs rotate at 1 MiB with three backups.
No shell arguments, subprocess dumps, HTTP bodies or secrets are logged.

Reinstallation preserves the original rollback baseline and refuses to replace
managed files changed independently since installation. It does not restart a
running monitor or healthy applications; monitor implementation changes take
full effect on its next start. Core networking services remain enabled on rollback.

```bash
sudo agentic-startup uninstall --user "$USER"
```

Rollback checks all installed hashes first, refuses to overwrite newer work,
disables the managed monitor/guard boot jobs, restores only managed files and
the original logout marker, then reloads SSH/user units. It leaves healthy
application processes, data and boot networking alone. A read-only lower home
layer is intentionally not unmounted automatically; it disappears at shutdown.
Do not stop the guard and manually unmount a live decrypted home as a removal step.
Keep a shell open when restoring the logout marker until your work is saved.

## Remaining availability limits

The existing browser/OIDC tailnet-renewal service is retained. Its state lives
inside encrypted home. Status warns below 24 hours of node-key lifetime; if
that identity expires before unlocking, use LAN/physical access and the existing
supported authentication flow. A short-lived personal identity cannot be made
permanent with local startup settings. No registration/logout/force-reauth or
control-plane change is performed. Local status/logs are the only alert delivery.

Saved repositories, worktrees, histories, databases and credentials persist.
Live shell commands, builds, previews and database transactions do not survive
reboot. T3 may continue eligible runs with a new turn; this is not exactly-once
execution or restoration of an OS process. Inspect results before retrying.
Temporary verification Docker/PostgreSQL/BuildKit under `/tmp` remain manually
recoverable workloads; this installer never promotes them to boot services.

The later zero-login milestone requires verified off-machine backups before
replacing eCryptfs with LUKS2, qualifying TPM/verified boot and testing recovery.
This machine has TPM 2.0, but Secure Boot is disabled and its systemd TPM backend
is absent. No TPM enrollment, firmware, partition, filesystem or OS change is
part of this package. Linux Mint 22.3 is supported until April 2029.

## Validation and controlled reboot

```bash
python3 -m unittest discover -s packages/startup/tests -v
bash -n install.sh packages/startup/install.sh
# Real mount/keyring test: disposable UID and data, private mount namespace.
sudo unshare --mount --propagation private python3 packages/startup/tests/mount_namespace.py
```

The integration test verifies that a disposable account cannot write while
locked, the real setuid eCryptfs mount helper unlocks on top of the read-only
surface, the correct mount is recognized, relock exposes the read-only layer,
and original legacy data is preserved. It never uses the real user's keys/home.
It requires Linux eCryptfs, ecryptfs-utils, keyutils, util-linux and root; CI runs
the unprivileged accounting/health/recovery/rollback tests on Python 3.10/3.12.

Before reboot: validate sshd and units, open a **second SSH connection using the
existing remote client/key**, save active work, and confirm an alternative LAN
or physical path. Installation does not reboot or log out the current desktop.
The installing agent cannot prove access from a remote client whose private key
is not on this machine. Reboot remains a separate acceptance step until that
connection and fallback are confirmed. Under working networking, measure SSH
availability against three minutes from boot, and proxy/T3/remote connection
against five minutes after unlock. Test logout and Internet recovery without
forcefully disconnecting the only remote access path.

## Configurable provisioning

The root frontend now plans by default; use `--apply` to install. See [the configuration reference](../../docs/CONFIGURATION.md) for partial `startup.ssh`, `startup.home`, `startup.workspace` and `startup.health` scopes and configurable ports/check intervals. Adding a component retains earlier startup components and rollback baselines. SSH-only needs no runtime; workspace requires installed runtime units and always installs mount guards. Health-only reports missing dependencies without creating applications.

The detailed eCryptfs procedure above remains the existing Mint deployment. New ordinary homes on local UUID-backed filesystems, including OS-unlocked LUKS/ext4, may use `startup.home_policy=mounted` (or auto-detection). Enrollment checks UUID-backed device, mount root/target/type, home inode and owner, and rejects unexpected nested mounts. It does not implement disk unlock; restore/unlock through the OS before `agentic-startup start`. eCryptfs metadata prevents selecting mounted policy as a shortcut. Btrfs, network and overlay layouts need additional adapters/testing.

The configurable frontend and new mount policy have fixture coverage. No fresh distro deployment or controlled reboot has been measured as part of that extension. Do not treat those tests as a remote-access or reboot acceptance result. An upgraded root monitor may restart to reload code/config, while existing healthy proxy/T3 processes are preserved. SSH, Tailscale and persistent networking must be installed/configured separately on a fresh host; their identity/routing are not replaced by startup setup.
