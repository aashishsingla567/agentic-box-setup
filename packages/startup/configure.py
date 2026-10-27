#!/usr/bin/python3
"""Bridge selected startup components to one root-owned installation transaction."""
import json,os,pwd,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from provision_support import config,run


def main():
    stage,component=sys.argv[1:3]
    cfg=config();user=pwd.getpwuid(os.getuid()).pw_name
    if stage=='verify':
        # Read-only functional status may return 2 for locked/degraded; expose that
        # condition without pretending provisioning itself failed or repairing apps.
        p=subprocess.run(['/usr/local/bin/agentic-startup','status','--json'],capture_output=True,text=True)
        if not p.stdout:raise RuntimeError('Startup not configured; run its configure stage first')
        status=json.loads(p.stdout)
        print('Startup readiness: '+status['state']+' (external authenticated UI remains unverified)')
        if p.returncode not in (0,2):raise RuntimeError('Startup verification failed')
        return
    components=os.environ.get('AGENTIC_STARTUP_COMPONENTS',component).split(',')
    options={'components':components,'home_policy':cfg['startup']['home_policy']}
    # Adding SSH/home must not reset previously configured runtime ports or health policy.
    if set(components)&{'home','workspace'}:
        options['keep_unlocked']=cfg['startup']['keep_unlocked']
        options['poll_interval']=cfg['startup']['poll_interval']
    if set(components)&{'workspace','health'}:
        options['health_interval']=cfg['startup']['health_interval']
        options.update({key:cfg['runtime'][key] for key in ('proxy_port','t3_port')})
    if 'ssh' in components:
        options['authorized_keys']=str(Path(cfg['startup']['authorized_keys']).expanduser().absolute())
    run('sudo','/usr/bin/python3',str(Path(__file__).with_name('install.py')),
        '--source',str(Path(__file__).parent),'--user',user,'--options-json',json.dumps(options))

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,KeyError):
        print('Startup scope failed. Check mounted home, selected runtime prerequisites, SSH keys and the private backup manifest.',file=sys.stderr)
        sys.exit(1)
