#!/usr/bin/python3
"""Administrator installer and conservative, manifest-based rollback."""
import argparse
import base64
import datetime as dt
import hashlib
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys

BASE = Path('/var/lib/agentic-startup')
CONFIG = Path('/etc/agentic-startup')
LIB = Path('/usr/local/libexec')


def command(*args, check=True):
    p = subprocess.run(args, text=True, capture_output=True, timeout=45, cwd='/')
    if check and p.returncode:
        raise RuntimeError('Required command failed: ' + Path(args[0]).name)
    return p


def digest(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(path):
    if path.is_symlink():
        raise RuntimeError('Refusing a symlink at a managed file path')
    if not path.exists():
        return None
    if not path.is_file():
        raise RuntimeError('Managed path is not a regular file')
    st = path.stat()
    return {'data': base64.b64encode(path.read_bytes()).decode(), 'mode': st.st_mode & 0o777,
            'uid': st.st_uid, 'gid': st.st_gid}


def write(path, data, mode=0o644, uid=0, gid=0):
    path = Path(path)
    # Do not follow a user's replacement symlink while operating with sudo.
    for parent in path.parents:
        if parent.is_symlink():
            raise RuntimeError('Refusing a symlink in a managed parent path')
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.agentic-new')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        os.fchmod(fd, mode)
        os.fchown(fd, uid, gid)
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def restore(path, prior):
    path = Path(path)
    if prior is None:
        path.unlink(missing_ok=True)
    else:
        write(path, base64.b64decode(prior['data']), prior['mode'], prior['uid'], prior['gid'])


def save_manifest(path, manifest):
    write(path, (json.dumps(manifest, indent=2) + '\n').encode(), 0o600)


def install(source, user, options=None):
    options = options or {}
    account = pwd.getpwnam(user)
    home = Path(account.pw_dir)
    if account.pw_uid == 0 or not re.fullmatch(r'[a-z_][a-z0-9_-]*[$]?', user):
        raise RuntimeError('A non-root workspace account is required')
    spec = importlib.util.spec_from_file_location('startup', source / 'startup.py')
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    backing = Path('/home/.ecryptfs') / user / '.Private'
    metadata = backing.parent / '.ecryptfs'
    locked = BASE / 'locked-homes' / user
    cfg = {'version': 1, 'user': user, 'uid': account.pw_uid, 'home': str(home),
           'backing': str(backing), 'metadata': str(metadata), 'locked_home': str(locked)}
    existing_path = CONFIG / (user + '.json')
    prior_cfg = json.loads(existing_path.read_text()) if existing_path.exists() else {}
    requested = options.get('components', ['ssh','home','workspace','health'])
    if any(c not in ('ssh','home','workspace','health') for c in requested):
        raise RuntimeError('Unknown startup component')
    components = sorted(set(requested) | set(prior_cfg.get('components',
                         ['ssh','home','workspace','health'] if prior_cfg else [])))
    cfg['components'] = components
    policy = options.get('home_policy', prior_cfg.get('home_policy', 'auto'))
    encrypted = metadata.exists() or any(e['target'] == str(home) and e['fstype'] == 'ecryptfs'
                                        for e in runtime.mount_entries())
    if policy == 'auto':
        policy = 'ecryptfs' if encrypted else 'mounted'
    if policy not in ('mounted','ecryptfs') or policy == 'mounted' and encrypted:
        raise RuntimeError('An eCryptfs home cannot use mounted policy')
    cfg['home_policy'] = policy
    cfg.update({key: options.get(key, prior_cfg.get(key, default)) for key, default in
                [('proxy_port',8317),('t3_port',3773),('poll_interval',15),('health_interval',300),
                 ('keep_unlocked',True)]})
    if policy == 'mounted':
        candidates = [e for e in runtime.mount_entries() if str(home) == e['target'] or
                      str(home).startswith(e['target'].rstrip('/') + '/')]
        entry = max(candidates, key=lambda e: (len(e['target']), e['id']))
        uuid = command('/usr/bin/findmnt', '-n', '-o', 'UUID', '--target', str(home)).stdout.strip()
        if not re.fullmatch(r'[A-Za-z0-9-]+', uuid) or not Path('/dev/disk/by-uuid', uuid).exists():
            raise RuntimeError('Mounted policy requires a persistent block-filesystem UUID')
        identity = {k: entry[k] for k in ('target','root','fstype')}
        identity.update(uuid_path='/dev/disk/by-uuid/' + uuid, home_inode=home.stat().st_ino)
        cfg['mount_identity'] = prior_cfg.get('mount_identity', identity)
    if not runtime.inspect_home(cfg)['verified']:
        raise RuntimeError('Installer requires the correctly enrolled home filesystem')
    if policy == 'ecryptfs' and (metadata / 'Private.mnt').read_text().strip() != str(home):
        raise RuntimeError('Unsupported eCryptfs mountpoint metadata')
    user_units = home / '.config/systemd/user'
    if 'workspace' in components:
        for name in runtime.REQUIRED:
            if not (user_units / name).is_file():
                raise RuntimeError('Required application unit missing; configure runtime first')
        for rel in ['.local/bin/cli-proxy-api', '.config/environment.d/cliproxy.conf']:
            if not (home / rel).is_file():
                raise RuntimeError('Required installed runtime prerequisite is missing')
    if 'workspace' in components and policy == 'ecryptfs' and not cfg['keep_unlocked']:
        raise RuntimeError('Persistent eCryptfs workspace requires keep_unlocked=true')
    if command('/usr/bin/systemctl', 'show', '-p', 'Version', '--value').returncode:
        raise RuntimeError('systemd is required')
    # Keep the existing control URL. Do not register, log out or alter network preferences.
    try:
        prefs = json.loads(command('/usr/bin/tailscale', 'debug', 'prefs').stdout)
        cfg['connectivity_url'] = prefs.get('ControlURL') or 'https://controlplane.tailscale.com'
    except (OSError, ValueError, RuntimeError):
        cfg['connectivity_url'] = None
    if 'ssh' in components:
        auth_path = options.get('authorized_keys', prior_cfg.get('authorized_keys', str(home / '.ssh/authorized_keys'))) if 'ssh' in requested else prior_cfg.get('authorized_keys', str(home / '.ssh/authorized_keys'))
        cfg['authorized_keys'] = auth_path
        auth = Path(auth_path)
        keys = auth.read_bytes()
        if not any(l.strip() and not l.lstrip().startswith(b'#') for l in keys.splitlines()):
            raise RuntimeError('Existing authorized public keys are required')
        command('/usr/bin/ssh-keygen', '-l', '-f', str(auth))
        if command('/usr/bin/systemctl', 'is-enabled', 'ssh.service', check=False).stdout.strip() == 'masked':
            raise RuntimeError('SSH is masked; inspect the existing policy')

    BASE.mkdir(mode=0o700, exist_ok=True)
    BASE.chmod(0o700)
    folder = BASE / user
    folder.mkdir(mode=0o700, exist_ok=True)
    manifest_path = folder / 'install-manifest.json'
    original_manifest = snapshot(manifest_path)
    previous_activity = {name: command('/usr/bin/systemctl', 'is-active', name, check=False).stdout.strip()
                         for name in [f'agentic-startup@{user}.service', f'agentic-home-guard@{user}.service',
                                      *(['ssh.service'] if 'ssh' in components else [])]}
    previous_enablement = {name: command('/usr/bin/systemctl', 'is-enabled', name, check=False).stdout.strip()
                          for name in previous_activity}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if not manifest.get('complete'):
            raise RuntimeError('Incomplete prior installation; inspect its backup manifest')
    else:
        manifest = {'version': 1, 'user': user, 'created_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                    'files': {}, 'markers': {}, 'complete': False}
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    save_manifest(folder / ('manifest-before-' + stamp + '.json'), manifest)
    current_changes = {}
    marker_changes = {}
    monitor_changed = False
    monitor_restarted = False

    def manage(path, data, mode=0o644, uid=0, gid=0):
        path = Path(path)
        prior = snapshot(path)
        current_changes[str(path)] = prior
        row = manifest['files'].setdefault(str(path), {'before': prior})
        if 'installed_sha256' in row:
            actual = digest(path.read_bytes()) if path.is_file() else None
            if actual != row['installed_sha256']:
                raise RuntimeError('Managed file changed since install; refusing to overwrite it')
        missing = []
        parent = path.parent
        while parent != home and home in parent.parents and not parent.exists():
            missing.append(parent)
            parent = parent.parent
        write(path, data, mode, uid, gid)
        if uid == account.pw_uid:
            for directory in missing:
                os.chown(directory, uid, gid)
        row['installed_sha256'] = digest(data)
        save_manifest(manifest_path, manifest)

    try:
        CONFIG.mkdir(mode=0o755, exist_ok=True)
        LIB.mkdir(mode=0o755, exist_ok=True)
        monitor_changed = not (LIB / 'agentic-startup.py').exists() or (LIB / 'agentic-startup.py').read_bytes() != (source / 'startup.py').read_bytes()
        manage(LIB / 'agentic-startup.py', (source / 'startup.py').read_bytes(), 0o755)
        manage(LIB / 'agentic-startup-install.py', (source / 'install.py').read_bytes(), 0o755)
        manage('/usr/local/bin/agentic-startup', b'#!/bin/sh\nexec /usr/bin/python3 /usr/local/libexec/agentic-startup.py "$@"\n', 0o755)
        if policy == 'ecryptfs':
            locked.parent.mkdir(mode=0o700, exist_ok=True)
            locked.mkdir(mode=0o555, exist_ok=True)
            os.chown(locked, account.pw_uid, account.pw_gid)
            locked.chmod(0o555)
            cfg['locked_home_inode'] = locked.stat().st_ino
            for name, target in [('.ecryptfs', metadata), ('.Private', backing)]:
                link = locked / name
                if link.is_symlink() and os.readlink(link) == str(target):
                    continue
                if link.exists() or link.is_symlink():
                    raise RuntimeError('Unexpected locked-home template contents')
                link.symlink_to(target)
        encoded_cfg = (json.dumps(cfg, indent=2) + '\n').encode()
        monitor_changed = monitor_changed or not existing_path.exists() or existing_path.read_bytes() != encoded_cfg
        manage(existing_path, encoded_cfg)
        for name in ('agentic-home-guard@.service', 'agentic-startup@.service'):
            manage(Path('/etc/systemd/system') / name, (source / 'systemd' / name).read_bytes())
        # The system manager can order the monitor against mounts and user managers;
        # user-unit After=home.mount alone cannot express this cross-manager ordering.
        mount_unit = command('/usr/bin/systemd-escape', '--path', '--suffix=mount', (str(home) if policy == 'ecryptfs' else cfg['mount_identity']['target'])).stdout.strip()
        monitor_name = f'agentic-startup@{user}.service'
        manage(Path('/etc/systemd/system') / (monitor_name + '.d/ordering.conf'),
               f'[Unit]\nAfter={mount_unit} user@{account.pw_uid}.service\n'.encode())
        manage(Path('/etc/systemd/system') / f'user@{account.pw_uid}.service.d/agentic-home.conf',
               f'[Unit]\nRequires=agentic-home-guard@{user}.service\nAfter=agentic-home-guard@{user}.service\n'.encode())
        if 'ssh' in components:
            manage(Path('/etc/systemd/system/ssh.service.d/agentic-home.conf'),
                   f'[Unit]\nWants=agentic-home-guard@{user}.service\nAfter=agentic-home-guard@{user}.service\n'.encode())
            key_path = Path('/etc/ssh/authorized_keys') / user
            key_path.parent.mkdir(mode=0o755, exist_ok=True)
            manage(key_path, keys, 0o644)
            ssh_config = (f'# Managed boot-access keys; password and home-key policies are retained.\n'
                          f'Match User {user}\n'
                          '    AuthorizedKeysFile /etc/ssh/authorized_keys/%u .ssh/authorized_keys .ssh/authorized_keys2\n'
                          'Match all\n')
            manage(Path('/etc/ssh/sshd_config.d') / ('00-agentic-startup-' + user + '.conf'), ssh_config.encode())
            command('/usr/sbin/sshd', '-t')
            effective = command('/usr/sbin/sshd', '-T', '-C', f'user={user},host=localhost,addr=127.0.0.1').stdout
            if 'authorizedkeysfile /etc/ssh/authorized_keys/%u ' not in effective:
                raise RuntimeError('Existing sshd precedence prevents boot-key configuration')
        if 'workspace' in components:
            wanted = list(runtime.REQUIRED)
            wanted.extend(u for u in runtime.OPTIONAL if (user_units / u).is_file())
            target = ('[Unit]\nDescription=Agentic workspace after verified home unlock\nWants=' +
                      ' '.join(wanted) + '\n[Install]\nWantedBy=default.target\n')
            manage(user_units / 'agentic-workspace.target', target.encode(), uid=account.pw_uid, gid=account.pw_gid)
            for unit in wanted:
                guard = ('[Unit]\nPartOf=agentic-workspace.target\n[Service]\n'
                         f'ExecCondition=/usr/bin/python3 {LIB}/agentic-startup.py check-home --user {user}\n')
                if unit.endswith('.timer'):
                    guard = '[Unit]\nPartOf=agentic-workspace.target\n'
                    # Guard the actual command service, not merely its timer.
                    service = unit[:-6] + '.service'
                    if (user_units / service).is_file():
                        manage(user_units / (service + '.d/agentic-home.conf'),
                               (f'[Unit]\nPartOf=agentic-workspace.target\n[Service]\n'
                                f'ExecCondition=/usr/bin/python3 {LIB}/agentic-startup.py check-home --user {user}\n').encode(),
                               uid=account.pw_uid, gid=account.pw_gid)
                manage(user_units / (unit + '.d/agentic-home.conf'), guard.encode(), uid=account.pw_uid, gid=account.pw_gid)
        # Stop-on-logout conflicts with lingering workspace services. Back up only the
        # marker, never a password, encryption key or wrapped-passphrase file.
        if policy == 'ecryptfs' and cfg['keep_unlocked'] and bool(set(components) & {'home','workspace'}):
            marker = metadata / 'auto-umount'
            marker_changes[str(marker)] = snapshot(marker)
            if str(marker) not in manifest['markers']:
                manifest['markers'][str(marker)] = snapshot(marker)
                save_manifest(manifest_path, manifest)
            marker.unlink(missing_ok=True)
        command('/usr/bin/systemctl', 'daemon-reload')
        if 'ssh' in components:
            command('/usr/bin/systemctl', 'enable', 'ssh.service')
            if command('/usr/bin/systemctl', 'is-active', 'ssh.service', check=False).returncode == 0:
                command('/usr/bin/systemctl', 'reload', 'ssh.service')
            else:
                command('/usr/bin/systemctl', 'start', 'ssh.service')
        command('/usr/bin/systemctl', 'enable', f'agentic-home-guard@{user}.service')
        command('/usr/bin/systemctl', 'start', f'agentic-home-guard@{user}.service')
        if 'workspace' in components:
            command('/usr/bin/loginctl', 'enable-linger', user)
        if set(components) & {'workspace','health','home'}:
            command('/usr/bin/systemctl', 'enable', monitor_name)
            # Reloading root monitor code/config does not restart workspace applications.
            action = 'restart' if monitor_changed and previous_activity[monitor_name] == 'active' else 'start'
            monitor_restarted = action == 'restart'
            command('/usr/bin/systemctl', action, monitor_name)
        # Networking and tailscaled retain their installed enablement, identity and policy.
        # No restart of T3, proxy, the user manager, networking, or tailscaled.
        manifest['complete'] = True
        save_manifest(manifest_path, manifest)
        print('Startup installed. Healthy application processes were not restarted.')
        if 'ssh' in components:
            print('Boot keys are staged; verify a second SSH connection before any reboot.')
        if policy == 'ecryptfs':
            print('The read-only locked-home surface is armed for the next boot; the active home was not changed.')
        print('One interactive home unlock per boot remains required.' if policy == 'ecryptfs' else
              'Home availability follows the OS filesystem unlock/mount policy.')
        print('Backup manifest: ' + str(manifest_path))
    except Exception:
        # Stop only units newly started by this failed attempt; application processes stay up.
        for name, previous in previous_activity.items():
            if previous != 'active':
                command('/usr/bin/systemctl', 'stop', name, check=False)
            if previous_enablement[name] != 'enabled':
                command('/usr/bin/systemctl', 'disable', name, check=False)
        # Roll back this attempt's file replacements. Keep a separate failure manifest.
        save_manifest(folder / ('failed-' + stamp + '.json'), manifest)
        for path, prior in reversed(list(current_changes.items())):
            restore(path, prior)
        for path, prior in marker_changes.items():
            restore(path, prior)
        restore(manifest_path, original_manifest)
        command('/usr/bin/systemctl', 'daemon-reload', check=False)
        if monitor_restarted:
            # This daemon caches its root config/code; roll it back along with the files.
            command('/usr/bin/systemctl', 'restart', monitor_name, check=False)
        if 'ssh' in components:
            command('/usr/bin/systemctl', 'reload', 'ssh.service', check=False)
        raise


def uninstall(user):
    folder = BASE / user
    manifest_path = folder / 'install-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    # Preflight all ownership hashes before touching services or files.
    for name, row in manifest['files'].items():
        p = Path(name)
        if p.is_symlink() or not p.is_file() or digest(p.read_bytes()) != row['installed_sha256']:
            raise RuntimeError('Managed file changed; rollback refuses to overwrite newer work')
    for name in manifest['markers']:
        if Path(name).exists():
            raise RuntimeError('Auto-unmount marker changed; review it before rollback')
    command('/usr/bin/systemctl', 'disable', '--now', f'agentic-startup@{user}.service')
    command('/usr/bin/systemctl', 'disable', f'agentic-home-guard@{user}.service')
    # Remove PartOf before touching the target: leave healthy work processes running.
    for name, row in reversed(list(manifest['files'].items())):
        restore(name, row['before'])
    for name, prior in manifest['markers'].items():
        restore(name, prior)
    command('/usr/bin/systemctl', 'daemon-reload')
    account = pwd.getpwnam(user)
    command('/usr/sbin/runuser', '-u', user, '--', '/usr/bin/env',
            f'XDG_RUNTIME_DIR=/run/user/{account.pw_uid}',
            f'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{account.pw_uid}/bus',
            '/usr/bin/systemctl', '--user', 'daemon-reload')
    if any('/etc/ssh/' in name for name in manifest['files']):
        command('/usr/sbin/sshd', '-t')
        command('/usr/bin/systemctl', 'reload', 'ssh.service')
    manifest['uninstalled_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    save_manifest(folder / 'uninstalled-manifest.json', manifest)
    manifest_path.unlink()
    print('Managed startup changes restored. Applications, data and boot networking were retained.')
    print('An existing read-only locked-home layer is intentionally not unmounted automatically.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user', required=True)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--uninstall', action='store_true')
    parser.add_argument('--options-json', default='{}', help='Nonsecret provisioning options')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Administrator privileges are required')
    BASE.mkdir(mode=0o700, exist_ok=True)
    lock = os.open(BASE / 'installer.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    other = [p for p in CONFIG.glob('*.json') if p.stem != args.user]
    if other:
        raise RuntimeError('This v1 supports one managed workspace account per host')
    if args.uninstall:
        uninstall(args.user)
    else:
        if args.source is None:
            parser.error('--source is required for installation')
        install(args.source.resolve(), args.user, json.loads(args.options_json))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError):
        print('Startup installation/rollback failed. Review prerequisites and the private backup manifest; no secrets are printed.', file=sys.stderr)
        sys.exit(1)
