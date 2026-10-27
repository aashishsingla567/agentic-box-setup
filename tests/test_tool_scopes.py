"""Run shell adapters with inert vendor/system-command fixtures, never network/sudo."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class ToolScopes(unittest.TestCase):
    def fixture(self,temp):
        base=Path(temp);bin=base/'bin';bin.mkdir();log=base/'commands'
        def stub(name,body):
            path=bin/name;path.write_text('#!/bin/bash\nset -euo pipefail\n'+body+'\n');path.chmod(0o755)
        stub('curl', '''printf 'curl %s\\n' "$*" >> "$TEST_LOG"
while [[ $# -gt 0 ]]; do
  if [[ $1 == -o ]]; then printf '#!/bin/sh\\nexit 0\\n' > "$2"; exit 0; fi
  shift
done
exit 1''')
        stub('sudo', '''printf 'sudo %s\\n' "$*" >> "$TEST_LOG"
# A simulated initial join reads the key file, never writes its contents to the log.
if [[ ${1:-} == tailscale && ${2:-} == up ]]; then
  for value in "$@"; do
    if [[ $value == --auth-key=file:* ]]; then
      file=${value#--auth-key=file:}
      [[ $(stat -c %a "$file") == 600 ]] || exit 1
      [[ -s $file ]] || exit 1
    fi
  done
fi''')
        stub('tailscale', '''if [[ ${1:-} == status ]]; then printf '{"BackendState":"%s"}\\n' "$TEST_TAILNET_STATE"; else echo fixture; fi''')
        for name in ('agent','agy','t3','opencode','claude'):stub(name,'echo fixture')
        env={**os.environ,'PATH':str(bin)+':/usr/bin:/bin','HOME':temp,'TEST_LOG':str(log),
             'AGENTIC_DESKTOP':'false','AGENTIC_TAILSCALE_JOIN':'true','TEST_TAILNET_STATE':'Running'}
        return env,log

    def test_headless_cli_installers_do_not_install_desktop_packages(self):
        with tempfile.TemporaryDirectory() as temp:
            env,log=self.fixture(temp)
            for tool in ('cursor','antigravity','t3code','opencode','claude-code'):
                result=subprocess.run(['bash',str(ROOT/f'packages/dev-tools/tools/{tool}.sh')],env=env,capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
            self.assertNotIn('sudo ',log.read_text())
            self.assertNotIn('.deb',log.read_text())

    def test_running_tailnet_identity_never_reenrolls(self):
        with tempfile.TemporaryDirectory() as temp:
            env,log=self.fixture(temp)
            result=subprocess.run(['bash',str(ROOT/'packages/dev-tools/tools/tailscale.sh')],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertNotIn('tailscale up',log.read_text())
            self.assertNotIn('logout',log.read_text())

    def test_initial_join_uses_private_file_and_never_exposes_key(self):
        with tempfile.TemporaryDirectory() as temp:
            env,log=self.fixture(temp);env.update(TEST_TAILNET_STATE='NeedsLogin',TAILSCALE_AUTHKEY='sentinel-sensitive-key',TAILSCALE_LOGIN_SERVER='https://control.example')
            result=subprocess.run(['bash',str(ROOT/'packages/dev-tools/tools/tailscale.sh')],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('--auth-key=file:',log.read_text())
            self.assertNotIn(env['TAILSCALE_AUTHKEY'],log.read_text()+result.stdout+result.stderr)
            keypath=log.read_text().split('--auth-key=file:')[1].strip().split()[0]
            self.assertFalse(Path(keypath).exists())

    def test_nonlogin_state_is_preserved_for_manual_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            env,log=self.fixture(temp);env['TEST_TAILNET_STATE']='Stopped'
            result=subprocess.run(['bash',str(ROOT/'packages/dev-tools/tools/tailscale.sh')],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,1)
            self.assertNotIn('tailscale up',log.read_text())

if __name__=='__main__':unittest.main()
