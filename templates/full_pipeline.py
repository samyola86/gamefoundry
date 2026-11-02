"""Run all scoped local toolchain checks in this run's independent directory."""
import json, os, pathlib, subprocess, sys, time, datetime, shutil, base64
import orchestrator
root=pathlib.Path(__file__).resolve().parent
engine=pathlib.Path(os.environ['HARNESS_UNREAL']).parents[2]
progress={k:{'status':'pending'} for k in ['assets','gpu','cpp','package','runtime']}
resume=os.environ.get('HARNESS_RESUME')=='1'
if resume and (root/'progress.json').exists():
    progress=json.loads((root/'progress.json').read_text())
core={}
def write():
    tmp=root/'progress.tmp'
    tmp.write_text(json.dumps(progress,indent=2));tmp.replace(root/'progress.json')
def run(key,args,timeout,verify=lambda:True,env=None):
    if resume and progress[key]['status']=='passed' and verify():
        print(key,'reusing verified output from this run',flush=True)
        return True
    progress[key]={'status':'running'};write();started=time.monotonic()
    try:
        with (root/'logs'/f'full_{key}.log').open('wb') as log:
            p=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,timeout=timeout,env=env)
        ok=p.returncode==0 and bool(verify())
        progress[key]={'status':'passed' if ok else 'failed','exit_code':p.returncode,'seconds':round(time.monotonic()-started,2)}
    except Exception as e:
        progress[key]={'status':'failed','error':str(e)}
    write();print(key,progress[key],flush=True)
    return progress[key]['status']=='passed'
if resume and progress['assets']['status']=='passed':
    core=json.loads(json.dumps(progress['assets']['checks']))
else:
    progress['assets']={'status':'running'};write()
    try:
        rc=orchestrator.main()
        core=json.loads((root/'results.json').read_text())
        progress['assets']={'status':'passed' if rc==0 else 'failed','checks':json.loads(json.dumps(core))}
    except Exception as e:
        progress['assets']={'status':'failed','error':str(e)}
write()
if progress['assets']['status']=='passed':
    def rendered():
        receipt=root/'editor_render_result.json'
        return receipt.exists() and json.loads(receipt.read_text()).get('ok') and (root/'unreal_viewport.png').stat().st_size>1000
    # UE's ExecCmds parser has its own quote/comma rules. Encode only the trusted
    # script path so spaces, backslashes and apostrophes cannot alter the command.
    encoded=base64.b64encode(str(root/'editor_render_test.py').encode('utf-8')).decode('ascii')
    startup=f"-ExecCmds=py import runpy; import base64; runpy.run_path(base64.b64decode('{encoded}').decode('utf-8'))"
    run('gpu',[os.environ['HARNESS_UNREAL'],str(root/'TestProject/PipelineSmoke.uproject'),startup,'-unattended','-nosplash','-nosound','-windowed','-ResX=960','-ResY=540',f'-abslog={root / "logs/full_gpu_engine.log"}'],210,rendered)
else:
    progress['gpu']={'status':'skipped','reason':'Asset pipeline failed'};write()
dotnets=list((engine/'Binaries/ThirdParty/DotNet').glob('*/win-x64/dotnet.exe'))
if dotnets:
    # Short staging path avoids Windows/UBT's 260-character build-path limit.
    buildroot=pathlib.Path(os.environ.get('GAMEFOUNDRY_BUILD_ROOT', str(pathlib.Path(os.environ.get('LOCALAPPDATA', str(pathlib.Path.home()))) / 'GFBuilds')))/root.name
    shutil.copytree(root/'CppProbe',buildroot,dirs_exist_ok=True,ignore=shutil.ignore_patterns('Intermediate','Binaries','Saved'))
    run('cpp',[str(dotnets[-1]),str(engine/'Binaries/DotNET/UnrealBuildTool/UnrealBuildTool.dll'),'PipelineCppProbe','Win64','Development',f'-Project={buildroot / "PipelineCppProbe.uproject"}','-NoHotReloadFromIDE'],600,lambda:(buildroot/'Binaries/Win64/PipelineCppProbe.exe').is_file())
else:
    progress['cpp']={'status':'failed','error':'Bundled .NET not found'};write()
if progress['assets']['status']=='passed' and dotnets:
    # Invoke the installed AutomationTool directly instead of passing project
    # paths through cmd.exe / RunUAT.bat's second layer of shell quoting.
    dotnet=dotnets[-1]
    buildenv=dict(os.environ,DOTNET_ROOT=str(dotnet.parent))
    buildenv['PATH']=str(dotnet.parent)+os.pathsep+os.environ.get('PATH','')
    packaged=run('package',[str(dotnet),str(engine/'Binaries/DotNET/AutomationTool/AutomationTool.dll'),'BuildCookRun',f'-project={root / "TestProject/PipelineSmoke.uproject"}','-noP4','-platform=Win64','-clientconfig=Development','-build','-cook','-stage','-pak','-archive',f'-archivedirectory={root / "Packaged"}','-map=/Game/PipelineSmoke/SmokeMap','-unattended','-utf8output'],420,lambda:(root/'Packaged/Windows/PipelineSmoke.exe').is_file(),env=buildenv)
    if packaged:
        def played():
            log=(root/'logs/full_runtime_engine.log').read_text(errors='replace')
            return 'Game Engine Initialized' in log and 'Bringing World /Game/PipelineSmoke/SmokeMap' in log
        run('runtime',[str(root/'Packaged/Windows/PipelineSmoke.exe'),'/Game/PipelineSmoke/SmokeMap','-windowed','-ResX=960','-ResY=540','-nosound','-unattended','-benchmark','-seconds=8','-fps=30',f'-abslog={root / "logs/full_runtime_engine.log"}'],90,played)
    else:
        progress['runtime']={'status':'skipped','reason':'Packaging failed'};write()
else:
    progress['package']={'status':'skipped'};progress['runtime']={'status':'skipped'};write()
passed=all(p['status']=='passed' for p in progress.values())
core['full_checks']=progress
core['run']={'status':'passed' if passed else 'failed','finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(root/'results.json').write_text(json.dumps(core,indent=2))
sys.exit(0 if passed else 1)
