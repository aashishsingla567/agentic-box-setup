#!/usr/bin/python3
import hashlib,json,os,platform,re,shutil,subprocess,sys,tempfile,urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from provision_support import config,download,run,managed_write

TOOLS={'opencode':'opencode','codex':'codex','claude-code':'claude','cursor':'agent','antigravity':'agy','t3code':'t3','tailscale':'tailscale'}

def install_packages(cfg):
    packages=['ca-certificates','curl','git','xz-utils','tar','python3','openssh-client']
    if 'startup' in cfg['packages']:
        packages+=['openssh-server','keyutils','libpam-systemd']
        if cfg['startup']['home_policy'] != 'mounted' and platform.machine() == 'x86_64':packages+=['ecryptfs-utils']
    if 'rig-panel' in cfg['packages']:packages+=['python3-gi','gir1.2-gtk-4.0','gir1.2-adw-1','gnome-terminal']
    run('sudo','apt-get','update')
    run('sudo','apt-get','install','-y',*packages)


def install_node(cfg):
    version=cfg['base']['node_version'];major=int(version.split('.')[0])
    if major<22:raise RuntimeError('Use Node 22.16+ or 24.10+')
    folder='latest-v'+version+'.x' if '.' not in version else 'v'+version
    arch={'x86_64':'x64','aarch64':'arm64','arm64':'arm64'}[platform.machine()]
    base='https://nodejs.org/dist/'+folder+'/'
    sums=urllib.request.urlopen(base+'SHASUMS256.txt',timeout=30).read().decode()
    matches=[l.split() for l in sums.splitlines() if re.search(r'node-v[0-9.]+-linux-'+arch+r'\.tar\.xz$',l)]
    if len(matches)!=1:raise RuntimeError('Cannot identify Node release')
    checksum,name=matches[0]
    release=name.split('-linux-')[0]
    store=Path.home()/'.local/share/agentic-box/node'
    destination=store/release
    if destination.exists() and not (destination/'.agentic-complete').is_file():
        raise RuntimeError('Unmanaged or incomplete Node directory preserved; inspect it before retrying')
    if not destination.exists():
        store.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='agentic-node-') as tmp:
            archive=Path(tmp)/name;download(base+name,archive)
            if hashlib.sha256(archive.read_bytes()).hexdigest()!=checksum:raise RuntimeError('Node checksum mismatch')
            with tempfile.TemporaryDirectory(prefix='.install-',dir=store) as staged:
                # Verified upstream archives contain legitimate relative npm symlinks.
                run('tar','-xJf',str(archive),'--strip-components=1','--no-same-owner','-C',staged)
                Path(staged,'.agentic-complete').write_text(checksum+'\n')
                os.rename(staged,destination)
    current=store/'current'
    if current.exists() and not current.is_symlink():raise RuntimeError('Existing Node current path preserved')
    link=store/'current.new';link.unlink(missing_ok=True);link.symlink_to(destination);os.replace(link,current)
    env=Path.home()/'.config/agentic-box/env.sh'
    body=('export PATH="'+str(current/'bin')+':$HOME/.local/bin:$PATH"\n').encode()
    managed_write(env,body,0o644)
    for name in ('.profile','.zprofile'):
        path=Path.home()/name
        if path.is_symlink():raise RuntimeError('Shell profile symlink preserved; source ~/.config/agentic-box/env.sh manually')
        line='[ ! -r "$HOME/.config/agentic-box/env.sh" ] || . "$HOME/.config/agentic-box/env.sh"'
        old=path.read_text() if path.exists() else ''
        if line not in old:
            with path.open('a') as out:out.write('\n# agentic-box managed PATH\n'+line+'\n')
    print('Node installed in a user prefix. Start a new login shell for its PATH.')


def main():
    stage,component=sys.argv[1:3]
    if stage=='verify-tool':
        command=TOOLS[component]
        if not shutil.which(command):raise RuntimeError('Missing command: '+command)
        print(component+': command available');return
    cfg=config()
    if component=='packages':install_packages(cfg)
    elif component=='node':install_node(cfg)

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,KeyError) as e:print('Base setup failed: '+str(e),file=sys.stderr);sys.exit(1)
