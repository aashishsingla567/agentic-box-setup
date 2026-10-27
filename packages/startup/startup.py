#!/usr/bin/python3
"""Mount-safe startup for an existing Linux agent workspace. Standard library only."""
import argparse
import datetime as dt
import fcntl
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import pwd
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

CONFIG_DIR = Path('/etc/agentic-startup')
STATE_DIR = Path('/var/lib/agentic-startup')
LIB = '/usr/local/libexec/agentic-startup.py'
REQUIRED = ('cli-proxy-api.service', 't3code.service')
OPTIONAL = ('agentic-proxy-ready.service', 'agentic-health.timer', 'tailnet-renew.timer', 'dev-storage-check.timer',
            'dev-storage-audit.timer', 'dev-storage-maintain.timer')
STOP = False


def run(argv, timeout=20, **kwargs):
    return subprocess.run(argv, text=True, capture_output=True, timeout=timeout, **kwargs)


def atomic_json(path, value, mode=0o600):
    path = Path(path)
    tmp = path.with_name(path.name + '.new')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, mode)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'w') as out:
            json.dump(value, out, indent=2)
            out.write('\n')
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def load_config(user):
    if not re.fullmatch(r'[a-z_][a-z0-9_-]*[$]?', user):
        raise ValueError('Invalid account name')
    path = CONFIG_DIR / (user + '.json')
    st = path.stat()
    if st.st_uid != 0 or st.st_mode & 0o022 or path.is_symlink():
        raise ValueError('Startup configuration must be root-owned and not writable by others')
    cfg = json.loads(path.read_text())
    account = pwd.getpwnam(user)
    if account.pw_uid == 0 or cfg['uid'] != account.pw_uid or cfg['home'] != account.pw_dir:
        raise ValueError('Account identity changed; reinstall startup configuration')
    if cfg['user'] != user or not Path(cfg['home']).is_absolute() or cfg['home'] in ('/', '/home'):
        raise ValueError('Invalid configured home')
    return cfg


def unescape_mount(value):
    return re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), value)


def mount_entries(text=None):
    if text is None:
        text = Path('/proc/self/mountinfo').read_text()
    entries = []
    for line in text.splitlines():
        before, after = line.split(' - ', 1)
        fields, fs = before.split(), after.split()
        entries.append(dict(id=int(fields[0]), device=fields[2], root=unescape_mount(fields[3]),
                            target=unescape_mount(fields[4]), options=fields[5].split(','),
                            fstype=fs[0], source=unescape_mount(fs[1])))
    return entries


def inspect_home(cfg, entries=None, stat=os.stat, statvfs=os.statvfs):
    """Inspect mount metadata only; never read a potentially hidden user's files."""
    if cfg.get('home_policy', 'ecryptfs') == 'mounted':
        return inspect_mounted_home(cfg, entries, stat)
    try:
        home = stat(cfg['home'])
        candidates = [e for e in (mount_entries() if entries is None else entries)
                      if e['target'] == cfg['home'] and
                      e['device'] == f'{os.major(home.st_dev)}:{os.minor(home.st_dev)}']
        entry = candidates[-1] if candidates else None
        backing = stat(cfg['backing'])
        if entry and entry['fstype'] == 'ecryptfs':
            allowed = {cfg['backing'], cfg['home'] + '/.Private'}
            if (entry['source'] in allowed and home.st_ino == backing.st_ino and
                    home.st_dev != backing.st_dev and home.st_uid == cfg['uid'] and
                    backing.st_uid == cfg['uid'] and 'rw' in entry['options']):
                return {'state': 'unlocked', 'mount_id': entry['id'], 'verified': True,
                        'recovery': None}
            return {'state': 'wrong-mount', 'verified': False, 'recovery': 'Inspect home mount; do not start applications'}
        # The template's root-private parent may be inaccessible to the user.
        # Its inode is recorded by the administrator; the backing filesystem
        # supplies the boot's device number (which need not stay stable).
        try:
            template_inode = stat(cfg['locked_home']).st_ino
        except OSError:
            template_inode = cfg.get('locked_home_inode')
        protected = bool(entry and home.st_ino == template_inode and
                         home.st_dev == backing.st_dev and
                         statvfs(cfg['home']).f_flag & os.ST_RDONLY)
        return {'state': 'locked', 'verified': False, 'protected': protected,
                'recovery': 'agentic-startup unlock'}
    except OSError:
        return {'state': 'unavailable', 'verified': False, 'recovery': 'Inspect home/backing mount and startup configuration'}


def inspect_mounted_home(cfg, entries=None, stat=os.stat):
    """Require the enrolled block filesystem and home inode, including root-home layouts."""
    try:
        home = stat(cfg['home'])
        identity = cfg['mount_identity']
        device = stat(identity['uuid_path']).st_rdev
        entries = mount_entries() if entries is None else entries
        candidates = [e for e in entries if cfg['home'] == e['target'] or
                      cfg['home'].startswith(e['target'].rstrip('/') + '/')]
        # A nested unexpected mount must not be mistaken for the enrolled ancestor.
        entry = max(candidates, key=lambda e: (len(e['target']), e['id']), default=None)
        valid = bool(entry and all(entry[k] == identity[k] for k in ('target','root','fstype')) and
                     entry['device'] == f'{os.major(device)}:{os.minor(device)}' and
                     home.st_dev == device and home.st_ino == identity['home_inode'] and
                     home.st_uid == cfg['uid'] and 'rw' in entry['options'])
        return {'state': 'unlocked' if valid else 'wrong-mount', 'verified': valid,
                'mount_id': entry['id'] if valid else None,
                'recovery': None if valid else 'Restore the enrolled filesystem before starting the workspace'}
    except OSError:
        return {'state': 'unavailable', 'verified': False,
                'recovery': 'Unlock/mount the enrolled filesystem through the OS; agentic-startup start'}


def user_command(cfg, argv, timeout=25):
    env = {'HOME': cfg['home'], 'USER': cfg['user'], 'LOGNAME': cfg['user'],
           'PATH': '/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin',
           'XDG_RUNTIME_DIR': f"/run/user/{cfg['uid']}",
           'DBUS_SESSION_BUS_ADDRESS': f"unix:path=/run/user/{cfg['uid']}/bus"}
    if os.geteuid() == 0:
        return run(['/usr/sbin/runuser', '-u', cfg['user'], '--', '/usr/bin/env', '-i',
                    *[f'{k}={v}' for k, v in env.items()], *argv], timeout=timeout, cwd='/')
    if os.getuid() != cfg['uid']:
        raise PermissionError('This command must run as the configured account')
    return run(argv, timeout=timeout, env=env, cwd='/')


def userctl(cfg, *args):
    return user_command(cfg, ['/usr/bin/systemctl', '--user', *args])


def reconcile(cfg):
    if 'workspace' not in cfg.get('components', ['workspace']):
        return {'started': False, 'reason': 'workspace-not-configured'}
    state = inspect_home(cfg)
    if not state['verified']:
        return {'started': False, 'reason': state['state']}
    if userctl(cfg, 'daemon-reload').returncode:
        return {'started': False, 'reason': 'user-manager-unavailable'}
    # Recheck after reload before asking systemd to run any home-backed command.
    if not inspect_home(cfg)['verified']:
        return {'started': False, 'reason': 'home-changed'}
    result = userctl(cfg, '--no-block', 'start', 'agentic-workspace.target')
    return {'started': result.returncode == 0,
            'reason': 'queued' if result.returncode == 0 else 'user-manager-unavailable'}


def stop_workspace(cfg):
    # Stop propagation belongs to PartOf= in the managed drop-ins.
    userctl(cfg, 'stop', 'agentic-workspace.target')


def prepare_locked(cfg):
    if os.geteuid() != 0:
        raise PermissionError('The locked-home guard requires root')
    state = inspect_home(cfg)
    if state['verified'] or state.get('protected'):
        return
    if cfg.get('home_policy') == 'mounted':
        raise RuntimeError('Enrolled home filesystem is unavailable; no fallback is allowed')
    entries = [e for e in mount_entries() if e['target'] == cfg['home']]
    if entries:
        raise RuntimeError('Refusing to cover an unexpected home mount')
    # This covers the legacy home, not the active eCryptfs mount. No old data is modified.
    result = run(['/usr/bin/mount', '--bind', cfg['locked_home'], cfg['home']])
    if result.returncode:
        raise RuntimeError('Cannot install locked-home guard')
    result = run(['/usr/bin/mount', '-o', 'remount,bind,ro,nosuid,nodev,noexec', cfg['home']])
    if result.returncode:
        run(['/usr/bin/umount', cfg['home']])
        raise RuntimeError('Cannot make locked-home guard read-only')
    if not inspect_home(cfg).get('protected'):
        raise RuntimeError('Locked-home guard verification failed')


def http_status(url, headers=None):
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return response.status, response.read(1024 * 1024)
    except urllib.error.HTTPError as error:
        return error.code, b''
    except (OSError, ValueError):
        return None, b''


def proxy_probe(cfg):
    try:
        # Parse a single value, never source user-controlled shell code.
        key = None
        for line in (Path(cfg['home']) / '.config/environment.d/cliproxy.conf').read_text().splitlines():
            if line.startswith('CLIPROXY_API_KEY='):
                key = line.split('=', 1)[1].strip().strip('\"\'')
        if not key:
            return {'state': 'missing-credential'}
        code, body = http_status(f"http://127.0.0.1:{cfg.get('proxy_port', 8317)}/v1/models", {'Authorization': 'Bearer ' + key})
        models = json.loads(body).get('data', []) if code == 200 else []
        return {'state': 'ready' if models else 'unavailable', 'model_count': len(models)}
    except (OSError, ValueError, TypeError):
        return {'state': 'unavailable'}


def tunnel_probe(cfg):
    """Probe only the T3-owned cloudflared loopback readiness endpoint."""
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        try:
            if p.stat().st_uid != cfg['uid'] or (p / 'comm').read_text().strip() != 'cloudflared':
                continue
            if '/t3code.service' not in (p / 'cgroup').read_text():
                continue
            args = (p / 'cmdline').read_bytes().split(b'\0')
            value = args[args.index(b'--metrics') + 1].decode()
            if not re.fullmatch(r'127\.0\.0\.1:[0-9]{1,5}', value):
                continue
            addresses = [value]
            if value.endswith(':0'):
                inodes = set()
                for fd in (p / 'fd').iterdir():
                    try:
                        link = os.readlink(fd)
                        if link.startswith('socket:['):
                            inodes.add(link[8:-1])
                    except OSError:
                        continue
                addresses = []
                for line in (p / 'net/tcp').read_text().splitlines()[1:]:
                    fields = line.split()
                    if fields[3] == '0A' and fields[9] in inodes:
                        host, port = fields[1].split(':')
                        if host == '0100007F':
                            addresses.append('127.0.0.1:' + str(int(port, 16)))
            ready = any(http_status('http://' + address + '/ready')[0] == 200 for address in addresses)
            return {'state': 'edge-connected' if ready else 'unavailable',
                    'external_authenticated_ui': 'unverified'}
        except (OSError, ValueError, IndexError):
            continue
    return {'state': 'unverified', 'external_authenticated_ui': 'unverified'}


def tailnet_probe():
    try:
        p = run(['/usr/bin/tailscale', 'status', '--json'], timeout=5)
        data = json.loads(p.stdout)
        own = data.get('Self') or {}
        expiry = own.get('KeyExpiry')
        remaining = None
        if expiry and not expiry.startswith('0001-'):
            remaining = (dt.datetime.fromisoformat(expiry.replace('Z', '+00:00')) -
                         dt.datetime.now(dt.timezone.utc)).total_seconds() / 3600
        online = data.get('BackendState') == 'Running' and own.get('Online') is True
        return {'state': 'online' if online else 'offline', 'expires_at': expiry,
                'hours_remaining': round(remaining, 1) if remaining is not None else None,
                'expiry_warning': remaining is not None and remaining < 24,
                'health_warning': bool(data.get('Health'))}
    except (OSError, ValueError, subprocess.TimeoutExpired, TypeError):
        return {'state': 'unverified'}


def checks(cfg):
    home = inspect_home(cfg)
    result = {'timestamp': dt.datetime.now(dt.timezone.utc).isoformat(), 'user': cfg['user'],
              'home': home, 'tailnet': tailnet_probe(), 'recovery': []}
    if not home['verified']:
        result.update(state='locked' if home['state'] == 'locked' else 'degraded',
                      proxy={'state': 'not-checked'}, t3={'state': 'not-checked'},
                      remote={'state': 'unverified', 'external_authenticated_ui': 'unverified'})
        result['recovery'].append(home['recovery'])
        return result
    result['proxy'] = proxy_probe(cfg)
    code, _ = http_status(f"http://127.0.0.1:{cfg.get('t3_port', 3773)}/")
    result['t3'] = {'state': 'ready' if code == 200 else 'unavailable'}
    result['remote'] = tunnel_probe(cfg)
    try:
        code, _ = http_status(cfg['connectivity_url']) if cfg.get('connectivity_url') else (None, b'')
        result['network'] = {'state': 'reachable' if code is not None and code < 500 else 'unverified'}
    except ValueError:
        result['network'] = {'state': 'unverified'}
    local = result['proxy']['state'] == result['t3']['state'] == 'ready'
    tailnet = result['tailnet']
    remote = result['remote']['state'] == 'edge-connected'
    result['state'] = ('ready' if local and remote and tailnet['state'] == 'online' and
                       not tailnet.get('expiry_warning') and not tailnet.get('health_warning') and
                       result['network']['state'] == 'reachable' else 'degraded')
    if not local:
        result['recovery'].append('agentic-startup start; inspect systemctl --user status cli-proxy-api t3code')
        try:
            states = userctl(cfg, 'show', *REQUIRED, '-p', 'ActiveState', '--value').stdout.splitlines()
            if any(s == 'activating' for s in states):
                result['state'] = 'starting'
        except (OSError, subprocess.TimeoutExpired):
            pass
    if tailnet.get('expiry_warning'):
        result['recovery'].append('Check tailscale status and supported browser/OIDC renewal; expired auth may require LAN or physical access')
    if not remote:
        result['recovery'].append('Inspect T3 Connect status; external authenticated UI remains unverified')
    return result


def configure_logging(cfg):
    folder = STATE_DIR / cfg['user']
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    logger = logging.getLogger('agentic-startup')
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(folder / 'startup.log', maxBytes=1024 * 1024, backupCount=3)
    handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
    logger.addHandler(handler)
    return logger, folder


class MountReconciler:
    """One state-machine tick, independent of the daemon loop for failure testing."""
    def __init__(self):
        self.identity = None
        self.manager = None
        self.reconciled = False
        self.retry_at = 0.0

    def tick(self, cfg, home, manager, now):
        identity = home.get('mount_id') if home['verified'] else None
        changed = (identity, manager) != (self.identity, self.manager)
        outcome = None
        if changed:
            if self.identity is not None and identity is None and 'workspace' in cfg.get('components',['workspace']):
                stop_workspace(cfg)
                outcome = 'home-unavailable; workspace-stopped'
            self.reconciled = False
            self.retry_at = 0.0
            self.identity, self.manager = identity, manager
        if identity is not None and 'workspace' in cfg.get('components',['workspace']) and not self.reconciled and now >= self.retry_at:
            result = reconcile(cfg)
            self.reconciled = result['started']
            self.retry_at = now + 30
            outcome = result['reason']
        return changed, outcome


def monitor(cfg):
    global STOP
    logger, folder = configure_logging(cfg)
    lock = os.open(folder / 'monitor.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    signal.signal(signal.SIGTERM, lambda *_: set_stop())
    signal.signal(signal.SIGINT, lambda *_: set_stop())
    reconciler = MountReconciler()
    last_state = None
    last_check = -float('inf')
    try:
        while not STOP:
            home = inspect_home(cfg)
            manager = run(['/usr/bin/systemctl', 'show', f"user@{cfg['uid']}.service",
                           '-p', 'InvocationID', '--value']).stdout.strip()
            now = time.monotonic()
            changed, outcome = reconciler.tick(cfg, home, manager, now)
            if changed:
                last_check = -float('inf')
            if outcome:
                logger.info('reconcile=%s', outcome)
            if now - last_check >= cfg.get('health_interval', 300) and 'health' in cfg.get('components', ['health']):
                # Credential-bearing probes run with the user's privileges, never as root.
                output = user_command(cfg, ['/usr/bin/python3', LIB, 'status', '--user', cfg['user'], '--json'], timeout=35)
                try:
                    state = json.loads(output.stdout)
                    if state['state'] not in ('locked', 'starting', 'ready', 'degraded'):
                        raise ValueError()
                    atomic_json(folder / 'latest-status.json', state)
                    if state['state'] != last_state:
                        logger.info('state=%s', state['state'])
                        last_state = state['state']
                except (ValueError, KeyError):
                    logger.warning('status-probe-failed')
                last_check = now
            for _ in range(cfg.get('poll_interval', 15)):
                if STOP:
                    break
                time.sleep(1)
    finally:
        # systemd orders this service before the home mount on startup and reverses at shutdown.
        if 'workspace' in cfg.get('components',['workspace']) and run(['/usr/bin/systemctl', 'is-system-running']).stdout.strip() == 'stopping':
            stop_workspace(cfg)
        os.close(lock)


def set_stop():
    global STOP
    STOP = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['status', 'start', 'unlock', 'check-home', 'guard', 'monitor', 'uninstall'])
    parser.add_argument('--user', default=pwd.getpwuid(os.getuid()).pw_name)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    cfg = load_config(args.user)
    if args.command in ('guard', 'monitor', 'uninstall') and os.geteuid() != 0:
        parser.error('This operation requires root')
    if args.command == 'guard':
        prepare_locked(cfg)
        return 0
    if args.command == 'monitor':
        monitor(cfg)
        return 0
    if args.command == 'check-home':
        return 0 if inspect_home(cfg)['verified'] else 1
    if args.command == 'uninstall':
        result = run(['/usr/bin/python3', '/usr/local/libexec/agentic-startup-install.py',
                      '--user', cfg['user'], '--uninstall'], timeout=120)
        print(result.stdout, end='')
        if result.returncode:
            print('Rollback stopped; inspect the private installer backup manifest.', file=sys.stderr)
        return result.returncode
    if args.command == 'unlock':
        if os.getuid() != cfg['uid'] or os.geteuid() == 0:
            parser.error('Unlock must run as the configured user, without sudo')
        if not inspect_home(cfg)['verified']:
            if cfg.get('home_policy') == 'mounted':
                print('Restore/unlock the enrolled filesystem through the OS, then run agentic-startup start.', file=sys.stderr)
                return 2
            if not sys.stdin.isatty():
                parser.error('Unlock requires an interactive terminal; passwords are never accepted as arguments')
            # No capture: the distro helper owns private terminal password input.
            result = subprocess.run(['/usr/bin/ecryptfs-mount-private'], cwd='/', check=False)
            if result.returncode:
                print('Home unlock failed; applications were not started.', file=sys.stderr)
                return 2
    if args.command in ('start', 'unlock'):
        result = reconcile(cfg)
        print(json.dumps(result) if args.json else ('Startup ' + result['reason']))
        return 0 if result['started'] else 2
    if os.geteuid() == 0:
        result = user_command(cfg, ['/usr/bin/python3', LIB, 'status', '--user', cfg['user'],
                                    *(['--json'] if args.json else [])], timeout=35)
        print(result.stdout, end='')
        return result.returncode
    state = checks(cfg)
    if args.json:
        print(json.dumps(state, indent=2))
    else:
        print(state['state'].upper() + ': local services + tunnel-edge checks; external authenticated UI unverified')
        for name in ('home', 'network', 'proxy', 't3', 'tailnet', 'remote'):
            print(f"{name}: {state.get(name, {}).get('state', 'not-checked')}")
        tailnet = state['tailnet']
        if tailnet.get('expires_at'):
            print(f"tailnet expiry: {tailnet['expires_at']} ({tailnet.get('hours_remaining')} hours)")
        for item in state['recovery']:
            print('Recovery: ' + item)
    return 0 if state['state'] == 'ready' else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError):
        # Never render subprocess output, response bodies, environment or exception details.
        print('Startup operation failed; inspect configuration and bounded private logs.', file=sys.stderr)
        sys.exit(2)
