"""Create a self-contained local interpreter and initial per-PC settings."""
import json
import os
from pathlib import Path
import subprocess
import sys
from config import app_home, defaults

ROOT=Path(__file__).resolve().parent

def main():
    if sys.version_info < (3,11):
        raise SystemExit('Python 3.11 or newer is required. Run Install-Prerequisites.ps1 first.')
    venv=ROOT/'.venv'
    python=venv/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.exists():
        subprocess.run([sys.executable,'-m','venv','--without-pip',str(venv)],check=True)
    subprocess.run([str(python),'-c','import json,ssl,urllib.request,http.server; print("Local Python environment ready")'],check=True)
    folder=app_home()/'data';folder.mkdir(parents=True,exist_ok=True)
    settings=folder/'settings.json'
    if not settings.exists():
        config=defaults();config['python']=str(python)
        settings.write_text(json.dumps(config,indent=2),encoding='utf-8')
        print('Created settings:',settings)
    else:
        print('Kept existing settings:',settings)
    print('No pip packages are required. Run Start-GameFoundry.cmd, review Settings, then run a full test.')

if __name__=='__main__': main()
