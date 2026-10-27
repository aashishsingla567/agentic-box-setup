# Validation record

Configurable provisioning extension, checked on the existing Linux Mint devbox on 2026-10-27:

- 21 configuration/adapter tests: precedence and types, OS/architecture checks, read-only plans, stage ordering, component selection, one startup transaction, fail-fast dispatch, unmanaged-file preservation, archive traversal refusal, runtime service-start policy, CLI-only desktop exclusion, tailnet identity preservation, private auth-key transport, and disabling cleanup before enabling overdue timers.
- 30 startup tests: original eCryptfs identity/guard/health/rollback coverage, UUID-backed mount identity including homes on root, wrong/nested mount refusal, configured ports, partial setup without application prerequisites, original backup retention across successive scopes, and failure rollback without restoring an already-disabled auto-unmount marker.
- Isolated integration with the real setuid eCryptfs helper: locked writes denied, interactive-helper mount succeeds with a disposable keyring/UID, relock exposes the read-only layer, legacy data remains unchanged. Only temporary test data and a private mount/passwd namespace are used.
- All Python files compile, every shell script passes `bash -n`, root systemd units pass `systemd-analyze verify`, local documentation links resolve, and staged diffs pass whitespace checks.
- Pinned x86_64 proxy release downloaded to a disposable directory: upstream SHA-256 digest and archive binary path checked; no binary installed.

Commands:

```bash
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s packages/startup/tests -v
python3 -m compileall -q provision.py provision_support.py packages tests
while IFS= read -r script; do bash -n "$script" || exit; done < <(git ls-files '*.sh')
sudo systemd-analyze verify packages/startup/systemd/agentic-home-guard@.service packages/startup/systemd/agentic-startup@.service
sudo unshare --mount --propagation private /usr/bin/python3 packages/startup/tests/mount_namespace.py
```

CI runs non-privileged fixtures/plans on Python 3.10 and 3.12. The privileged integration requires eCryptfs support, ecryptfs-utils, keyutils and util-linux; it is not a CI result.

This extension was not applied to the live machine. Its previously installed startup stack still reported verified unlocked home, functional proxy/T3, online tailnet and connected tunnel edge during the read-only check. The external authenticated UI remains unverified. Existing uncommitted runtime work was kept in its original checkout.

Not measured: a fresh OS install, aarch64 hardware deployment, OS-encrypted LUKS boot, a public-key connection from a second device before desktop login, logout persistence across a real remote session, or a controlled reboot. The three-minute SSH and five-minute post-unlock readiness targets require those acceptance measurements. No partitioning, OS replacement, TPM enrollment, key migration, remote identity reset or reboot was performed.
