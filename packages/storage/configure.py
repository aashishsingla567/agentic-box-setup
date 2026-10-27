#!/usr/bin/python3
import json,os,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from provision_support import config,run
import tempfile

def save_policy(path,current):
    if path.is_symlink():raise RuntimeError('Storage configuration symlink preserved; manage its target explicitly')
    fd,name=tempfile.mkstemp(prefix='.agentic-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as out:
            os.fchmod(out.fileno(),0o600);json.dump(current,out,indent=2);out.write('\n')
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def main():
    stage,component=sys.argv[1:3];cfg=config();storage=cfg['storage']
    if stage=='verify' and component=='system':
        if not Path('/etc/systemd/system/dev-storage-system-audit.timer').is_file():raise RuntimeError('System storage policy is missing')
        print('System storage audit timer installed; inspect systemctl status dev-storage-system-audit.timer');return
    if stage=='verify' and component=='limits':
        run('systemctl','--user','show','app-t3code-agents.slice','-p','CPUQuotaPerSecUSec','-p','CPUWeight','-p','IOWeight','-p','MemoryHigh','-p','MemoryMax');return
    if stage=='verify':
        result=subprocess.run([str(Path.home()/'.local/bin/dev-storage'),'status'],check=False)
        if result.returncode not in (0,1):raise RuntimeError('Storage status command failed')
        return
    if component=='audit':
        path=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'dev-storage/config.json'
        # Disable deletion before any installer can enable a persistent overdue timer.
        if path.exists() and not storage['cleanup']:
            current=json.loads(path.read_text());current['cleanup_enabled']=False;save_policy(path,current)
        args=['bash',str(Path(__file__).with_name('install.sh')),'--profile',storage['profile']]
        if not storage['timers']:args.append('--no-timers')
        if storage['cleanup']:args.append('--enable-cleanup')
        run(*args)
        path=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'dev-storage/config.json'
        current=json.loads(path.read_text())
        current['budgets_gib'].update(storage['budgets_gib'])
        current['cleanup_enabled']=storage['cleanup']
        # Modify only selected policy fields and preserve utility-owned audit/runtime state.
        save_policy(path,current)
        if not storage['timers']:
            for timer in ('dev-storage-check.timer','dev-storage-audit.timer','dev-storage-maintain.timer'):
                loaded=subprocess.run(['systemctl','--user','show',timer,'-p','LoadState','--value'],capture_output=True,text=True)
                if loaded.stdout.strip()=='loaded':run('systemctl','--user','disable','--now',timer)

    elif component=='limits':
        loaded=subprocess.run(['systemctl','--user','show','app-t3code-agents.slice','-p','LoadState','--value'],capture_output=True,text=True)
        if loaded.stdout.strip()!='loaded':raise RuntimeError('Start an agent in T3 first; its native agents slice is required')
        limits=storage['agent_limits']
        quota=limits['cpu_quota_percent'] or max(1,(os.cpu_count() or 1)-1)*100
        run('systemctl','--user','set-property','app-t3code-agents.slice',f'CPUQuota={quota}%',
            f"CPUWeight={limits['cpu_weight']}",f"IOWeight={limits['io_weight']}")
        print('Agent CPU/I/O policy applied. Native T3 aggregate memory limits retained; no agents restarted.')
    else:
        run('bash',str(Path(__file__).with_name('install.sh')),'--fetch-only')
        rev='55c1a410a2cf9eb004ba4a35a414e5ecc27e9198'
        source=Path(os.environ.get('DEV_STORAGE_SOURCE',str(Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'agentic-box-setup/sources/dev-storage'/rev)))
        run('sudo','bash',str(source/'linux/install-system.sh'))
if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError):print('Storage scope failed; check its prerequisites.',file=sys.stderr);sys.exit(1)
