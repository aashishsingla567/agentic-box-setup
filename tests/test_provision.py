import copy,importlib.util,json,os,subprocess,sys,tarfile,tempfile,unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import provision as p
import provision_support as support


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
runtime=load('runtime_config','packages/runtime/configure.py')


class Config(unittest.TestCase):
    def setUp(self):self.cfg=copy.deepcopy(p.DEFAULTS)

    def test_layered_merges_and_lists_replace(self):
        cfg=p.merge(self.cfg,{'runtime':{'t3_port':4773},'packages':['storage']})
        cfg=p.override(cfg,'runtime.t3_port=5773')
        self.assertEqual(cfg['runtime']['t3_port'],5773)
        self.assertEqual(cfg['runtime']['proxy_port'],8317)
        self.assertEqual(cfg['packages'],['storage'])
        self.assertEqual(p.DEFAULTS['runtime']['t3_port'],3773)
        self.assertEqual(p.override(cfg,'storage.budgets_gib.build-artifacts=12')['storage']['budgets_gib'],{'build-artifacts':12})

    def test_invalid_types_and_unknown_keys_rejected(self):
        for assignment in ['runtime.t3_port=true','runtime.t3_port=80','runtime.t3_port=8317',
          'startup.poll_interval=0','storage.cleanup="yes"','packages=[{}]',
          'startup.home_policy="plaintext-key"','storage.budgets_gib.bad=-1',
          'runtime.limits.memory_max_gib=-5','runtime.proxy_version=8',
          'base.node_version="23"','network.login_server="http://host"']:
            with self.subTest(assignment=assignment),self.assertRaises(ValueError):p.validate(p.override(self.cfg,assignment))
        with self.assertRaises(ValueError):p.override(self.cfg,'runtime.unknown=12')

    def test_component_scope_and_deduplication(self):
        self.assertEqual(p.selections(self.cfg,'startup.ssh'),[('startup','ssh')])
        self.assertEqual(p.selections(self.cfg,'dev-tools.codex,dev-tools.codex'),[('dev-tools','codex')])
        self.assertEqual(p.selections(self.cfg,'storage.audit'),[('storage','audit')])
        for value in ['startup.invalid','invalid','startup.ssh.bad','']:
            with self.assertRaises(ValueError):p.selections(self.cfg,value)

    def test_startup_configures_after_all_selected_units(self):
        plan=p.plan(self.cfg,'runtime,storage,startup','configure',actual={'ID':'ubuntu'},arch='x86_64')
        packages=[s['package'] for s in plan['steps']]
        self.assertLess(packages.index('storage'),packages.index('startup'))

    def test_stage_order_prerequisites_and_no_implicit_installation(self):
        plan=p.plan(self.cfg,actual={'ID':'ubuntu'},arch='x86_64')
        order=[{'install':0,'configure':1,'verify':2}[s['stage']] for s in plan['steps']]
        self.assertEqual(order,sorted(order))
        self.assertFalse(plan['errors'])
        verify=p.plan(self.cfg,'runtime','verify',actual={'ID':'debian'},arch='aarch64')
        self.assertTrue(all(s['stage']=='verify' for s in verify['steps']))
        ssh=p.plan(self.cfg,'startup.ssh',actual={'ID':'ubuntu'},arch='x86_64')
        self.assertEqual({s['package'] for s in ssh['steps']},{'startup'})

    def test_os_arch_and_empty_plan_fail_closed(self):
        for host,arch in [('arch','x86_64'),('ubuntu','riscv64')]:
            self.assertTrue(p.plan(self.cfg,actual={'ID':host},arch=arch)['errors'])
        self.cfg['machine']['os']='linuxmint'
        self.assertTrue(p.plan(self.cfg,actual={'ID':'debian'},arch='x86_64')['errors'])
        self.cfg['machine']['os']='auto'
        self.cfg['dev-tools']['desktop']=True
        self.assertTrue(p.plan(self.cfg,'dev-tools.t3code',actual={'ID':'ubuntu'},arch='aarch64')['errors'])
        self.assertTrue(p.plan(self.cfg,'startup','install',actual={'ID':'ubuntu'},arch='x86_64')['errors'])

    def test_profiles_are_valid(self):
        for path in (ROOT/'config/profiles').glob('*.json'):p.validate(p.merge(self.cfg,json.loads(path.read_text())))

    def test_plan_never_dispatches_installers(self):
        with tempfile.TemporaryDirectory() as temp:
            env={**os.environ,'HOME':temp}
            result=subprocess.run([str(ROOT/'install.sh'),'--profile','headless-heavy','--json'],env=env,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue(json.loads(result.stdout)['steps'])
            self.assertEqual(list(Path(temp).iterdir()),[])

    def test_error_does_not_echo_secret_values(self):
        result=subprocess.run([str(ROOT/'install.sh'),'--set','runtime.t3_port="sentinel-secret"'],text=True,capture_output=True)
        self.assertEqual(result.returncode,2)
        self.assertNotIn('sentinel-secret',result.stdout+result.stderr)

    def test_data_env_is_never_sourced(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);victim=folder/'victim'
            folder.joinpath('.env').write_text(f'TAILSCALE_AUTHKEY=$(touch {victim})\n')
            with patch.object(p,'ROOT',folder),patch.dict(os.environ,{},clear=True):
                env=p.environment(self.cfg)
                self.assertIn('$(touch ',env['TAILSCALE_AUTHKEY'])
            self.assertFalse(victim.exists())
            folder.joinpath('.env').write_text('PATH=malicious\n')
            with patch.object(p,'ROOT',folder),self.assertRaises(ValueError):p.environment(self.cfg)

    def test_startup_configuration_is_one_transaction(self):
        steps=p.plan(self.cfg,'startup','configure',actual={'ID':'linuxmint'},arch='x86_64')['steps']
        calls=[]
        def runner(argv,**kwargs):calls.append((argv,kwargs));return subprocess.CompletedProcess(argv,0)
        p.execute_steps(steps,self.cfg,{},runner)
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0][1]['env']['AGENTIC_STARTUP_COMPONENTS'],'ssh,home,workspace,health')

    def test_failure_stops_remaining_steps(self):
        steps=p.plan(self.cfg,'dev-tools.codex,dev-tools.t3code','install',actual={'ID':'linuxmint'},arch='x86_64')['steps']
        calls=[]
        def runner(argv,**kwargs):calls.append(argv);return subprocess.CompletedProcess(argv,1)
        with self.assertRaises(RuntimeError):p.execute_steps(steps,self.cfg,{},runner)
        self.assertEqual(len(calls),1)


class FileSafety(unittest.TestCase):
    def test_managed_updates_and_unmanaged_preservation(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'config'
            path.write_bytes(b'user data')
            with self.assertRaises(RuntimeError):support.managed_write(path,b'new')
            self.assertEqual(path.read_bytes(),b'user data');path.unlink()
            support.managed_write(path,b'first');support.managed_write(path,b'second')
            self.assertEqual(path.read_bytes(),b'second')
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            path.write_bytes(b'changed')
            with self.assertRaises(RuntimeError):support.managed_write(path,b'third')
            path.unlink();path.symlink_to(Path(temp)/'victim')
            with self.assertRaises(RuntimeError):support.managed_write(path,b'no')
            self.assertFalse(Path(temp,'victim').exists())

    def test_tar_path_traversal_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            archive=Path(temp)/'bad.tar';target=Path(temp)/'out';target.mkdir()
            with tarfile.open(archive,'w') as tf:
                info=tarfile.TarInfo('../victim');info.size=1;tf.addfile(info,BytesIO(b'x'))
            with self.assertRaises(RuntimeError):support.safe_tar(archive,target)
            self.assertFalse(Path(temp,'victim').exists())

    def test_missing_t3_service_never_starts_without_explicit_choice(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(runtime.Path,'home',return_value=Path(temp)),patch.object(runtime.shutil,'which',return_value='/bin/t3'),patch.object(runtime,'run') as run,patch.object(runtime.subprocess,'run') as subprocess_run:
            cfg=copy.deepcopy(p.DEFAULTS)
            with self.assertRaisesRegex(RuntimeError,'start_services=true'):runtime.configure_t3(cfg)
            run.assert_not_called();subprocess_run.assert_not_called()

    def test_existing_t3_service_uses_start_never_restart(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(runtime.Path,'home',return_value=Path(temp)),patch.object(runtime.shutil,'which',return_value='/bin/t3'),patch.object(runtime,'run') as run,patch.object(runtime.subprocess,'run') as subprocess_run:
            unit=Path(temp)/'.config/systemd/user/t3code.service';unit.parent.mkdir(parents=True);unit.write_text('existing')
            cfg=copy.deepcopy(p.DEFAULTS);cfg['runtime']['start_services']=True
            runtime.configure_t3(cfg)
            subprocess_run.assert_not_called()
            self.assertEqual(unit.read_text(),'existing')
            self.assertNotIn('restart',str(run.call_args_list))
            self.assertIn('agentic-proxy-ready.service',unit.with_name('t3code.service.d').joinpath('provision.conf').read_text())



class StoragePolicy(unittest.TestCase):
    def test_cleanup_off_precedes_enabling_overdue_timers(self):
        storage=load('storage_config','packages/storage/configure.py')
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'dev-storage/config.json';path.parent.mkdir()
            path.write_text(json.dumps({'cleanup_enabled':True,'budgets_gib':{},'workload':{'keep':'existing'}}))
            cfg=copy.deepcopy(p.DEFAULTS)
            def install(*args):
                self.assertFalse(json.loads(path.read_text())['cleanup_enabled'])
            with patch.dict(os.environ,{'XDG_CONFIG_HOME':temp}),patch.object(storage,'config',return_value=cfg),patch.object(storage.sys,'argv',['configure.py','configure','audit']),patch.object(storage,'run',side_effect=install):
                storage.main()
            self.assertEqual(json.loads(path.read_text())['workload'],{'keep':'existing'})
            self.assertFalse(json.loads(path.read_text())['cleanup_enabled'])

if __name__=='__main__':unittest.main()
