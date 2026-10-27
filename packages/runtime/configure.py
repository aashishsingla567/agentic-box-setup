#!/usr/bin/python3
"""Provision a fresh loopback proxy/T3 runtime without copying host credentials."""
import json,os,platform,secrets,shutil,subprocess,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from provision_support import config,run,checked_release,safe_tar,managed_write


def install_proxy(cfg):
    version=cfg['runtime']['proxy_version']
    arch={'x86_64':'amd64','aarch64':'aarch64','arm64':'aarch64'}[platform.machine()]
    binary=Path.home()/'.local/bin/cli-proxy-api'
    version_file=binary.with_name('cli-proxy-api.agentic-version')
    if binary.exists() and (not version_file.exists() or version_file.read_text().strip()!=version):
        raise RuntimeError('Existing proxy binary preserved; select configure/verify or manage its upgrade explicitly')
    if not binary.exists():
        with tempfile.TemporaryDirectory(prefix='agentic-proxy-') as tmp:
            archive=Path(tmp)/'release.tar.gz'
            checked_release('router-for-me/CLIProxyAPI',version,f'CLIProxyAPI_{version}_linux_{arch}.tar.gz',archive)
            unpack=Path(tmp)/'unpack';unpack.mkdir();safe_tar(archive,unpack)
            matches=list(unpack.rglob('cli-proxy-api'))
            if len(matches)!=1:raise RuntimeError('Unexpected proxy release contents')
            binary.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(matches[0],binary);binary.chmod(0o755)
            version_file.write_text(version+'\n')


def configure_proxy(cfg):
    home=Path.home();env=home/'.config/environment.d/cliproxy.conf'
    if (home/'.config/cli-proxy-api/config.yaml').exists() and not env.exists():
        raise RuntimeError('Existing proxy configuration has no managed credential source; preserve its credentials and configure it manually')
    if env.exists():
        keys=[l.split('=',1)[1].strip().strip('\"\'') for l in env.read_text().splitlines() if l.startswith('CLIPROXY_API_KEY=')]
        if len(keys)!=1 or not keys[0]:raise RuntimeError('Existing proxy credential source is incomplete')
        key=keys[0]
    else:
        key=secrets.token_urlsafe(32)
        managed_write(env,('CLIPROXY_API_KEY='+key+'\n').encode())
    auth=home/'.config/cli-proxy-api/auths';auth.mkdir(mode=0o700,parents=True,exist_ok=True);auth.chmod(0o700)
    settings={'host':'127.0.0.1','port':cfg['runtime']['proxy_port'],'auth-dir':str(auth),
              'api-keys':[key],'usage-statistics-enabled':True,'routing':{'strategy':'round-robin'}}
    # JSON is a YAML subset; keeping a managed subset avoids rewriting unknown YAML.
    managed_write(home/'.config/cli-proxy-api/config.yaml',(json.dumps(settings,indent=2)+'\n').encode())
    unit=('[Unit]\nDescription=CLIProxyAPI local provider gateway\nStartLimitIntervalSec=0\n'
          '[Service]\nExecStart=%h/.local/bin/cli-proxy-api -config %h/.config/cli-proxy-api/config.yaml\n'
          'Restart=always\nRestartSec=5\n[Install]\nWantedBy=default.target\n')
    managed_write(home/'.config/systemd/user/cli-proxy-api.service',unit.encode(),0o644)
    run('systemctl','--user','daemon-reload');run('systemctl','--user','enable','cli-proxy-api.service')
    if cfg['runtime']['start_services']:run('systemctl','--user','start','cli-proxy-api.service')
    print('Proxy configured on loopback. Authenticate provider accounts explicitly; no key was printed.')


def configure_t3_dependencies(cfg):
    home=Path.home();port=cfg['runtime']['proxy_port']
    managed_write(home/'.local/libexec/agentic-box/proxy-ready.py',Path(__file__).with_name('proxy_ready.py').read_bytes(),0o755)
    gate=('[Unit]\nDescription=Authenticated local proxy readiness\n'
          'Requires=cli-proxy-api.service\nAfter=cli-proxy-api.service\n'
          '[Service]\nType=oneshot\nRemainAfterExit=yes\nTimeoutStartSec=130\n'
          f'ExecStart=/usr/bin/python3 %h/.local/libexec/agentic-box/proxy-ready.py --port {port}\n')
    managed_write(home/'.config/systemd/user/agentic-proxy-ready.service',gate.encode(),0o644)
    values=cfg['runtime']['limits']
    rows=[]
    for key,unit,suffix in [('memory_high_gib','MemoryHigh','G'),('memory_max_gib','MemoryMax','G'),
                            ('tasks_max','TasksMax',''),('cpu_quota_percent','CPUQuota','%')]:
        if values[key]:rows.append(f'{unit}={values[key]}{suffix}')
    # Empty/zero overrides leave native T3 and existing administrator limits in effect.
    managed_write(home/'.config/systemd/user/t3code.service.d/resources.conf',
                  ('[Service]\n'+'\n'.join(rows)+'\n').encode(),0o644)


def configure_t3(cfg):
    if not shutil.which('t3'):raise RuntimeError('Install dev-tools.t3code first')
    home=Path.home();unit=home/'.config/systemd/user/t3code.service'
    port=cfg['runtime']['t3_port']
    # Service installation is the supported T3 launcher path; never invent its ExecStart.
    if not unit.exists() and not cfg['runtime']['start_services']:
        raise RuntimeError('Missing T3 service: its supported installer starts it. Set runtime.start_services=true explicitly, or install it yourself first.')
    configure_t3_dependencies(cfg)
    dropin=('[Unit]\nRequires=agentic-proxy-ready.service\nAfter=agentic-proxy-ready.service\n[Service]\nEnvironmentFile=-%h/.config/environment.d/cliproxy.conf\n'
            f'Environment=T3CODE_PORT={port}\n'
            'Environment=PATH=%h/.local/share/agentic-box/node/current/bin:%h/.local/bin:%h/.opencode/bin:/usr/local/bin:/usr/bin:/bin\n')
    managed_write(home/'.config/systemd/user/t3code.service.d/provision.conf',dropin.encode(),0o644)
    if not unit.exists():
        env=os.environ.copy();env['T3CODE_PORT']=str(port)
        p=subprocess.run(['t3','service','install'],env=env,check=False)
        if p.returncode:raise RuntimeError('T3 service installation failed')
    run('systemctl','--user','daemon-reload');run('systemctl','--user','enable','t3code.service')
    if cfg['runtime']['start_services']:run('systemctl','--user','start','t3code.service')
    print('T3 uses its supported service launcher. Configure providers and Connect through their normal authentication flows.')


def verify(cfg,component):
    home=Path.home()
    expected=(home/'.local/bin/cli-proxy-api',home/'.config/cli-proxy-api/config.yaml') if component=='proxy' else (home/'.config/systemd/user/t3code.service',)
    if any(not p.exists() for p in expected):raise RuntimeError('Runtime prerequisites are incomplete')
    print(component+': installed/configured; account authentication is a separate readiness check')


def main():
    stage,component=sys.argv[1:3];cfg=config()
    if stage=='install':install_proxy(cfg)
    elif stage=='configure':(configure_proxy if component=='proxy' else configure_t3)(cfg)
    else:verify(cfg,component)

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,KeyError) as error:
        print('Runtime setup failed: '+(str(error) if isinstance(error,RuntimeError) else type(error).__name__),file=sys.stderr);sys.exit(1)
