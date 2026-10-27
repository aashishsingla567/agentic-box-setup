#!/usr/bin/python3
import os,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from provision_support import config,run
stage,component=sys.argv[1:3];cfg=config()
if stage=='verify':
    if not (Path.home()/'.local/bin/sleepless').exists():raise SystemExit('sleepless command missing')
    print('sleepless: command installed; power policy '+cfg['sleepless']['mode'])
else:
    mode='--install-only' if component=='cli' else '--on' if cfg['sleepless']['mode']=='always-on' else '--off'
    run('bash',str(Path(__file__).with_name('install.sh')),mode)
