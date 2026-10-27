# Review of storage, startup and configurable provisioning

Reviewed PRs #1 (storage integration), #2 (mount-safe startup) and #3 (configurable provisioning) on 2026-10-27. The head commits of #1 and #2 are ancestors of #3, so the final combined tree was reviewed as well as the original feature changes. A merge commit preserves those histories and avoids a temporary conflict between the two older shell installers on main.

Findings resolved before merge:

- Startup diagnostics return 1 for locked/degraded health. The provisioning adapter expected 2 and incorrectly failed instead of reporting that condition. It now accepts valid diagnostic results, rejects execution errors, and probes once per invocation.
- The upstream OpenCode installer puts its binary in `~/.opencode/bin`. That directory was missing from the current installer process, provisioning environment and boot service PATH. Fresh installation and later verification now find it without requiring a new shell.
- Exact Node releases below 22.16/24.10 could pass preflight and only fail after installation. Validation now rejects those versions before mutations.
- An existing unknown proxy configuration without the expected environment file could receive a new conflicting credential before setup stopped. Setup now stops before creating any credential in that case.
- Unexpected model JSON shapes could crash health/readiness probes or produce false readiness. They now report unavailable cleanly.
- Authenticated loopback probes could follow redirects or environment proxy settings with the local API credential. Those probes now stay direct and refuse redirects; no credential is forwarded.
- If an upgrade failed after restarting the root monitor, its files rolled back while the daemon retained the newer code/config in memory. Rollback now reloads the monitor after restoring its files, preserving healthy application services.

Validation: 28 provisioning/adapter tests plus 30 startup tests pass locally. Tests include a real local HTTP redirect server, a fresh-installer PATH fixture, unknown credential preservation, and injected failure after monitor restart. The real eCryptfs mount-helper integration also passes in a private namespace with disposable data/keyring/UID. Python compilation, shell syntax, systemd unit and diff checks pass. GitHub CI covers Python 3.10/3.12.

Remaining deployment acceptance is unchanged: fresh distro/architecture installations and a controlled reboot with pre-login SSH, remote unlock and external authenticated T3 reconnection must be measured separately. Review/merge does not install changes or reboot the live machine. The current devbox still needs one remote home unlock per boot.
