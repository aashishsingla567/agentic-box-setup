#!/usr/bin/python3
"""Bounded authenticated local readiness gate. Never print credentials or responses."""
import argparse,json,time,urllib.error,urllib.request
from pathlib import Path


def ready(port):
    try:
        env=Path.home()/'.config/environment.d/cliproxy.conf'
        values=[line.partition('=')[2].strip().strip('\"\'') for line in env.read_text().splitlines()
                if line.startswith('CLIPROXY_API_KEY=')]
        if len(values)!=1 or not values[0]:return False
        req=urllib.request.Request(f'http://127.0.0.1:{port}/v1/models',headers={'Authorization':'Bearer '+values[0]})
        with urllib.request.urlopen(req,timeout=3) as response:
            return response.status==200 and isinstance(json.loads(response.read(1024*1024)).get('data'),list)
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
