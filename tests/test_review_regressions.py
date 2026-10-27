"""Regression checks for issues found while reviewing the cumulative PR."""
import copy,importlib.util,json,os,subprocess,sys,tempfile,threading,unittest
from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import provision

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
startup_config=load('review_startup_config','packages/startup/configure.py')
startup=load('review_startup','packages/startup/startup.py')
runtime=load('review_runtime','packages/runtime/configure.py')
gate=load('review_gate','packages/runtime/proxy_ready.py')

class ReviewRegressions(unittest.TestCase):
    def test_degraded_or_locked_is_reported_without_installation_failure(self):
        for state in ('locked','starting','ready','degraded'):
            result=subprocess.CompletedProcess([],0 if state=='ready' else 1,json.dumps({'state':state}),'')
            with self.subTest(state=state),patch.object(startup_config,'config',return_value=provision.DEFAULTS),patch.object(sys,'argv',['configure.py','verify','health']),patch.object(startup_config.subprocess,'run',return_value=result):
                startup_config.main()
        result=subprocess.CompletedProcess([],2,json.dumps({'state':'degraded'}),'')
        with patch.object(startup_config,'config',return_value=provision.DEFAULTS),patch.object(sys,'argv',['configure.py','verify','health']),patch.object(startup_config.subprocess,'run',return_value=result),self.assertRaises(RuntimeError):startup_config.main()

    def test_startup_verification_runs_one_status_probe(self):
        steps=provision.plan(provision.DEFAULTS,'startup','verify',actual={'ID':'ubuntu'},arch='x86_64')['steps']
        calls=[]
        def runner(argv,**kwargs):calls.append(argv);return subprocess.CompletedProcess(argv,0)
        provision.execute_steps(steps,provision.DEFAULTS,{},runner)
        self.assertEqual(len(calls),1)

    def test_unsupported_exact_node_release_is_rejected_before_install(self):
        for version in ('22.15.0','24.9.0'):
            cfg=provision.override(provision.DEFAULTS,'base.node_version='+json.dumps(version))
            with self.assertRaises(ValueError):provision.validate(cfg)
        for version in ('22.16.0','24.10.0','24'):
            provision.validate(provision.override(provision.DEFAULTS,'base.node_version='+json.dumps(version)))

    def test_unknown_proxy_config_does_not_create_a_conflicting_credential(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(runtime.Path,'home',return_value=Path(folder)):
            path=Path(folder)/'.config/cli-proxy-api/config.yaml';path.parent.mkdir(parents=True);path.write_text('original: provider-config\n')
            with self.assertRaisesRegex(RuntimeError,'Existing proxy configuration'):runtime.configure_proxy(provision.DEFAULTS)
            self.assertFalse((Path(folder)/'.config/environment.d/cliproxy.conf').exists())
            self.assertEqual(path.read_text(),'original: provider-config\n')

    def test_opencode_available_after_fresh_installer_without_new_shell(self):
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder);bin=home/'bin';bin.mkdir()
            curl=bin/'curl';curl.write_text('''#!/bin/bash
while [[ $# -gt 0 ]]; do
 if [[ $1 == -o ]]; then
  cat > "$2" <<'INSTALLER'
#!/bin/bash
mkdir -p "$HOME/.opencode/bin"
printf '#!/bin/sh\\necho installed-fixture\\n' > "$HOME/.opencode/bin/opencode"
chmod +x "$HOME/.opencode/bin/opencode"
INSTALLER
  exit 0
 fi
 shift
done
exit 1
''');curl.chmod(0o755)
            result=subprocess.run(['bash',str(ROOT/'packages/dev-tools/tools/opencode.sh')],env={**os.environ,'HOME':folder,'PATH':str(bin)+':/usr/bin:/bin'},capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('installed-fixture',result.stdout)
            with patch.object(provision.Path,'home',return_value=home):self.assertIn(str(home/'.opencode/bin'),provision.environment(provision.DEFAULTS)['PATH'].split(':'))

    def test_malformed_model_payloads_report_unavailable(self):
        with tempfile.TemporaryDirectory() as folder:
            env=Path(folder)/'.config/environment.d';env.mkdir(parents=True);(env/'cliproxy.conf').write_text('CLIPROXY_API_KEY=sentinel\n')
            for payload in ([],None,{'data':'wrong'},{'data':None}):
                body=json.dumps(payload).encode()
                with patch.object(startup,'http_status',return_value=(200,body)):
                    self.assertEqual(startup.proxy_probe({'home':folder})['state'],'unavailable')
                class Response:
                    status=200
                    def read(self,*args):return body
                    def __enter__(self):return self
                    def __exit__(self,*args):pass
                class Opener:
                    def open(self,*args,**kwargs):return Response()
                with patch.object(gate.Path,'home',return_value=Path(folder)),patch.object(gate.urllib.request,'build_opener',return_value=Opener()):self.assertFalse(gate.ready(8317))

    def test_proxy_credentials_never_follow_http_redirects(self):
        received=[]
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                received.append((self.path,self.headers.get('Authorization')))
                self.send_response(302);self.send_header('Location',f'http://127.0.0.1:{self.server.server_port}/leaked');self.end_headers()
            def log_message(self,*args):pass
        server=HTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as folder:
                env=Path(folder)/'.config/environment.d';env.mkdir(parents=True);(env/'cliproxy.conf').write_text('CLIPROXY_API_KEY=sentinel\n')
                code,_=startup.http_status(f'http://127.0.0.1:{server.server_port}/v1/models',{'Authorization':'Bearer sentinel'})
                self.assertEqual(code,302)
                with patch.object(gate.Path,'home',return_value=Path(folder)):self.assertFalse(gate.ready(server.server_port))
                self.assertEqual(len(received),2)
                self.assertTrue(all(path=='/v1/models' for path,_ in received))
        finally:server.shutdown();thread.join();server.server_close()

if __name__=='__main__':unittest.main()
