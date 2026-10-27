#!/usr/bin/python3
"""Bounded authenticated local readiness gate. Never print credentials or responses."""
import argparse,json,time,urllib.error,urllib.request
from pathlib import Path


class NoCredentialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, url):
        return None


def ready(port):
    try:
        env=Path.home()/'.config/environment.d/cliproxy.conf'
        values=[line.partition('=')[2].strip().strip('\"\'') for line in env.read_text().splitlines()
                if line.startswith('CLIPROXY_API_KEY=')]
        if len(values)!=1 or not values[0]:return False
        req=urllib.request.Request(f'http://127.0.0.1:{port}/v1/models',headers={'Authorization':'Bearer '+values[0]})
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoCredentialRedirect())
        with opener.open(req,timeout=3) as response:
            payload=json.loads(response.read(1024*1024))
            return response.status==200 and isinstance(payload,dict) and isinstance(payload.get('data'),list)
    except (OSError,ValueError,urllib.error.URLError):return False


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,required=True)
    args=parser.parse_args();deadline=time.monotonic()+120
    while time.monotonic()<deadline:
        if ready(args.port):return 0
        time.sleep(2)
    print('Local proxy API unavailable. Check proxy configuration and its local credential.')
    return 1

if __name__=='__main__':raise SystemExit(main())
