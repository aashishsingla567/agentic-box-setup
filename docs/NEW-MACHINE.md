# Fresh machine: OS installation to remote agent work

This is the complete setup runbook for a new physical Linux machine. Commands in this guide are for the **new machine** unless marked **MacBook/client**. They are not instructions to reinstall the current devbox.

The repository is a post-install provisioner. You install the OS with its normal installer; this repo then installs selected tools, configures services, schedules storage checks, and optionally manages workspace startup. It does not create a bootable OS image, partition disks, configure firmware, or make encrypted disks unlock automatically. See [capabilities and boundaries](CAPABILITIES.md) for the exact contract and [the setup/boot diagram](SETUP-FLOW.html) for the sequence.

## 1. Decide the OS and boot policy

| Choice | Use it for | Provisioning support |
| --- | --- | --- |
| Linux Mint 22.3 Cinnamon | A desktop devbox that also works remotely | Recommended continuation of the Mint setup; default ext4 filesystem |
| Ubuntu 24.04 LTS desktop/server | Desktop use or a machine managed primarily over SSH | Debian-family adapters; use a systemd user session |
| Supported Debian with Python 3.10+; Debian 12 or newer | A minimal server you configure explicitly | Debian-family adapters; systemd and sudo are required |

The existing deployment is Mint 21.3 on x86_64. New-distro and aarch64 paths have planning/fixture coverage, not a completed installation test on each platform. CLI adapters accept x86_64/aarch64; selected desktop assets require x86_64. `machine.os` checks the installed distribution; changing it does not convert one OS into another. `machine.role=headless` is descriptive and does not remove a desktop you installed.

Choose encryption before installing:

| Storage policy | What happens at power-on | Remote access implication |
| --- | --- | --- |
| Ordinary unencrypted ext4 root/home | OS can mount storage without a passphrase | Services can start without desktop login after startup setup; data has no disk encryption at rest |
| New LUKS2-encrypted root/work data | The OS normally asks for a disk passphrase during early boot | SSH cannot start until the OS disk has been unlocked; this repo supplies no pre-boot remote unlock |
| Existing Ubuntu/Mint eCryptfs home | OS and root services boot while home stays locked | Root-backed SSH works after OS/network boot; run `agentic-startup unlock` once per boot |

For a new encrypted installation, prefer the distro-supported LUKS2 route with independently stored recovery material. Do not create a new eCryptfs home merely to match the old machine. TPM-backed automatic unlock remains a separate project requiring verified off-machine backups, recovery tests, and qualification of firmware/verified boot/kernel/initramfs/update behavior. A TPM being present or Secure Boot being enabled alone is insufficient. No password, plaintext keyfile, or custom secret-storage workaround is installed here.

Select a non-root workspace username and a distinct hostname. Have Internet access for installation, an authorized SSH client, and a way to reach the machine locally or through a physical/KVM console if remote access fails. For planning, the existing four-thread/16 GiB machine is a useful small-host reference; RAM and active builds determine capacity more than the number of open conversations. The provisioner does not promise an unlimited number of running agents.

## 2. Download, verify and write the installation USB

Use official installation media and instructions:

- Mint: [releases](https://linuxmint.com/download_all.php), [installation documentation](https://linuxmint.com/documentation.php).
- Ubuntu: [downloads](https://ubuntu.com/download), [desktop installation](https://ubuntu.com/tutorials/install-ubuntu-desktop), [server installation](https://ubuntu.com/tutorials/install-ubuntu-server).
- Debian: [downloads](https://www.debian.org/distrib/), [installation manual](https://www.debian.org/releases/stable/installmanual).

Download the intended release and architecture. Follow the distribution's checksum **and signature** verification instructions; a checksum copied from the same untrusted download is not an independent authenticity check. On a MacBook, the checksum command is `shasum -a 256 /path/to/downloaded.iso`; compare it with the authenticated published checksum. Follow the vendor's GPG instructions to authenticate the checksum file.

Use an image writer such as balenaEtcher on the MacBook, or the distro's USB image writer on Linux. Select the downloaded ISO and the intended USB device, then write and verify it. Writing the image erases that USB device. No disk-writing command is provided by this repo.

If the destination machine has any existing work, verify a separate backup/restore path before using an erase-disk installation option. The current devbox's encryption migration remains deferred until off-machine restore capacity exists.

## 3. Install the OS using its installer

1. Connect the machine to AC power and preferably Ethernet. Insert the USB, select its UEFI entry in the firmware boot menu, and start the live environment/installer.
2. Check that the live environment can use the storage, keyboard/display and network. Start the normal OS installer.
3. Choose language, keyboard, timezone and the intended desktop/server installation. Select updates/drivers/codecs according to the distribution's instructions and hardware.
4. For a genuinely blank destination disk, select the intended disk and the distro's normal install/erase option. Use its supported encrypted-storage/LVM options if choosing LUKS2. Installer labels differ by release; verify the disk and encryption summary before committing. Disk changes are performed by you in that installer, never by this repository.
5. Create the chosen non-root sudo user and hostname. Set its login password. For an encrypted install, keep disk recovery material independently recoverable; do not assume the Linux login password and the disk unlock are the same operation.
6. Keep normal graphical login on a desktop. Desktop autologin is unnecessary for workspace services. Install the bootloader through the OS installer, finish, remove the USB when prompted, and boot from the installed disk.
7. On an encrypted root installation, verify that you can unlock it at boot and log in. `lsblk -f` shows the disk layout; an administrator can use `cryptsetup luksDump` against the identified LUKS partition to check its format version. Do not run formatting/enrollment commands against an existing installation as part of this runbook.

Use the OS's update tools to finish normal security/driver updates. If they require a reboot, do that now, before starting development work. Firmware behavior after AC power loss, BIOS wake settings, locale, Wi-Fi credentials and disk encryption are OS/hardware configuration, not repo settings.

## 4. Make network access independent of desktop login

On Mint/Ubuntu desktop, edit the intended NetworkManager connection and make it available to all users. Save required Wi-Fi secrets in a system connection rather than only in the user's desktop keyring. Use the GUI's normal password prompt; do not put Wi-Fi passwords in this repo or shell history. Ethernet is simpler when available.

On Ubuntu Server/Debian, use the installed network stack's normal NetworkManager, Netplan or networkd configuration. Do not install a second network manager just to follow a Mint-specific command. Confirm the connection will come up at boot, including DNS and an accurate system clock. The startup installer preserves the network stack's existing policy; it does not enable or rewrite an arbitrary network service.

As the workspace user, bootstrap prerequisites:

```bash
sudo apt-get update
sudo apt-get install -y git python3 ca-certificates curl openssh-server libpam-systemd
sudo systemctl enable --now ssh.service
python3 --version
systemctl --user status
```

Python must be 3.10+. If the user manager is unavailable, fix the normal PAM/systemd login session, log out/in if needed while retaining console access, and retry. Do not run the frontend or T3 with sudo. Individual system changes use sudo themselves.

At this point SSH may be usable over LAN once keys are added, but provider tools, proxy, T3 and workspace orchestration are not installed yet.

## 5. Clone, choose a profile, and inspect the plan

```bash
git clone https://github.com/aashishsingla567/agentic-box-setup.git
cd agentic-box-setup
./install.sh --wizard --output machine.local.json
./install.sh --config machine.local.json --show-config
./install.sh --config machine.local.json --plan
```

The wizard asks for the target OS, a profile and an optional package list. Choose the OS you just installed, then `headless-heavy` for a remote agent machine or `desktop` for optional desktop apps. It saves a 0600, gitignored JSON override and installs nothing. Inspect/edit that file before applying.

| Profile | What its package selection installs/configures |
| --- | --- |
| `minimal` | Base apt prerequisites, user-local Node, Codex and T3 CLI; no runtime services or storage timers |
| `headless-heavy` | Base, Codex/Claude Code/OpenCode/T3/Tailscale CLIs, proxy/T3 runtime, heavy storage guidance and user timers; permits starting fresh services |
| `desktop` | The default CLI selection plus T3 desktop app and Rig Panel; desktop assets for Cursor/Antigravity are installed only if those tools are also selected; permits starting fresh services |
| `existing-machine` | Storage audit utility/timers only, heavy guidance, cleanup off |

Startup orchestration and persistent power changes are deliberately absent from these initial profiles. The desktop profile inherits the balanced storage policy; set `storage.profile=heavy` explicitly if that is the desired workload.

For a smaller fixed starting configuration, copy [new-headless.json](../config/examples/new-headless.json) to `machine.local.json` instead of using the wizard. That example selects Codex, Claude Code, T3 and Tailscale; it omits OpenCode and desktop apps. Change `machine.os` for Ubuntu/Debian. The [configuration reference](CONFIGURATION.md) lists every supported setting.

A plan prints selected actions and rejects unsupported hosts/settings before installation. It does not download tools, change services or prove that later account authentication will succeed. No arguments also means plan-only. Configuration precedence is defaults → profile → config files in order → individual `--set` overrides. One-off `--set` values apply only to that invocation; keep the desired nonsecret settings in your machine config for future rebuilds.

## 6. Apply the selected tools and runtime

```bash
./install.sh --config machine.local.json --apply
. "$HOME/.config/agentic-box/env.sh"
```

The remaining full workflow assumes `headless-heavy` or the `new-headless` example, including base/runtime/storage. With `minimal` or a custom partial selection, install missing prerequisites/components explicitly before following the service steps.

Run from the repo as the workspace user. Expected work for `headless-heavy`:

1. apt installs selected prerequisites. Node is downloaded from its official distribution, SHA-256 checked, staged and installed under the user's managed prefix. Existing system Node is retained.
2. Selected tool installers run. Codex uses user-local npm; other CLIs use their upstream installers. Most vendor CLIs track their current release, so this is not an offline or fully version-locked fleet image.
3. The pinned CLIProxyAPI release is SHA-256 checked and installed. Setup creates a fresh private local API key/config/auth directory, binds the proxy to `127.0.0.1:8317`, enables its user service, and starts it when allowed.
4. T3 uses `t3 service install` for a missing service. Its supported installer starts the service, so `runtime.start_services=true` is required; headless/desktop profiles set it. Our drop-ins set its port (default 3773), tool PATH, proxy environment, local readiness ordering and optional server limits. They do not register providers/models or create a T3 Connect identity.
5. The storage utility gets adaptive budgets and its selected check/audit/maintenance timers. Cleanup is false. Omitted packages are not removed.
6. Verification checks installed commands/files and reports storage conditions. Startup functional readiness is available after the separate startup phase.

An authenticated local proxy API response can contain zero models; the local startup gate permits this so T3 onboarding works without a provider account. A later `ready` result requires a nonempty model list and the remaining readiness dependencies. A running service is not proof of usable provider authentication.

Inspect before proceeding:

```bash
systemctl --user status cli-proxy-api.service t3code.service
./install.sh --config machine.local.json --only runtime --stage verify
systemctl --user list-timers --all
ss -ltn
```

Only the proxy loopback binding is set by this repo. T3's bind address otherwise follows the installed T3 release/settings; inspect it before exposing the host to other networks. Use T3 Connect or an SSH tunnel rather than forwarding app/proxy ports on the router. A loopback-only T3 policy can be added through a user-owned systemd drop-in setting `T3CODE_HOST=127.0.0.1`, followed by a deliberate service restart while there is no active work. This is a local service setting, not a Headscale change.

If a scope fails, already completed scopes remain installed. Read the error, fix its prerequisite, then rerun that scope. Do not delete an existing proxy config, credential source, service or repository merely to force installation through. Unknown configs and modified managed files are intentionally preserved.

## 7. Authenticate providers and configure T3

Each machine needs its own supported logins. Select only the CLIs you actually installed. Use their interactive login flow; consult their `--help` if its syntax changes with an upstream release. Installing a CLI does not authenticate it.

Authenticate the local proxy separately. These examples match the pinned CLIProxyAPI release; choose only the account you intend to use:

```bash
cli-proxy-api -help
cli-proxy-api -config "$HOME/.config/cli-proxy-api/config.yaml" -codex-device-login
# Alternative provider example:
cli-proxy-api -config "$HOME/.config/cli-proxy-api/config.yaml" -claude-login
```

For a headless OAuth flow, use the release's supported device/no-browser/callback procedure. Follow its private prompt; callbacks may require an SSH tunnel. Provider policy/account access still applies. Do not paste account tokens or pairing output into a public issue, this repo, or an agent conversation.

Open T3 locally at its configured port, or from a client through SSH once remote keys/network are ready. In T3, select authenticated native CLI providers and create one test conversation. If you want a provider adapter to use the local proxy, configure that adapter through its supported settings: the endpoint is `http://127.0.0.1:8317/v1`, the credential source is the private `CLIPROXY_API_KEY` in `~/.config/environment.d/cliproxy.conf`, and models depend on the accounts authenticated to the proxy. The exported variable alone does **not** wire every T3 provider or CLI to that endpoint. Adapter configuration is per T3/provider version; this repo does not copy the current devbox's provider settings.

Use `t3 connect` and follow its current enrollment flow to configure T3 Connect on this machine. Use the resulting connection in the MacBook/client and prove you can open the authenticated UI. Keep pairing/connection secrets private. This step establishes the cloud connection; enabling a systemd service alone does not establish it. If you choose SSH-only access instead, T3 can still be usable, but this repo's Connect-aware readiness remains degraded/unverified for the absent tunnel.

## 8. Enroll Tailscale/Headscale and the MacBook SSH key

For Tailscale, run its normal interactive enrollment. For an existing Headscale deployment, use the existing server origin; do not set up or change the control server here:

```bash
sudo tailscale up
# Use this instead for your existing Headscale control server:
# sudo tailscale up --login-server=https://YOUR-CONTROL-HOST

tailscale status
tailscale ip -4
```

Choose **one** enrollment command appropriate to your tailnet. Browser/OIDC authentication is per machine. Alternatively, select `network.join=true` for the Tailscale install scope; an optional auth key belongs only in a private `.env`/environment, not JSON or Git. Already Running identities are retained, not logged out or reset. Do not copy another machine's `tailscaled` state or SSH host private keys into this new machine.

On the **MacBook/client**, use the intended existing SSH identity. Copy only its **public** authorization entry to the new machine through a trusted local/LAN channel. If it carries restrictions, preserve the whole entry. Verify the new machine's SSH host fingerprint from its console before trusting the first connection.

On the **new machine**, prepare `~/.ssh` mode 0700 and `~/.ssh/authorized_keys` mode 0600. Add the public entry without overwriting unrelated existing entries. On a genuinely fresh account, `install -d -m 700 ~/.ssh`, then create/edit `authorized_keys` with `umask 077`. Keep private keys on the client.

If a firewall is already active, review its policy and allow SSH on the intended LAN/tailnet interface. Tailscale uses `tailscale0`; use your OS firewall's supported rules. This repo does not disable the firewall or add a broad public SSH/app-port exposure.

On the **MacBook/client**, replacing the username/address with this machine's values:

```bash
ssh WORKSPACE_USER@TAILNET_IP 'echo boot-access-ok'
# Keep a separate interactive terminal for recovery/testing:
ssh -t WORKSPACE_USER@TAILNET_IP
# Optional browser access through SSH, using an unused local port:
ssh -N -L 4773:127.0.0.1:3773 WORKSPACE_USER@TAILNET_IP
```

For the tunnel, open `http://127.0.0.1:4773` on the MacBook and follow T3's normal authentication/pairing. Adjust the destination if you changed `runtime.t3_port`. SSH forwarding also requires a key/policy that permits forwarding; do not strip existing key restrictions to make the optional tunnel work. A successful key check while home is unlocked does not prove access before desktop login or after a reboot.

## 9. Add mount-safe boot startup

After runtime, provider authentication, SSH key access and the intended remote connection are established:

```bash
./install.sh --config machine.local.json --only startup --plan
./install.sh --config machine.local.json --only startup --apply
agentic-startup start
agentic-startup status --json
```

This opt-in installer enrolls the current home identity, installs root-owned helpers outside home, stages the public SSH authorization file outside home while retaining home keys/password policy, enables its boot jobs, enables lingering for workspace services, and adds mount guards/target membership to selected installed services/timers. Existing working application processes are retained. A changed root monitor may restart to load code/config.

`startup.home_policy=auto` selects the existing eCryptfs metadata layout when present; otherwise it enrolls a supported mounted local block filesystem. A root-backed ordinary/ext4 home works. Btrfs subvolumes, NFS/network homes, overlay/container filesystems and custom unlock systems need separate adapters/testing. A fresh LUKS filesystem must be unlocked/mounted by the OS before the normal user session; this helper cannot unlock it remotely from early boot.

Keep using the same machine config for partial calls. Earlier startup components and original rollback backups are retained. After any later installation of additional optional timers, rerun this startup scope, then `agentic-startup start`, so the user manager reloads the updated target/guards and can discover them. If you want startup included in a future rebuild, record that choice in your private config and retain this two-phase ordering: establish keys/runtime first, then configure startup.

## 10. Select maintenance, budgets and power behavior

Run an initial read-only audit after installing representative projects/data:

```bash
dev-storage audit
dev-storage status
./install.sh --config machine.local.json --only storage.audit --set storage.profile=heavy --set storage.cleanup=false --apply
# Example allocation adjustment; choose from measured usage:
./install.sh --config machine.local.json --only storage.audit --set 'storage.budgets_gib.project-dependencies=60' --apply
```

The audit reports allocated storage by category/path, large files, pressure and advisory budgets; it does not infer which personal/project data is expendable. Budgets scale to the filesystem and workload guidance uses RAM/CPU. The default free-space target is 20%, with a critical threshold at 10%. Those are warnings, not hard quotas or authorization to delete data. File preservation can leave the host above a budget until a human reviews it.

User timers, when enabled:

| Task | Schedule / behavior |
| --- | --- |
| Capacity/pressure check | First opportunity around 10 minutes after boot, then hourly, with up to 5 minutes jitter |
| Deep home audit | Daily opportunity at 04:00 + up to 45 minutes jitter; skips if the latest audit is under seven days old or the host is busy |
| Maintenance | Sunday at 05:00 + up to 45 minutes jitter; cleanup stays skipped while disabled and defers to busy checks when enabled |
| Functional startup health | Every five minutes by default after selecting startup health; home/user-manager checks every 15 seconds |

These are machine-local schedules. Persistent timers can catch up on missed opportunities; a scheduled start is not a promise to perform heavy work during an active build. Local reports/status are the alert channel; there are no external notifications.

Optional system policy and native T3 agent fairness are independent selections:

```bash
./install.sh --config machine.local.json --only storage.system --plan
./install.sh --config machine.local.json --only storage.system --apply
# Start an agent in T3 first so its native agent slice exists:
./install.sh --config machine.local.json --only storage.limits --apply
```

System policy bounds journald retention/writeback and adds a low-priority system audit timer. It does not prune Docker, change filesystem reserved blocks, manage Timeshift retention, install database services or create off-machine backups. Agent fairness reserves roughly one CPU thread for the host by default and retains native T3 aggregate memory limits. The optional `devbox-run build -- COMMAND` / `devbox-run agent -- COMMAND` wrappers bound newly launched commands; they do not take over every shell on the machine. Server cgroup limits and agent scopes are distinct.

For an always-available laptop, explicitly select power configuration:

```bash
./install.sh --config machine.local.json --only sleepless.cli --apply
./install.sh --config machine.local.json --only sleepless.power --set sleepless.mode=always-on --plan
./install.sh --config machine.local.json --only sleepless.power --set sleepless.mode=always-on --apply
```

Logind is not restarted during setup; that drop-in takes effect at its next restart/boot. Review the desktop Power Management panel as well: disable automatic AC suspend if continuous availability is intended, especially on Cinnamon, and verify lid behavior on your hardware. A locked or blank screen is fine. Persistent power configuration is not part of `headless-heavy` by default. Save desired power/maintenance overrides in your nonsecret machine config for the next rebuild.

## 11. Test the actual boot and recovery path

Do this only after saving active work and proving a second SSH connection plus a usable LAN/physical recovery path. An open SSH session itself does not survive a reboot and is not a fallback to an expired tailnet identity.

1. Record boot/reboot time and stop/save manual builds, terminals, databases and other in-flight work according to their normal recovery procedures. Preserve repositories, agent state, databases and volume data; commit state is not a substitute for a data backup.
2. From the local console or the confirmed administrative path, perform a controlled reboot. On new encrypted root storage, satisfy the OS disk-unlock prompt first. Do not bypass it with a stored plaintext password/key.
3. Before desktop login, reconnect from the MacBook with the known key. Under working networking the acceptance target is SSH within three minutes of boot; record the actual time and account for any deliberate pre-boot disk-unlock delay.
4. On the old eCryptfs layout, use `ssh -t WORKSPACE_USER@TAILNET_IP`, then `agentic-startup unlock` as that user, without sudo. The distro helper privately asks for the Linux login password. On an ordinary/OS-unlocked home there is no eCryptfs unlock step.
5. Run `agentic-startup status --json` and inspect the user services. The monitor should start the workspace after a verified home mount. The target is functional proxy/T3/remote connection within five minutes after unlock/availability, not a guarantee.
6. Open the authenticated T3 UI from the MacBook and run one safe new agent task. Check that existing conversation history is present. This external test is separate from the local tunnel-edge probe; the status JSON deliberately leaves end-to-end UI verification unverified.
7. Log out of the test SSH session. Reconnect independently and confirm that workspace services remained up. Check expiry/status and deliberately test networking recovery only while preserving an alternate access path.

What survives: saved repositories/worktrees, conversation databases, credentials, files and persistent volumes. What does not: RAM, SSH sessions, running shell commands, builds, previews and in-flight database transactions. T3 may continue eligible interrupted runs according to its own policy; this is not restoration of the same OS process or permission to replay an interrupted command blindly. Manually launched Docker/PostgreSQL/BuildKit, particularly data under `/tmp`, require their own reviewed recovery; this repo does not turn them into permanent boot services. `/tmp` is not a durable data location.

## 12. Operate, update and recover

```bash
agentic-startup status --json
systemctl --user status cli-proxy-api.service t3code.service
systemctl --user list-timers --all
dev-storage status
```

`ready` requires the enrolled home, authenticated nonempty proxy model list, T3 HTTP response, Internet/control URL reachability, online tailnet without the warning conditions, and the T3 tunnel edge check. `locked`, `starting` and `degraded` identify other conditions. Status exit codes are 0 ready, 1 reported non-ready state, 2 execution/configuration error. The provisioner's verify stage reports conditions without reinstalling/restarting the stack.

Home/startup problem: use the [startup recovery runbook](../packages/startup/README.md); never unmount an active home to test recovery. After a legitimate home unlock/mount, `agentic-startup start` reconciles idempotently. Provider/Internet outage: inspect its supported login/network state; no whole-stack restart is triggered by a failed model request. Tailnet expiry below 24 hours is a local warning. Renew through the supported browser/OIDC flow while access is available; after expiry, LAN/physical recovery may be necessary. Existing renewal timers are retained when already installed; a fresh machine does not automatically receive the old devbox's renewal service.

Upgrade code intentionally: preserve dirty work, review upstream changes, then rerun plans/scopes with the saved machine config. Reapplying is not a universal rollback transaction: completed steps remain after a later failure; some version upgrades need explicit adoption. Locally modified managed files stop automated overwrite. Native provider/T3 updates follow their supported release procedures. A deliberate restart may be needed to activate changed ports/limits on a healthy running service.

Startup rollback, with the correct home available:

```bash
sudo agentic-startup uninstall --user "$USER"
```

It checks hashes, restores its managed files/logout marker and leaves healthy work/data/networking in place. It is not a complete uninstaller for every selected application. Do not remove the protected home layer manually under a running workspace.

Keep the nonsecret machine config, repo revision, OS release, installed versions and measured acceptance results as a recovery inventory. Back up repositories, conversations, worktrees, databases and volumes to verified off-machine capacity. Store credentials and encryption recovery material privately outside this public repo; provider sessions and machine identities are not transferred by copying JSON. Test restores. Storage checks and Timeshift freshness reporting are not a backup system.
