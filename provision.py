#!/usr/bin/python3
"""Layered configuration and scoped Linux provisioning. Planning never executes installers."""
import argparse
import copy
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
BUDGETS = ('os-apps','system-snapshots','swap','project-source-and-data','git-history',
           'project-dependencies','build-artifacts','toolchains','package-caches','other-caches',
           'agent-state','containers','browser-runtimes','application-state','personal-files-and-downloads',
           'system-logs-and-caches','model-weights','virtual-machines','android-sdk-and-emulators',
           'encrypted-overhead-and-other')
TOOLS = ('opencode','codex','claude-code','cursor','antigravity','t3code','tailscale')
COMPONENTS = {
 'base': ('packages','node'), 'dev-tools': TOOLS, 'runtime': ('proxy','t3'),
 'startup': ('ssh','home','workspace','health'), 'storage': ('audit','system','limits'),
 'sleepless': ('cli','power'), 'rig-panel': ('ui',),
}
STAGES = {'base': ('install',), 'dev-tools': ('install','verify'),
          'runtime': ('install','configure','verify'), 'startup': ('configure','verify'),
          'storage': ('configure','verify'), 'sleepless': ('configure','verify'),
          'rig-panel': ('install','verify')}
OS_CHOICES = {
 'linuxmint': ('Linux Mint 22.3 Cinnamon', 'https://linuxmint.com/download.php'),
 'ubuntu': ('Ubuntu 24.04 LTS desktop/server', 'https://ubuntu.com/download'),
 'debian': ('Debian stable (12 or newer)', 'https://www.debian.org/distrib/'),
}
DEFAULTS = json.loads((ROOT/'config/defaults.json').read_text())


def merge(base, overlay, path=''):
    if not isinstance(overlay,dict):raise ValueError('Config root must be an object')
    result=copy.deepcopy(base)
    for key,value in overlay.items():
        if key not in base and path not in ('storage.budgets_gib.',):
            raise ValueError('Unknown setting: '+path+key)
        if isinstance(base.get(key),dict):
            if not isinstance(value,dict):raise ValueError(path+key+' must be an object')
            result[key]=merge(base[key],value,path+key+'.')
        else:result[key]=copy.deepcopy(value)
    return result


def override(cfg, assignment):
    if '=' not in assignment:raise ValueError('--set expects key=value')
    key,value=assignment.split('=',1)
    try:value=json.loads(value)
    except json.JSONDecodeError:pass
    tree=value
    for part in reversed(key.split('.')):tree={part:tree}
    return merge(cfg,tree)


def validate(cfg):
    def enum(path, choices):
        node=cfg
        for k in path.split('.'):node=node[k]
        if node not in choices:raise ValueError(path+' must be one of '+', '.join(choices))
    if type(cfg['version']) is not int or cfg['version']!=1:raise ValueError('Unsupported config version')
    enum('machine.os',('auto',*OS_CHOICES))
    enum('machine.role',('headless','desktop'))
    enum('storage.profile',('heavy','balanced'))
    enum('startup.home_policy',('auto','ecryptfs','mounted'))
    enum('sleepless.mode',('unchanged','always-on','normal'))
    if not isinstance(cfg['packages'],list) or any(not isinstance(x,str) or x not in COMPONENTS for x in cfg['packages']):raise ValueError('Invalid package selection')
    for package,known in COMPONENTS.items():
        values=cfg[package]['components']
        if not isinstance(values,list) or any(not isinstance(x,str) or x not in known for x in values):raise ValueError('Invalid '+package+' components')
    for package,key in [('dev-tools','desktop'),('runtime','start_services'),('startup','keep_unlocked'),('storage','timers'),('storage','cleanup'),('network','join')]:
        if type(cfg[package][key]) is not bool:raise ValueError(package+'.'+key+' must be a boolean')
    for key in ('proxy_port','t3_port'):
        if type(cfg['runtime'][key]) is not int or not 1024<=cfg['runtime'][key]<=65535:raise ValueError('Runtime ports must be integers from 1024 through 65535')
    if cfg['runtime']['proxy_port']==cfg['runtime']['t3_port']:raise ValueError('Proxy and T3 ports must differ')
    limits=cfg['runtime']['limits']
    for key,value in limits.items():
        if type(value) is not int or not 0<=value<=100000:raise ValueError('Invalid runtime limit '+key)
    if limits['memory_high_gib'] and limits['memory_max_gib'] and limits['memory_high_gib']>limits['memory_max_gib']:
        raise ValueError('MemoryHigh must not exceed MemoryMax')
    for key,low,high in [('poll_interval',5,300),('health_interval',30,3600)]:
        n=cfg['startup'][key]
        if type(n)is not int or not low<=n<=high:raise ValueError('Invalid startup.'+key)
    for section, key in [('base','node_version'),('runtime','proxy_version')]:
        if not isinstance(cfg[section][key],str) or not re.fullmatch(r'\d+(\.\d+\.\d+)?',cfg[section][key]):raise ValueError('Invalid '+section+'.'+key)
    if not isinstance(cfg['storage']['budgets_gib'],dict):raise ValueError('storage.budgets_gib must be an object')
    if '.' not in cfg['runtime']['proxy_version']:raise ValueError('runtime.proxy_version must be an exact release')
    major=int(cfg['base']['node_version'].split('.')[0])
    parts=[int(part) for part in cfg['base']['node_version'].split('.')]
    if major < 22 or major == 23 or len(parts)>1 and (major==22 and parts[1]<16 or major==24 and parts[1]<10):
        raise ValueError('Use Node 22.16+, 24.10+ or newer')
    for key,value in cfg['dev-tools']['versions'].items():
        if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9._-]+',value):raise ValueError('Invalid tool version '+key)
    for key,value in cfg['storage']['budgets_gib'].items():
        if not isinstance(key,str) or key not in BUDGETS or type(value) not in (int,float) or not 0<=value<=100000:raise ValueError('Invalid storage budget')
    for key,value in cfg['storage']['agent_limits'].items():
        low,high=(0,100000) if key=='cpu_quota_percent' else (1,10000)
        if type(value) is not int or not low<=value<=high:raise ValueError('Invalid storage.agent_limits.'+key)
    server=cfg['network']['login_server']
    if not isinstance(server,str) or server and not re.fullmatch(r'https://[A-Za-z0-9.:-]+/?',server):raise ValueError('login_server must be an HTTPS origin')
    if not isinstance(cfg['startup']['authorized_keys'],str) or not cfg['startup']['authorized_keys']:raise ValueError('authorized_keys must be a path')
    return cfg


def os_info(path=Path('/etc/os-release')):
    rows={}
    for line in path.read_text().splitlines():
        if '=' in line:
            k,v=line.split('=',1);rows[k]=v.strip('"\'')
    return rows


def selections(cfg, only):
    chosen=[]
    for selector in (only.split(',') if only is not None else cfg['packages']):
        parts=selector.split('.')
        package=parts[0]
        if package not in COMPONENTS or len(parts)>2:raise ValueError('Unknown selector: '+selector)
        components=[parts[1]] if len(parts)==2 else cfg[package]['components']
        if any(c not in COMPONENTS[package] for c in components):raise ValueError('Unknown selector: '+selector)
        for component in components:
            if (package,component) not in chosen:chosen.append((package,component))
    order=list(COMPONENTS)
    return sorted(chosen,key=lambda pair:(order.index(pair[0]),COMPONENTS[pair[0]].index(pair[1])))


def plan(cfg, only=None, stage='all', actual=None, arch=None):
    selected=selections(cfg,only)
    actual=actual or os_info()
    arch=arch or platform.machine()
    problems=[]
    if sys.version_info < (3,10):problems.append('Python 3.10 or newer is required')
    if actual.get('ID') not in OS_CHOICES:problems.append('Supported provisioning hosts are Linux Mint, Ubuntu and Debian; other distributions need adapters')
    if cfg['machine']['os']!='auto' and cfg['machine']['os']!=actual.get('ID'):problems.append('Selected OS differs from installed OS; complete the OS installation handoff first')
    if arch not in ('x86_64','aarch64','arm64'):problems.append('Unsupported CPU architecture: '+arch)
    if arch!='x86_64' and any(p=='dev-tools' and cfg['dev-tools']['desktop'] and c in ('cursor','antigravity','t3code') for p,c in selected):problems.append('Selected desktop/Antigravity assets currently require x86_64')
    steps=[]
    for p,c in selected:
        for action in STAGES[p]:
            if stage!='all' and action!=stage:continue
            if p=='runtime' and action=='install' and c=='t3':continue # dev-tools owns its binary
            if p=='sleepless' and c=='power' and cfg[p]['mode']=='unchanged':continue
            steps.append({'package':p,'component':c,'stage':action})
    # Keep global stages ordered: provision all binaries before configuration/probes.
    # Startup discovers unit files/timers from every selected configuration scope.
    steps.sort(key=lambda row:(('install','configure','verify').index(row['stage']),row['package']=='startup'))
    if not steps:problems.append('The selection has no actions in this stage')
    return {'os':actual.get('ID'),'architecture':arch,'steps':steps,'errors':problems,
            'notes':['Selection is additive: unselected packages are never removed.',
                     'Provider/OIDC authentication and disk installation are explicit setup steps.',
                     'Startup components always include their required mount-safety checks.',
                     'Existing startup selections are retained when adding components.',
                     'Missing T3 service installation starts T3 and requires runtime.start_services=true.']}


def environment(cfg):
    env=os.environ.copy()
    # Parse a narrow data-only .env; never execute shell from configuration.
    path=ROOT/'.env'
    if path.exists():
        allowed={'TAILSCALE_AUTHKEY'}
        for line in path.read_text().splitlines():
            if not line.strip() or line.lstrip().startswith('#'):continue
            k,sep,v=line.partition('=')
            if not sep or k not in allowed:raise ValueError('.env permits only TAILSCALE_AUTHKEY; use JSON for settings')
            env.setdefault(k,v.strip().strip('"\''))
    env.update(AGENTIC_CONFIG_JSON=json.dumps(cfg),AGENTIC_DESKTOP=str(cfg['dev-tools']['desktop']).lower(),
               CURSOR_VERSION=cfg['dev-tools']['versions']['cursor'],CODEX_VERSION=cfg['dev-tools']['versions']['codex'],
               ANTIGRAVITY_APP_VERSION=cfg['dev-tools']['versions']['antigravity_app'],
               ANTIGRAVITY_APP_BUILD=cfg['dev-tools']['versions']['antigravity_app_build'],
               ANTIGRAVITY_IDE_VERSION=cfg['dev-tools']['versions']['antigravity_ide'],
               ANTIGRAVITY_IDE_BUILD=cfg['dev-tools']['versions']['antigravity_ide_build'],
               TAILSCALE_LOGIN_SERVER=cfg['network']['login_server'],AGENTIC_TAILSCALE_JOIN=str(cfg['network']['join']).lower())
    env['PATH']=str(Path.home()/'.local/share/agentic-box/node/current/bin')+':'+str(Path.home()/'.local/bin')+':'+str(Path.home()/'.opencode/bin')+':'+env.get('PATH','')
    env['NPM_CONFIG_PREFIX']=str(Path.home()/'.local')
    return env


def execute_step(step,cfg,env,runner=subprocess.run):
    p,c,stage=(step[k] for k in ('package','component','stage'))
    if p=='dev-tools':
        if stage=='install':argv=['bash',str(ROOT/'packages/dev-tools/tools'/f'{c}.sh')]
        else:argv=['/usr/bin/python3',str(ROOT/'packages/base/configure.py'),'verify-tool',c]
    elif p in ('base','runtime','storage','sleepless','rig-panel'):
        argv=['/usr/bin/python3',str(ROOT/'packages'/p/'configure.py'),stage,c]
    else:
        argv=['/usr/bin/python3',str(ROOT/'packages/startup/configure.py'),stage,c]
    env=env.copy()
    if not (p=='dev-tools' and c=='tailscale' and stage=='install'):
        env.pop('TAILSCALE_AUTHKEY',None)
    result=runner(argv,env=env,cwd=ROOT,check=False)
    if result.returncode:raise RuntimeError(f'{p}.{c} {stage} failed; remaining steps were not run')


def execute_steps(steps,cfg,env,runner=subprocess.run):
    handled=set()
    for step in steps:
        if step['package']=='startup':
            if step['stage'] in handled:continue
            handled.add(step['stage'])
            env=env.copy()
            env['AGENTIC_STARTUP_COMPONENTS']=','.join(s['component'] for s in steps
                if s['package']=='startup' and s['stage']=='configure')
        execute_step(step,cfg,env,runner)


def wizard(output):
    if not sys.stdin.isatty():raise ValueError('--wizard requires an interactive terminal')
    def choose(prompt,choices,default):
        print(prompt+' ['+'/'.join(choices)+']')
        value=input('> ').strip() or default
        if value not in choices:raise ValueError('Invalid choice')
        return value
    target=choose('Target operating system',list(OS_CHOICES),'linuxmint')
    profile=choose('Machine profile',['minimal','headless-heavy','desktop','existing-machine'],'headless-heavy')
    cfg=json.loads((ROOT/'config/profiles'/f'{profile}.json').read_text())
    cfg.setdefault('machine',{})['os']=target
    selected=input('Packages (comma separated; blank keeps profile): ').strip()
    if selected:cfg['packages']=selected.split(',')
    validate(merge(DEFAULTS,cfg))
    output=Path(output).expanduser()
    output.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:json.dump(cfg,f,indent=2);f.write('\n')
    print('Saved '+str(output)+'; no packages were installed.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',action='append',default=[])
    parser.add_argument('--profile',choices=['minimal','headless-heavy','desktop','existing-machine'])
    parser.add_argument('--set',dest='overrides',action='append',default=[])
    parser.add_argument('--only',help='comma-separated packages or package.component selectors')
    parser.add_argument('--tools',help='shorthand for --only dev-tools.TOOL,...')
    parser.add_argument('--stage',choices=['all','install','configure','verify'],default='all')
    parser.add_argument('--plan',action='store_true')
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--json',action='store_true')
    parser.add_argument('--show-config',action='store_true')
    parser.add_argument('--list',action='store_true')
    parser.add_argument('--wizard',action='store_true')
    parser.add_argument('--output',default='machine.local.json')
    parser.add_argument('--os-guide',action='store_true')
    args=parser.parse_args()
    if args.plan and args.apply:parser.error('--plan and --apply are mutually exclusive')
    if args.list:
        print(json.dumps(COMPONENTS,indent=2) if args.json else '\n'.join(p+': '+', '.join(c) for p,c in COMPONENTS.items()));return 0
    if args.wizard:wizard(args.output);return 0
    cfg=copy.deepcopy(DEFAULTS)
    if args.profile:cfg=merge(cfg,json.loads((ROOT/'config/profiles'/f'{args.profile}.json').read_text()))
    for name in args.config:cfg=merge(cfg,json.loads(Path(name).expanduser().read_text()))
    for value in args.overrides:cfg=override(cfg,value)
    validate(cfg)
    if args.show_config:print(json.dumps(cfg,indent=2));return 0
    if args.os_guide:
        target=cfg['machine']['os']
        if target=='auto':raise ValueError('Choose machine.os before requesting an OS guide')
        name,url=OS_CHOICES[target]
        print(name+'\nOfficial installation media: '+url+'\nVerify the ISO signature/checksum, back up data, and install the OS using its installer.\nChoose storage/encryption there; this repo never formats disks. Create a non-root sudo user.\nInstall git, python3 and ca-certificates, clone this repo, restore this config, then run --plan and --apply.\nSee docs/NEW-MACHINE.md for exact commands and encryption/recovery requirements.')
        return 0
    only=args.only
    if args.tools:
        if only:raise ValueError('Use either --only or --tools')
        only=','.join('dev-tools.'+x for x in args.tools.split(','))
    result=plan(cfg,only,args.stage)
    if args.json:print(json.dumps(result,indent=2))
    else:
        print(f"Host: {result['os']} / {result['architecture']}")
        for row in result['steps']:print(f"{row['stage']:10} {row['package']}.{row['component']}")
        for error in result['errors']:print('BLOCKED: '+error)
        if not args.apply and not (args.stage=='verify' and not args.plan):print('Read-only plan. Add --apply to execute exactly these scopes.')
    if result['errors']:return 2
    if args.apply or args.stage=='verify' and not args.plan:
        if os.geteuid()==0:raise ValueError('Run as the workspace user, not root; individual system actions use sudo')
        env=environment(cfg)
        execute_steps(result['steps'],cfg,env)
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,ValueError,RuntimeError,json.JSONDecodeError) as e:
        # Do not render JSON values, environment, credentials or subprocess traces.
        print('Setup failed: '+(str(e) if isinstance(e,(ValueError,RuntimeError)) else type(e).__name__),file=sys.stderr)
        sys.exit(2)
