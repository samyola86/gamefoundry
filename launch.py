"""Launch or reuse this checkout's local dashboard."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from config import app_home

ROOT=Path(__file__).resolve().parent
PORT=int(os.environ.get('GAME_DASHBOARD_PORT','8787'))
URL=f'http://127.0.0.1:{PORT}'

def health():
    try:
        with urllib.request.urlopen(URL+'/api/health',timeout=1) as response:
            return json.load(response)
    except Exception:
        return None

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--no-browser',action='store_true');args=parser.parse_args()
    current=health()
    if current and current.get('instance')!=str(ROOT):
        raise SystemExit('Another Game Foundry checkout uses this port. Stop it or set GAME_DASHBOARD_PORT to a different port.')
    if not current:
        app_home().mkdir(parents=True,exist_ok=True)
        with (app_home()/'dashboard-server.log').open('ab') as log:
            proc=subprocess.Popen([sys.executable,str(ROOT/'server.py')],cwd=ROOT,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        for _ in range(40):
            current=health()
            if current or proc.poll() is not None: break
            time.sleep(.25)
    if not current or current.get('instance')!=str(ROOT):
        raise SystemExit(f'Dashboard could not start. Check {app_home() / "dashboard-server.log"}. Port {PORT} may be in use.')
    print(URL)
    if not args.no_browser: webbrowser.open(URL)

if __name__=='__main__':main()
