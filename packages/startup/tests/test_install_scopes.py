"""Root-installer fixtures: all system paths and commands are redirected/stubbed."""
import importlib.util,json,os,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from contextlib import ExitStack
import subprocess
SOURCE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('scoped_installer',SOURCE/'install.py')
i=importlib.util.module_from_spec(spec);spec.loader.exec_module(i)

class ScopedInstaller(unittest.TestCase):
    def test_ssh_then_home_then_workspace_preserves_original_backups(self):
        with tempfile.TemporaryDirectory() as temp,ExitStack() as stack:
            root=Path(temp);home=root/'home/dev';home.mkdir(parents=True)
            (root/'system/etc/ssh').mkdir(parents=True)
            metadata=root/'system/home/.ecryptfs/dev/.ecryptfs';metadata.mkdir(parents=True)
            (metadata/'Private.mnt').write_text(str(home))
            (metadata/'auto-umount').write_bytes(b'original-marker')
            (home/'.ssh').mkdir();(home/'.ssh/authorized_keys').write_text('restrict ssh-ed25519 fixture comment\n')
            account=NS(pw_dir=str(home),pw_uid=os.getuid() or 1000,pw_gid=os.getgid())
            runtime=NS(REQUIRED=('cli-proxy-api.service','t3code.service'),OPTIONAL=(),
                       inspect_home=lambda cfg:{'verified':True},mount_entries=lambda:[])
            fake_spec=NS(loader=NS(exec_module=lambda module:None))
            calls=[]
            fail={'daemon':False}
            def cmd(*args,check=True):
                calls.append(args)
                if args[-1]=='daemon-reload' and fail['daemon']:
                    fail['daemon']=False
                    raise RuntimeError('injected daemon reload failure')
                output=''
                if 'is-active' in args:output='active' if args[-1]=='ssh.service' else 'inactive'
                if 'is-enabled' in args:output='disabled'
                if '-T' in args:output='authorizedkeysfile /etc/ssh/authorized_keys/%u .ssh/authorized_keys\n'
                if 'prefs' in args:output='{}'
                if 'systemd-escape' in args[0]:output='home-dev.mount'
                return subprocess.CompletedProcess(args,0,output,'')
            def path(*args):
                value=Path(*args)
                if any(str(value)==prefix or str(value).startswith(prefix+'/') for prefix in ('/etc','/usr/local','/home/.ecryptfs')):
                    return root/'system'/str(value).lstrip('/')
                return value
            for name in ('BASE','CONFIG','LIB'):
                stack.enter_context(patch.object(i,name,root/name.lower()))
            stack.enter_context(patch.object(i,'Path',path))
            stack.enter_context(patch.object(i,'command',side_effect=cmd))
            stack.enter_context(patch.object(i.pwd,'getpwnam',return_value=account))
            stack.enter_context(patch.object(i.importlib.util,'spec_from_file_location',return_value=fake_spec))
            stack.enter_context(patch.object(i.importlib.util,'module_from_spec',return_value=runtime))
            stack.enter_context(patch.object(i.os,'chown'))
            stack.enter_context(patch.object(i.os,'fchown'))
            original_chmod=Path.chmod
            def chmod(path,mode,*args,**kwargs):
                return original_chmod(path,0o755 if '/locked-homes/' in str(path) else mode,*args,**kwargs)
            stack.enter_context(patch.object(Path,'chmod',chmod))
            options={'components':['ssh'],'home_policy':'ecryptfs'}
            i.install(SOURCE,'dev',options)
            self.assertTrue((metadata/'auto-umount').exists())
            self.assertFalse((home/'.config/systemd/user/agentic-workspace.target').exists())
            self.assertFalse(any('enable-linger' in call for call in calls))
            self.assertFalse(any('start' in call and call[-1]=='agentic-startup@dev.service' for call in calls))
            key=path('/etc/ssh/authorized_keys/dev')
            self.assertEqual(key.read_text(),'restrict ssh-ed25519 fixture comment\n')
            manifest_path=root/'base/dev/install-manifest.json'
            original=json.loads(manifest_path.read_text())
            i.install(SOURCE,'dev',{'components':['home'],'home_policy':'ecryptfs'})
            self.assertFalse((metadata/'auto-umount').exists())
            self.assertEqual(json.loads((root/'config/dev.json').read_text())['components'],['home','ssh'])
            before=manifest_path.read_bytes()
            fail['daemon']=True
            with self.assertRaisesRegex(RuntimeError,'injected'):
                i.install(SOURCE,'dev',{'components':['home'],'home_policy':'ecryptfs'})
            self.assertFalse((metadata/'auto-umount').exists())
            self.assertEqual(manifest_path.read_bytes(),before)
            with self.assertRaisesRegex(RuntimeError,'application unit missing'):
                i.install(SOURCE,'dev',{'components':['workspace'],'home_policy':'ecryptfs'})
            self.assertEqual(manifest_path.read_bytes(),before)
            units=home/'.config/systemd/user';units.mkdir(parents=True)
            for name in runtime.REQUIRED:(units/name).write_text('[Service]\nExecStart=/bin/true\n')
            (home/'.local/bin').mkdir(parents=True);(home/'.local/bin/cli-proxy-api').write_text('fixture')
            (home/'.config/environment.d').mkdir();(home/'.config/environment.d/cliproxy.conf').write_text('fixture')
            i.install(SOURCE,'dev',{'components':['workspace'],'home_policy':'ecryptfs'})
            final=json.loads(manifest_path.read_text())
            for name,row in original['files'].items():self.assertEqual(final['files'][name]['before'],row['before'])
            self.assertEqual(final['markers'][str(metadata/'auto-umount')]['data'],'b3JpZ2luYWwtbWFya2Vy')
            self.assertFalse(any(call[-1] in runtime.REQUIRED and 'restart' in call for call in calls))
