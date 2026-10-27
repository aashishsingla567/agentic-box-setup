import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('startup', SOURCE / 'startup.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
spec = importlib.util.spec_from_file_location('installer', SOURCE / 'install.py')
i = importlib.util.module_from_spec(spec)
spec.loader.exec_module(i)
CFG = {'user': 'dev', 'uid': 1000, 'home': '/home/dev', 'backing': '/home/.ecryptfs/dev/.Private',
       'locked_home': '/var/lib/agentic-startup/locked-homes/dev', 'connectivity_url': 'https://control.example'}


def mounted(source='/home/dev/.Private', fs='ecryptfs', device='0:45', inode=17):
    entries = [dict(id=41, device=device, root='/', target='/home/dev', options=['rw'], fstype=fs, source=source)]
    def stat(path):
        return NS(st_dev=os.makedev(0, 45) if path == CFG['home'] and fs == 'ecryptfs' else os.makedev(8, 2),
                  st_ino=inode if path == CFG['home'] else 17, st_uid=1000)
    return entries, stat


def completed(code=0, out=''):
    return subprocess.CompletedProcess([], code, out, '')


class MountSafety(unittest.TestCase):
    def test_matching_inode_and_backing_required(self):
        entries, stat = mounted()
        self.assertTrue(s.inspect_home(CFG, entries, stat)['verified'])
        entries, stat = mounted(inode=18)
        self.assertEqual(s.inspect_home(CFG, entries, stat)['state'], 'wrong-mount')
        entries, stat = mounted(source='/different/source')
        self.assertFalse(s.inspect_home(CFG, entries, stat)['verified'])

    def test_wrong_filesystem_never_unlocked(self):
        entries, stat = mounted(fs='ext4')
        self.assertFalse(s.inspect_home(CFG, entries, stat, lambda p: NS(f_flag=0))['verified'])

    def test_hidden_home_without_mount_is_locked(self):
        _, stat = mounted()
        state = s.inspect_home(CFG, [], stat)
        self.assertEqual(state['state'], 'locked')
        self.assertFalse(state['protected'])

    def test_locked_bind_must_be_readonly(self):
        entries, stat = mounted(fs='ext4', device='8:2')
        entries[0]['root'] = CFG['locked_home']
        self.assertTrue(s.inspect_home(CFG, entries, stat, lambda p: NS(f_flag=os.ST_RDONLY))['protected'])
        self.assertFalse(s.inspect_home(CFG, entries, stat, lambda p: NS(f_flag=0))['protected'])

    def test_ro_encrypted_home_rejected(self):
        entries, stat = mounted()
        entries[0]['options'] = ['ro']
        self.assertFalse(s.inspect_home(CFG, entries, stat)['verified'])

    def test_mountinfo_escaped_paths(self):
        entries = s.mount_entries('42 1 0:45 / /home/dev\\040box rw - ecryptfs /home/dev\\040box/.Private rw\n')
        self.assertEqual(entries[0]['target'], '/home/dev box')

    def test_locked_reconcile_does_not_touch_user_manager(self):
        with patch.object(s, 'inspect_home', return_value={'verified': False, 'state': 'locked'}), patch.object(s, 'userctl') as ctl:
            self.assertFalse(s.reconcile(CFG)['started'])
            ctl.assert_not_called()

    def test_reconcile_rechecks_mount_and_never_restarts(self):
        with patch.object(s, 'inspect_home', side_effect=[{'verified': True}, {'verified': False}]), patch.object(s, 'userctl', return_value=completed()) as ctl:
            self.assertEqual(s.reconcile(CFG)['reason'], 'home-changed')
            self.assertEqual(ctl.call_count, 1)
        with patch.object(s, 'inspect_home', return_value={'verified': True}), patch.object(s, 'userctl', return_value=completed()) as ctl:
            for _ in range(2):
                self.assertTrue(s.reconcile(CFG)['started'])
            self.assertNotIn('restart', str(ctl.call_args_list))
            self.assertEqual(ctl.call_count, 4)

    def test_manager_failure_is_retryable(self):
        with patch.object(s, 'inspect_home', return_value={'verified': True}), patch.object(s, 'userctl', return_value=completed(1)):
            self.assertEqual(s.reconcile(CFG)['reason'], 'user-manager-unavailable')

    def test_guard_never_covers_active_encrypted_home(self):
        with patch.object(s.os, 'geteuid', return_value=0), patch.object(s, 'inspect_home', return_value={'verified': True}), patch.object(s, 'run') as run:
            s.prepare_locked(CFG)
            run.assert_not_called()

    def test_guard_refuses_unknown_mount(self):
        with patch.object(s.os, 'geteuid', return_value=0), patch.object(s, 'inspect_home', return_value={'verified': False}), patch.object(s, 'mount_entries', return_value=[{'target': CFG['home']}]), patch.object(s, 'run') as run:
            with self.assertRaises(RuntimeError):
                s.prepare_locked(CFG)
            run.assert_not_called()


class MonitorRecovery(unittest.TestCase):
    def test_manager_restart_reconciles_without_home_transition(self):
        monitor=s.MountReconciler()
        home={'verified':True,'mount_id':41}
        with patch.object(s,'reconcile',return_value={'started':True,'reason':'queued'}) as reconcile:
            monitor.tick(CFG,home,'manager-one',0)
            monitor.tick(CFG,home,'manager-one',15)
            self.assertEqual(reconcile.call_count,1)
            monitor.tick(CFG,home,'manager-two',30)
            self.assertEqual(reconcile.call_count,2)

    def test_retry_manager_failure_and_stop_on_mount_loss(self):
        monitor=s.MountReconciler()
        home={'verified':True,'mount_id':41}
        results=[{'started':False,'reason':'user-manager-unavailable'}, {'started':True,'reason':'queued'}]
        with patch.object(s,'reconcile',side_effect=results) as reconcile,patch.object(s,'stop_workspace') as stop:
            monitor.tick(CFG,home,'manager',0)
            monitor.tick(CFG,home,'manager',15)
            self.assertEqual(reconcile.call_count,1)
            monitor.tick(CFG,home,'manager',30)
            self.assertEqual(reconcile.call_count,2)
            monitor.tick(CFG,{'verified':False},'manager',45)
            stop.assert_called_once_with(CFG)
            monitor.tick(CFG,{'verified':False},'manager',60)
            stop.assert_called_once()


class Health(unittest.TestCase):
    def test_locked_checks_never_read_credentials_or_probe_apps(self):
        with patch.object(s, 'inspect_home', return_value={'verified': False, 'state': 'locked', 'recovery': 'unlock'}), patch.object(s, 'tailnet_probe', return_value={'state': 'online'}), patch.object(s, 'proxy_probe') as proxy, patch.object(s, 'http_status') as http:
            self.assertEqual(s.checks(CFG)['state'], 'locked')
            proxy.assert_not_called()
            http.assert_not_called()

    def base_checks(self, proxy='ready', tunnel='edge-connected', online='online'):
        return (patch.object(s, 'inspect_home', return_value={'verified': True, 'state': 'unlocked'}),
                patch.object(s, 'tailnet_probe', return_value={'state': online}),
                patch.object(s, 'proxy_probe', return_value={'state': proxy}),
                patch.object(s, 'tunnel_probe', return_value={'state': tunnel, 'external_authenticated_ui': 'unverified'}),
                patch.object(s, 'http_status', return_value=(200, b'')),
                patch.object(s, 'userctl', return_value=completed(out='active\n')))

    def test_functional_ready_does_not_claim_external_verification(self):
        a,b,c,d,e,f = self.base_checks()
        with a,b,c,d,e,f:
            state=s.checks(CFG)
            self.assertEqual(state['state'], 'ready')
            self.assertEqual(state['remote']['external_authenticated_ui'], 'unverified')

    def test_failed_proxy_or_network_does_not_restart_services(self):
        for kwargs in [{'proxy': 'unavailable'}, {'online': 'offline'}, {'tunnel': 'unavailable'}]:
            a,b,c,d,e,f=self.base_checks(**kwargs)
            with a,b,c,d,e,f as ctl:
                self.assertEqual(s.checks(CFG)['state'], 'degraded')
                self.assertNotIn('restart', str(ctl.call_args_list))

    def test_expiry_under_24_hours_warns(self):
        expiry=(s.dt.datetime.now(s.dt.timezone.utc)+s.dt.timedelta(hours=12)).isoformat()
        payload={'BackendState':'Running','Self':{'Online':True,'KeyExpiry':expiry}}
        with patch.object(s, 'run', return_value=completed(out=json.dumps(payload))):
            self.assertTrue(s.tailnet_probe()['expiry_warning'])
        payload['Self']['KeyExpiry']=None
        with patch.object(s, 'run', return_value=completed(out=json.dumps(payload))):
            self.assertFalse(s.tailnet_probe()['expiry_warning'])

    def test_proxy_response_and_credentials_are_not_returned(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'.config/environment.d'
            p.mkdir(parents=True)
            p.joinpath('cliproxy.conf').write_text('CLIPROXY_API_KEY=sentinel-do-not-log\n')
            with patch.object(s, 'http_status', return_value=(401, b'sentinel-do-not-log')):
                result=s.proxy_probe({**CFG,'home':folder})
                self.assertNotIn('sentinel', json.dumps(result))
                self.assertEqual(result['state'],'unavailable')


class InstallerSafety(unittest.TestCase):
    def test_snapshot_roundtrip_and_private_permissions(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'file'
            p.write_bytes(b'original')
            p.chmod(0o600)
            original=i.snapshot(p)
            i.write(p,b'replacement',0o644,os.getuid(),os.getgid())
            i.restore(p,original)
            self.assertEqual(p.read_bytes(),b'original')
            self.assertEqual(p.stat().st_mode&0o777,0o600)

    def test_symlink_destinations_and_parents_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            p.joinpath('real').mkdir()
            p.joinpath('alias').symlink_to(p/'real',target_is_directory=True)
            with self.assertRaises(RuntimeError):
                i.write(p/'alias/file',b'no')
            p.joinpath('file').symlink_to(p/'real/target')
            with self.assertRaises(RuntimeError):
                i.snapshot(p/'file')
            self.assertFalse((p/'real/target').exists())

    def test_atomic_status_does_not_follow_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            (p/'status.new').symlink_to(p/'victim')
            with self.assertRaises(OSError):
                s.atomic_json(p/'status',{'state':'ready'})
            self.assertFalse((p/'victim').exists())

    def test_changed_managed_file_blocks_rollback_before_service_actions(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            user=root/'dev'; user.mkdir()
            managed=root/'managed';managed.write_text('newer work')
            manifest={'files':{str(managed):{'installed_sha256':i.digest(b'installed'),'before':None}},'markers':{}}
            (user/'install-manifest.json').write_text(json.dumps(manifest))
            with patch.object(i,'BASE',root),patch.object(i,'command') as cmd:
                with self.assertRaises(RuntimeError):i.uninstall('dev')
                cmd.assert_not_called()
            self.assertEqual(managed.read_text(),'newer work')


class RollbackRoundtrip(unittest.TestCase):
    def test_restores_marker_and_files_without_stopping_apps(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            state=root/'dev';state.mkdir()
            original=root/'existing';original.write_text('before')
            previous=i.snapshot(original)
            original.write_text('installed')
            new=root/'added';new.write_text('installed-new')
            marker=root/'auto-umount'
            marker.write_bytes(b'')
            old_marker=i.snapshot(marker);marker.unlink()
            manifest={'files':{
                str(original):{'before':previous,'installed_sha256':i.digest(original.read_bytes())},
                str(new):{'before':None,'installed_sha256':i.digest(new.read_bytes())}},
                'markers':{str(marker):old_marker}}
            (state/'install-manifest.json').write_text(json.dumps(manifest))
            account=NS(pw_uid=os.getuid())
            with patch.object(i,'BASE',root),patch.object(i,'command',return_value=completed()) as cmd,patch.object(i.pwd,'getpwnam',return_value=account),patch.object(i.os,'fchown'):
                i.uninstall('dev')
                calls=[' '.join(c.args) for c in cmd.call_args_list]
                self.assertFalse(any('restart' in c or 'stop t3code' in c or 'stop cli-proxy' in c for c in calls))
            self.assertEqual(original.read_text(),'before')
            self.assertFalse(new.exists())
            self.assertTrue(marker.is_file())
            self.assertFalse((state/'install-manifest.json').exists())


if __name__=='__main__':unittest.main()
