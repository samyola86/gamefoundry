"""Read-only prerequisite discovery; only a pipeline run proves integration."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import urllib.request
from config import app_home, defaults

def inspect():
    path=app_home()/'data/settings.json'
    s=defaults()
    if path.exists():s.update(json.loads(path.read_text(encoding='utf-8')))
    results={k:{'found':bool(s[k]) and Path(s[k]).is_file(),'path':s[k]} for k in ['python','blender','unreal','vscode']}
    if results['blender']['found']:
        try:
            p=subprocess.run([s['blender'],'--version'],capture_output=True,text=True,timeout=20)
            results['blender'].update(exit_code=p.returncode,version=p.stdout.splitlines()[0] if p.stdout else 'Unknown')
        except Exception as e:results['blender']['error']=str(e)
    if results['unreal']['found']:
        engine=Path(s['unreal']).parents[2]
        results['unreal']['commandlet_found']=(engine/'Binaries/Win64/UnrealEditor-Cmd.exe').is_file()
        version=engine/'Build/Build.version'
        if version.exists():results['unreal']['build']=json.loads(version.read_text())
    sdk=Path(os.environ.get('ProgramFiles(x86)','C:/Program Files (x86)'))/'Windows Kits/10'
    results['windows_sdk']={'detected_headers':[p.name for p in (sdk/'Include').glob('*') if p.is_dir()],'note':'Presence is not a compiler/build test.'}
    try:
        with urllib.request.urlopen(s['ollama_url']+'/api/tags',timeout=3) as response:models=json.load(response).get('models',[])
        results['ollama']={'reachable':True,'selected_model':s['model'],'selected_model_installed':any(m['name']==s['model'] for m in models)}
    except Exception as e:results['ollama']={'reachable':False,'error':str(e)}
    results['configuration']=str(path)
    results['scope']='Discovery only. Use Architecture > Test whole pipeline for executable integration checks.'
    return results

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--json',action='store_true');args=parser.parse_args()
    report=inspect()
    print(json.dumps(report,indent=2))
    ready=all(report[k]['found'] for k in ['python','blender','unreal','vscode']) and report['ollama'].get('selected_model_installed')
    raise SystemExit(0 if ready else 1)
