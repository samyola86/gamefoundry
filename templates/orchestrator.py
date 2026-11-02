import os
import json, pathlib, subprocess, sys, time, urllib.request, traceback, datetime
ROOT=pathlib.Path(__file__).resolve().parent
RESULTS={}
def run(name,args,timeout=240,expected=0):
    start=time.monotonic()
    try:
        p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
        (ROOT/'logs'/f'{name}.log').write_bytes(p.stdout)
        RESULTS[name]={'ok':p.returncode==expected,'exit_code':p.returncode,'seconds':round(time.monotonic()-start,2)}
    except Exception as e:
        (ROOT/'logs'/f'{name}.log').write_text(traceback.format_exc())
        RESULTS[name]={'ok':False,'error':str(e)}
    return RESULTS[name]['ok']
def main():
    RESULTS['run']={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'running'}
    (ROOT/'results.json').write_text(json.dumps(RESULTS,indent=2))
    (ROOT/'logs/ollama.json').unlink(missing_ok=True)
    RESULTS['python']={'version':sys.version,'executable':sys.executable}
    run('expected_failure',[sys.executable,'-c','import sys; print("EXPECTED_FAILURE"); sys.exit(7)'],expected=7)
    run('expected_timeout',[sys.executable,'-c','import time; time.sleep(5)'],timeout=0.2)
    RESULTS['expected_timeout']['ok']='timed out' in RESULTS['expected_timeout'].get('error','')
    for filename in ['blender_result.json','unreal_result.json','unreal_error.txt','unreal_reopen_result.json']:
        (ROOT/filename).unlink(missing_ok=True)
    if run('blender',[os.environ['HARNESS_BLENDER'],'--background','--factory-startup','--python-exit-code','23','--python',str(ROOT/'blender_test.py')]):
        RESULTS['blender']['artifact_verified']=(ROOT/'blender_result.json').exists()
        run('unreal',[str(pathlib.Path(os.environ['HARNESS_UNREAL']).with_name('UnrealEditor-Cmd.exe')),str(ROOT/'TestProject/PipelineSmoke.uproject'),'-run=pythonscript',f'-script={(ROOT / "unreal_test.py").as_posix()}','-unattended','-nosplash','-nullrhi','-nosound',f'-abslog={ROOT / "logs/unreal_engine.log"}'],timeout=360)
        RESULTS['unreal']['artifact_verified']=(ROOT/'unreal_result.json').exists() and (ROOT/'TestProject/Content/PipelineSmoke/SmokeMap.umap').exists()
        RESULTS['unreal']['ok'] &= RESULTS['unreal']['artifact_verified']
        if RESULTS['unreal']['ok']:
            run('unreal_reopen',[str(pathlib.Path(os.environ['HARNESS_UNREAL']).with_name('UnrealEditor-Cmd.exe')),str(ROOT/'TestProject/PipelineSmoke.uproject'),'-run=pythonscript',f'-script={(ROOT / "unreal_verify.py").as_posix()}','-unattended','-nosplash','-nullrhi','-nosound',f'-abslog={ROOT / "logs/unreal_reopen_engine.log"}'],timeout=240)
            RESULTS['unreal_reopen']['ok'] &= (ROOT/'unreal_reopen_result.json').exists()
    try:
        with urllib.request.urlopen(os.environ['HARNESS_OLLAMA']+'/api/tags',timeout=5) as r: tags=json.load(r)
        RESULTS['ollama']={'reachable':True,'models':[m['name'] for m in tags.get('models',[])]}
        if os.environ['HARNESS_MODEL'] in RESULTS['ollama']['models']:
            request=urllib.request.Request(os.environ['HARNESS_OLLAMA']+'/api/generate',data=json.dumps({'model':os.environ['HARNESS_MODEL'],'prompt':'Reply with PIPELINE_OK only.','stream':False,'options':{'num_predict':16}}).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(request,timeout=120) as r: response=json.load(r)
            (ROOT/'logs/ollama.json').write_text(json.dumps(response,indent=2))
            RESULTS['ollama']['inference_ok']=bool(response.get('done') and response.get('response','').strip()=='PIPELINE_OK')
    except Exception as e: RESULTS['ollama']={'reachable':False,'error':str(e)}
    passed=all(RESULTS.get(k,{}).get('ok') for k in ['expected_failure','expected_timeout','blender','unreal','unreal_reopen']) and RESULTS.get('blender',{}).get('artifact_verified',False) and RESULTS.get('ollama',{}).get('inference_ok',False)
    RESULTS['run'].update(status='passed' if passed else 'failed',finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (ROOT/'results.json').write_text(json.dumps(RESULTS,indent=2))
    print(json.dumps(RESULTS,indent=2))
    return 0 if passed else 1
if __name__=='__main__': sys.exit(main())
