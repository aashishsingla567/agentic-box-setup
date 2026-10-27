# Storage and heavy agent workload maintenance

```bash
./install.sh --only storage --apply
dev-storage audit
dev-storage status
devbox-run build -- npm run build
```

This package installs the Linux implementation of
[aashishsingla567/dev-storage](https://github.com/aashishsingla567/dev-storage)
from the exact commit recorded in `install.sh`. It generates adaptive disk
budgets and a heavy-work concurrency plan, enables hourly capacity checks,
provides idle opportunities for weekly deep audits, and schedules weekly
maintenance. Existing config is preserved. **Cleanup defaults disabled.**
Reports and settings are private and never copied into this repository.

Worktrees, repositories, dependencies, build outputs, agent histories,
databases, Docker volumes and personal files are preserved. `dev-storage clean`
only previews old download-cache/log files; `--apply` is explicit and defers
while the machine is busy. Do not use blanket pruning for an active agent box.

On a four-thread / 16 GiB host, start with four lightweight agent sessions,
two doing active local work, and one heavy build. The wrapper provides optional
memory/CPU limits; it retains T3's native aggregate budget when launched from
a T3 agent scope. Limits are ceilings, not memory reservations. Large builds
may require a higher per-command limit or fewer concurrent agents.

Optional administrator policies and T3 CPU fairness are separate:

```bash
# SOURCE is printed/discoverable under ~/.local/share/agentic-box-setup/sources/dev-storage/
bash "$SOURCE/linux/configure-t3-limits.sh"
sudo bash "$SOURCE/linux/install-system.sh"
```

These add aggregate T3 agent CPU fairness, bounded dirty-write buffering,
journal caps, and a separate system audit. The administrator installer backs up
managed settings and does not restart application services or delete files.
Review filesystem reservations, Timeshift retention and encrypted off-machine
backups separately; the installers never change them.

Detailed accounting rules, retention boundaries, timer cadences, rollback and
non-systemd installation are in the utility's `linux/README.md`.
For large eCryptfs homes, the utility also supports read-only allocated-byte
audits using inode-matched backing metadata, avoiding per-file header reads.
The administrator installer also provides `dev-storage-underlay`: a read-only
private-mount-namespace audit of legacy files hidden underneath a mounted home.
It leaves the active home mounted and never deletes discovered files.
For an existing local source checkout, run
`DEV_STORAGE_SOURCE=/absolute/path/to/dev-storage ./install.sh --only storage --apply`.
The explicit local override trusts that checkout, including its local edits.

## Granular configuration

`storage.audit` installs the user utility and schedules checks/audits/maintenance. `storage.system` independently fetches the pinned source, then installs the optional administrator policy without installing user timers. `storage.limits` independently adjusts the native T3 agent slice and requires an agent to have created that slice; it does not need a storage audit installation.

The frontend exposes profile, timer/cleanup switches, individual budget envelopes, and agent CPU/I/O fairness. Setting cleanup false explicitly disables scheduled deletion. Setting timers false disables these managed user timers; it does not stop an already-running audit service. System policy remains a separately selected scope. T3 native agent memory limits are retained.

Budget names: `os-apps`, `system-snapshots`, `swap`, `project-source-and-data`, `git-history`, `project-dependencies`, `build-artifacts`, `toolchains`, `package-caches`, `other-caches`, `agent-state`, `containers`, `browser-runtimes`, `application-state`, `personal-files-and-downloads`, `system-logs-and-caches`, `model-weights`, `virtual-machines`, `android-sdk-and-emulators`, `encrypted-overhead-and-other`. Use these known utility categories; the frontend rejects unknown category names. Values are GiB allocation guidance and warnings, never permission to delete protected work.

```bash
./install.sh --only storage.audit --set storage.profile=heavy --set storage.cleanup=false --apply
./install.sh --only storage.audit --set 'storage.budgets_gib.project-dependencies=60' --apply
./install.sh --only storage.limits --set storage.agent_limits.cpu_quota_percent=600 --apply
```
