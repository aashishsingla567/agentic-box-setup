# From OS installation to a remote agent machine

Choose the OS before provisioning. Recommended starting points are Linux Mint 22.3 Cinnamon for a desktop devbox, Ubuntu 24.04 LTS desktop/server, or a supported Debian release with Python 3.10+ (Debian 12 or newer). Distribution support here means Debian-family provisioning adapters; full installations on every distribution/architecture have not been tested. CLI adapters target x86_64 and aarch64; selected desktop assets are currently x86_64 only and upstream availability can change.

1. Download installation media from [Mint](https://linuxmint.com/download.php), [Ubuntu](https://ubuntu.com/download), or [Debian](https://www.debian.org/distrib/). Follow that distribution's signature/checksum verification instructions. Back up existing data and test restoration before replacing an installation.
2. Use the OS installer to choose filesystem/encryption, partitioning, locale, timezone, keyboard, username and desktop/server packages. This repository neither partitions nor formats disks. For a new encrypted installation, use distro-supported LUKS2 and keep a recovery key separately. Automatic TPM unlock requires qualification of firmware, Secure Boot, kernel/initramfs verification, updates and recovery on that hardware. Enabling Secure Boot alone is insufficient. Disk passphrase entry may still require physical access before SSH starts.
3. Create a non-root sudo user. Configure persistent network access using the OS's normal network tools: on a desktop, make the intended Wi-Fi connection available to all users and do not rely on a secret stored only in the desktop keyring. On a server, use its NetworkManager/networkd configuration. Test the actual boot network path; provisioning does not guess Wi-Fi credentials or replace network policy.
4. Bootstrap and clone as that workspace user:

```bash
sudo apt-get update
sudo apt-get install -y git python3 ca-certificates curl openssh-server libpam-systemd
git clone https://github.com/aashishsingla567/agentic-box-setup.git
cd agentic-box-setup
./install.sh --wizard --output machine.local.json
./install.sh --config machine.local.json --plan
```

Before this PR is merged, clone its `feat/configurable-provisioning` branch with `git clone --branch feat/configurable-provisioning ...`. Alternatively copy [new-headless.json](../config/examples/new-headless.json) to `machine.local.json`, change `machine.os` to the installed OS, and review the configuration reference. No host-specific account name, machine identity, provider login or key is in that example.

5. Apply the reviewed profile:

```bash
./install.sh --config machine.local.json --apply
```

Headless/desktop profiles permit service starts, including the supported `t3 service install` path. If you want to review each stage, run `--stage install --apply`, then individual `--only runtime.proxy --stage configure --apply` and `--only runtime.t3 --stage configure --apply` scopes. The proxy readiness gate checks its authenticated local API without requiring Internet or a provider login. T3 remains usable for onboarding while startup health reports missing models as degraded. A later failure leaves prior completed actions in place; repair and rerun that scope.

6. Authenticate only the selected providers through their supported interactive login flows. Configure CLIProxyAPI accounts using `cli-proxy-api -help` and the selected release's login options; credentials stay in the private auth directory. Use `t3` and its UI to configure providers and T3 Connect. This repo generates a new local proxy key, never prints it, and does not export this host's provider configuration. Existing unmanaged proxy config is preserved; configure it manually or skip that component instead of overwriting it. Restart neither existing healthy services nor interrupted commands automatically.
7. Enroll remote access explicitly. Add the intended device's **public** SSH authorization entry (with its restrictions) to `~/.ssh/authorized_keys`, with `.ssh` mode 0700 and the file 0600. Test a second connection while preserving the original session. For tailnet enrollment, run `sudo tailscale up` (add `--login-server=https://YOUR-CONTROL-HOST` for Headscale), or set `network.join=true` for the selected Tailscale install scope. A private `.env` auth key is optional; OIDC/browser login needs none. Running identities and routing are retained. Browser renewal under an encrypted home cannot run until that home is unlocked. No control-server settings are changed.
8. Add startup after runtime and remote access are established:

```bash
./install.sh --config machine.local.json --only startup --plan
./install.sh --config machine.local.json --only startup --apply
agentic-startup status --json
```

The existing Mint eCryptfs layout needs one remote `agentic-startup unlock` after every boot. An OS-encrypted root/home follows its OS unlock policy; this package does not make disk unlock automatic. Root-backed SSH keys help only when the OS has booted far enough to provide networking and SSH.

9. Calibrate budgets after installing real projects and running representative agent/build workloads:

```bash
dev-storage audit
dev-storage status
./install.sh --only storage.audit --set 'storage.budgets_gib.project-dependencies=60' --apply
# After starting an agent through T3, apply optional aggregate CPU/I/O fairness:
./install.sh --only storage.limits --apply
```

Adaptive budgets target 20% free storage, warn critically below 10%, and reserve RAM/CPU for the UI, SSH and the host. They are allocation guidance rather than hard storage quotas. Heavy agent throughput depends on active builds/model runtimes and measured memory pressure; don't equate idle conversations with running shell processes. The optional system policy bounds journald/writeback and schedules a low-priority read-only system audit. It does not run Docker, PostgreSQL or BuildKit as permanent services or delete their data.

10. Follow the [startup acceptance checklist](../packages/startup/README.md): save work; prove a second public-key connection and an alternative recovery path; then perform a separately controlled reboot. Measure SSH availability before desktop login and local/remote readiness after unlock. Do not promise the three/five-minute goals without measuring them. Eligible T3 conversation/run continuation is application-owned; old shell commands and manually launched `/tmp` workloads must be reviewed and recovered explicitly. Tailnet expiry may require LAN or physical access.

Keep a nonsecret machine config alongside the repo version and a private recovery inventory. Back up repositories, conversations, worktrees, databases and volume data to verified off-machine capacity. Private credentials need their own protected recovery procedure. Do not commit keys, conversation exports, runtime databases or encryption material to this public repo. Hardware identity, encryption enrollment and provider authentication are per-machine operations, even when the nonsecret configuration is shared.
