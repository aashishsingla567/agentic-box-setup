#!/usr/bin/python3
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from provision_support import run
if sys.argv[1]=='install':run('bash',str(Path(__file__).with_name('install.sh')))
elif not (Path.home()/'.local/bin/rig-panel').is_file():raise SystemExit('rig-panel missing')
else:print('rig-panel installed')
