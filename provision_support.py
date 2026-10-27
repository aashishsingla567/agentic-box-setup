"""Small helpers shared by scoped provisioning adapters."""
import hashlib,json,os,platform,subprocess,tarfile,tempfile,urllib.request
from pathlib import Path


def config():return json.loads(os.environ['AGENTIC_CONFIG_JSON'])

def run(*args):
    result=subprocess.run(list(args),check=False)
    if result.returncode:raise RuntimeError(Path(args[0]).name+' failed')
    return result


def download(url,path):
    with urllib.request.urlopen(url,timeout=60) as r,open(path,'wb') as f:
        while True:
            block=r.read(1024*1024)
            if not block:break
            f.write(block)


def safe_tar(archive,destination):
    with tarfile.open(archive) as t:
        for member in t.getmembers():
            name=Path(member.name)
            if name.is_absolute() or '..' in name.parts or not (member.isfile() or member.isdir()):
                raise RuntimeError('Unsupported archive member')
        t.extractall(destination)


def managed_write(path,data,mode=0o600):
    """Preserve arbitrary user files; only update files matching our recorded hash."""
    path=Path(path).expanduser()
    stamp=path.with_name(path.name+'.agentic-sha256')
    if path.is_symlink() or stamp.is_symlink():raise RuntimeError('Managed file cannot be a symlink')
    if path.exists():
        if not stamp.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=stamp.read_text().strip():
            if path.read_bytes()==data:return
            raise RuntimeError('Existing unmanaged or modified config preserved: '+str(path))
    for parent in path.parents:
        if parent.is_symlink():raise RuntimeError('Managed parent cannot be a symlink')
    path.parent.mkdir(parents=True,exist_ok=True)
    def replace(target,content,permissions):
        fd,name=tempfile.mkstemp(prefix=target.name+'.agentic-',dir=target.parent)
        try:
            with os.fdopen(fd,'wb') as out:
                os.fchmod(out.fileno(),permissions);out.write(content);out.flush();os.fsync(out.fileno())
            os.replace(name,target)
        finally:
            if os.path.exists(name):os.unlink(name)
    replace(path,data,mode)
    replace(stamp,(hashlib.sha256(data).hexdigest()+'\n').encode(),0o600)


def checked_release(repo,version,asset,destination):
    url=f'https://api.github.com/repos/{repo}/releases/tags/v{version}'
    with urllib.request.urlopen(url,timeout=30) as r:release=json.load(r)
    row=next((a for a in release['assets'] if a['name']==asset),None)
    if not row or not (row.get('digest') or '').startswith('sha256:'):
        raise RuntimeError('Release requires an upstream SHA-256 asset digest')
    download(row['browser_download_url'],destination)
    if hashlib.sha256(Path(destination).read_bytes()).hexdigest()!=row['digest'][7:]:
        raise RuntimeError('Release checksum mismatch')
