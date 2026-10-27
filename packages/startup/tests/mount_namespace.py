#!/usr/bin/python3
"""Privileged integration test. Always run under unshare --mount --propagation private.
Uses a disposable UID, private passwd view, anonymous keyring and temporary encrypted data.
Never unmounts, reads keys from, or changes the real user's home.
"""
import importlib.util
import json
import os
from pathlib import Path
import pwd
import secrets
import subprocess
import tempfile

if os.geteuid() != 0 or os.readlink('/proc/self/ns/mnt') == os.readlink('/proc/1/ns/mnt'):
    raise SystemExit('Requires root in a private mount namespace')
source = Path(__file__).resolve().parents[1] / 'startup.py'
spec = importlib.util.spec_from_file_location('startup', source)
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
uid = 61000
while True:
    try:
        pwd.getpwuid(uid)
        uid += 1
    except KeyError:
        break

with tempfile.TemporaryDirectory(prefix='agentic-mount-test-', dir='/run') as folder:
    root = Path(folder)
    root.chmod(0o755)
    home, backing, metadata, locked = [root / x for x in ('home', 'backing', 'metadata', 'locked')]
    for p in (home, backing, metadata, locked):
        p.mkdir(mode=0o700)
        os.chown(p, uid, uid)
    legacy = home / 'legacy-do-not-touch'
    legacy.write_text('preserved')
    for name, target in [('.ecryptfs', metadata), ('.Private', backing)]:
        (locked / name).symlink_to(target)
    locked.chmod(0o555)
    (metadata / 'Private.mnt').write_text(str(home) + '\n')
    os.chown(metadata / 'Private.mnt', uid, uid)
    passwd = root / 'passwd'
    passwd.write_text(Path('/etc/passwd').read_text() + f'agentic-mount-test:x:{uid}:{uid}:Test:{home}:/bin/sh\n')
    subprocess.run(['mount', '--bind', str(passwd), '/etc/passwd'], check=True)
    cfg = {'user': 'agentic-mount-test', 'uid': uid, 'home': str(home),
           'backing': str(backing), 'locked_home': str(locked)}
    deny = ['setpriv', f'--reuid={uid}', f'--regid={uid}', '--clear-groups',
            '/usr/bin/python3', '-c', f"from pathlib import Path; Path({str(home / 'must-not-write')!r}).write_text('no')"]
    worker = root / 'worker.py'
    worker.write_text('''import subprocess,sys,re,json,os
from pathlib import Path
subprocess.run(['/usr/bin/keyctl','link','@u','@s'],check=True,capture_output=True)
password=sys.stdin.readline().strip()
p=subprocess.run(['/usr/bin/ecryptfs-add-passphrase','--fnek','-'],input=password+'\\n',text=True,capture_output=True)
if p.returncode:raise SystemExit('temporary keyring insertion failed')
sigs=re.findall(r'\\[([0-9a-f]{16})\\]',p.stdout)
if len(sigs)!=2:raise SystemExit('temporary signatures unavailable')
metadata=Path(sys.argv[1]);home=Path(sys.argv[2])
(metadata/'Private.sig').write_text('\\n'.join(sigs)+'\\n')
p=subprocess.run(['/sbin/mount.ecryptfs_private'],capture_output=True)
if p.returncode:raise SystemExit('distro mount helper: '+p.stderr.decode(errors='replace'))
(home/'encrypted-proof').write_text('works')
print(json.dumps({'mounted':True,'wrote':True}),flush=True)
sys.stdin.readline()
''')
    try:
        s.prepare_locked(cfg)
        assert s.inspect_home(cfg)['protected']
        assert subprocess.run(deny, capture_output=True).returncode != 0
        assert not legacy.exists()  # hidden by the guard, never removed
        child = subprocess.Popen(['setpriv', f'--reuid={uid}', f'--regid={uid}', '--clear-groups',
                                  'keyctl', 'session', '-', '/usr/bin/python3', str(worker), str(metadata), str(home)],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        child.stdin.write(secrets.token_hex(24) + '\n')
        child.stdin.flush()
        import select
        if not select.select([child.stdout], [], [], 20)[0]:
            child.kill()
            raise RuntimeError('Timed out waiting for isolated eCryptfs helper')
        line = child.stdout.readline()
        if not line:
            raise RuntimeError('Isolated helper failed: ' + child.stderr.read())
        assert json.loads(line)['mounted']
        assert s.inspect_home(cfg)['verified']
        child.stdin.write('\n')
        child.stdin.flush()
        child.communicate(timeout=10)
        subprocess.run(['umount', str(home)], check=True)
        assert s.inspect_home(cfg)['protected']
        assert subprocess.run(deny, capture_output=True).returncode != 0
        subprocess.run(['umount', str(home)], check=True)
        assert legacy.read_text() == 'preserved'
        assert not (home / 'must-not-write').exists()
        print('PASS: locked writes denied; real eCryptfs helper unlocks; relock reveals readonly guard; legacy data preserved')
    finally:
        # Only this test's temporary target; never the machine's real home.
        for _ in range(3):
            subprocess.run(['umount', str(home)], capture_output=True)
        subprocess.run(['umount', '/etc/passwd'], check=True)
