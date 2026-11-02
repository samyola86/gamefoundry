"""Discover installed tools without embedding a particular user's paths."""
import os
from pathlib import Path
import re
import shutil
import sys

def app_home():
    override = os.environ.get('GAMEFOUNDRY_HOME')
    return Path(override).expanduser().resolve() if override else Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local/share'))) / 'GameFoundry'

def version_key(p):
    return tuple(int(v) for v in re.findall(r'\d+', str(p)))

def choose(paths):
    return next((str(Path(p).resolve()) for p in paths if p and Path(p).is_file()), '')

def discover_tools():
    pf=Path(os.environ.get('ProgramFiles', 'C:/Program Files'))
    local=Path(os.environ.get('LOCALAPPDATA', str(Path.home()/'AppData/Local')))
    blender=sorted((pf/'Blender Foundation').glob('Blender */blender.exe'),key=version_key,reverse=True)
    preferred=[p for p in blender if 'Blender 5.2' in str(p)]
    engines=list((pf/'Epic Games').glob('UE_5.8/Engine/Binaries/Win64/UnrealEditor.exe'))
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\EpicGames\Unreal Engine\5.8') as key:
            engines.insert(0,Path(winreg.QueryValueEx(key,'InstalledDirectory')[0])/'Engine/Binaries/Win64/UnrealEditor.exe')
    except (ImportError, OSError):
        pass
    return {
        'blender':choose([shutil.which('blender'),*preferred,*blender]),
        'unreal':choose([shutil.which('UnrealEditor'),*engines]),
        'vscode':choose([local/'Programs/Microsoft VS Code/Code.exe',pf/'Microsoft VS Code/Code.exe']),
        'python':sys.executable,
    }

def defaults():
    return {'games_root':str(Path.home()/'Documents/GameFoundryGames'),**discover_tools(),'ollama_url':'http://127.0.0.1:11434','model':'qwen2.5-coder:7b'}
