"""Local game-project dashboard. Python standard library only."""
import datetime as dt
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import urllib.error
from briefs import BriefStore, OwnerRequired, RevisionConflict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent
from config import app_home, defaults
DATA = app_home() / 'data'
DATA.mkdir(parents=True, exist_ok=True)
TEMPLATES = ROOT / 'templates'
BRIEFS = BriefStore(DATA / 'briefs')
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.RLock()
BUSY = threading.Lock()
CHAT_BUSY = threading.Lock()
PORT = int(os.environ.get('GAME_DASHBOARD_PORT', '8787'))
ORIGIN = f'http://127.0.0.1:{PORT}'
DEFAULT = defaults()
def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def read(name, default):
    p = DATA / (name + '.json')
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default

def save(name, value):
    with LOCK:
        p = DATA / (name + '.json')
        temp = p.with_suffix('.tmp')
        temp.write_text(json.dumps(value, indent=2), encoding='utf-8')
        temp.replace(p)

def settings():
    return {**DEFAULT, **read('settings', {})}

def absolute(value):
    p = Path(value).expanduser()
    if not p.is_absolute():
        raise ValueError('Choose a full absolute Windows path.')
    return p.resolve()

def executable(value):
    p = absolute(value)
    if p.suffix.lower() != '.exe' or not p.is_file():
        raise ValueError(f'Executable not found: {p}')
    return str(p)

def project(pid):
    return next((p for p in read('projects', []) if p['id'] == pid), None)

def ensure_blend(p):
    if not p['managed']:
        return None
    assets = Path(p['folder']) / 'Assets'
    assets.mkdir(exist_ok=True)
    blend = assets / (p['name'] + '.blend')
    if not blend.exists():
        proc = subprocess.run([executable(settings()['blender']), '--background', '--factory-startup', '--python-exit-code', '23', '--python', str(ROOT / 'starter_blend.py'), '--', str(blend)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        if proc.returncode or not blend.is_file():
            raise ValueError('Blender could not create the starter file. Check the Blender path in Settings.')
    return blend

def chat(body):
    p = project(body.get('project_id'))
    message = str(body.get('message', '')).strip()
    if not p or not message or len(message) > 4000:
        raise ValueError('Select a project and enter a message of up to 4,000 characters.')
    if not CHAT_BUSY.acquire(blocking=False):
        raise ValueError('Qwen is answering another message. Please wait.')
    try:
        s = settings()
        if not re.fullmatch(r'http://(127\.0\.0\.1|localhost):[0-9]{1,5}', s['ollama_url']):
            raise ValueError('Choose a local Ollama address in Settings.')
        history = read('chat_' + p['id'], [])
        messages = [{'role': 'system', 'content': f'You are a local game-development assistant for the project {p["name"]}, target {p["target"]}. Give concise practical suggestions. You cannot inspect project files or run tools. Never claim to have changed files, executed commands or tested anything.'}]
        messages += [{'role': m['role'], 'content': m['content']} for m in history[-12:]]
        messages.append({'role': 'user', 'content': message})
        req = urllib.request.Request(s['ollama_url'] + '/api/chat', data=json.dumps({'model': s['model'], 'messages': messages, 'stream': False, 'options': {'num_predict': 512}}).encode(), headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.load(response)
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors='replace')[:500]
            raise ValueError(f'Ollama returned {e.code}: {detail}') from e
        except (urllib.error.URLError, TimeoutError) as e:
            raise ValueError('Ollama did not respond. Start Ollama and check the address and model in Settings.') from e
        answer = result.get('message', {}).get('content', '').strip()
        if not answer:
            raise ValueError('The model returned an empty answer. Try again.')
        history += [{'role': 'user', 'content': message, 'at': now()}, {'role': 'assistant', 'content': answer, 'at': now(), 'model': s['model']}]
        save('chat_' + p['id'], history[-100:])
        return {'messages': history[-100:], 'model': s['model']}
    finally:
        CHAT_BUSY.release()

def create_project(body, owner_token=None):
    initial_brief = body.get('brief')
    if initial_brief:
        BRIEFS.authorize(owner_token)
    target_platform = body.get('target', 'Windows')
    if target_platform not in {'Windows', 'Android'}:
        raise ValueError('Choose Windows or Android as the target platform.')
    name = str(body.get('name', '')).strip()
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{1,39}', name):
        raise ValueError('Use 2–40 letters, numbers or underscores; start with a letter.')
    if name.upper() in {'CON', 'PRN', 'AUX', 'NUL'} or re.fullmatch(r'(COM|LPT)[0-9]', name.upper()):
        raise ValueError('That name is reserved by Windows.')
    parent = absolute(body.get('folder') or settings()['games_root'])
    parent.mkdir(parents=True, exist_ok=True)
    dest = parent / name
    dest.mkdir(exist_ok=False)  # Existing folders are never overwritten.
    try:
        ue = dest / 'Unreal'
        ue.mkdir()
        for folder in ['Assets', 'Builds', 'Notes', '.harness']:
            (dest / folder).mkdir()
        (ue / 'Content').mkdir()
        descriptor = {'FileVersion': 3, 'EngineAssociation': '5.8', 'Category': 'Games', 'Description': body.get('description', ''), 'Plugins': [{'Name': 'PythonScriptPlugin', 'Enabled': True}, {'Name': 'EditorScriptingUtilities', 'Enabled': True}]}
        if target_platform == 'Android':
            descriptor['TargetPlatforms'] = ['Android']
        up = ue / f'{name}.uproject'
        up.write_text(json.dumps(descriptor, indent=2))
        item = {'id': secrets.token_hex(8), 'name': name, 'folder': str(dest), 'uproject': str(up), 'managed': True, 'created': now(), 'target': target_platform}
        ensure_blend(item)
        item['creative_brief'] = {'read_url': '/api/brief/' + item['id'], 'owner': 'user', 'assistant_access': 'read-only'}
        if initial_brief: BRIEFS.save(item['id'], {**initial_brief, 'revision': 0}, owner_token)
        context = ('# Game creative direction\n\n'
                   'The creative brief is user-owned and read-only to assistants. Read it and its reference images before game work. Use core-reference PDFs to fill missing descriptions; explicit written sections take priority. Ask the user about conflicts or unresolved gaps. Never edit it or obtain its owner passphrase. Keep your implementation notes and proposals in Notes/.\n\n'
                   f'Read API: http://127.0.0.1:{PORT}/api/brief/{item["id"]}\n\n'
                   f'Local brief: {BRIEFS.folder(item["id"]) / "brief.json"}\n')
        (dest / 'AGENTS.md').write_text(context, encoding='utf-8')
        (dest / 'game.json').write_text(json.dumps(item, indent=2))
        (dest / f'{name}.code-workspace').write_text(json.dumps({'folders': [{'path': '.'}], 'settings': {'python.defaultInterpreterPath': settings()['python']}}, indent=2))
        projects = read('projects', [])
        projects.append(item)
        save('projects', projects)
        return item
    except Exception:
        # Keep partial files for inspection; never recursively remove user folders.
        raise

def register_project(body):
    up = absolute(body.get('uproject', ''))
    if up.suffix.lower() != '.uproject' or not up.is_file():
        raise ValueError('Choose an existing .uproject file.')
    json.loads(up.read_text(encoding='utf-8-sig'))
    projects = read('projects', [])
    if any(Path(p['uproject']).resolve() == up for p in projects):
        raise ValueError('This project is already registered.')
    item = {'id': secrets.token_hex(8), 'name': up.stem, 'folder': str(up.parent), 'uproject': str(up), 'managed': False, 'created': now(), 'target': 'Unspecified'}
    projects.append(item)
    save('projects', projects)
    return item

def update_settings(body):
    s = settings()
    for key in DEFAULT:
        if key in body:
            s[key] = str(body[key]).strip()
    absolute(s['games_root'])
    for key in ['blender', 'unreal', 'python', 'vscode']:
        executable(s[key])
    if not re.fullmatch(r'http://(127\.0\.0\.1|localhost):[0-9]{1,5}', s['ollama_url']):
        raise ValueError('Ollama must use a local http://127.0.0.1:PORT or localhost:PORT address.')
    if not s['model']:
        raise ValueError('Choose an Ollama model.')
    save('settings', s)
    return s

def job_update(job):
    jobs = read('jobs', [])
    jobs = [job if j['id'] == job['id'] else j for j in jobs]
    save('jobs', jobs)

def run_job(job, s):
    folder = Path(job['folder'])
    try:
        for f in TEMPLATES.iterdir():
            if f.is_file():
                shutil.copy2(f, folder / f.name)
            elif f.is_dir() and f.name == 'CppProbe':
                shutil.copytree(f, folder / f.name, dirs_exist_ok=True)
        (folder / 'TestProject/Content').mkdir(parents=True, exist_ok=True)
        shutil.copy2(folder / 'PipelineSmoke.uproject', folder / 'TestProject/PipelineSmoke.uproject')
        (folder / 'logs').mkdir(exist_ok=True)
        env = dict(os.environ, HARNESS_BLENDER=s['blender'], HARNESS_UNREAL=s['unreal'], HARNESS_OLLAMA=s['ollama_url'], HARNESS_MODEL=s['model'])
        if job.get('resume'):
            env['HARNESS_RESUME'] = '1'
        job.update(status='running', started=now())
        job_update(job)
        with (folder / 'console.log').open('wb') as log:
            script = 'full_pipeline.py' if job.get('full') else 'orchestrator.py'
            proc = subprocess.Popen([executable(s['python']), str(folder / script)], stdout=log, stderr=subprocess.STDOUT, env=env, cwd=folder)
            # Every tool step inside the harness has its own timeout.
            code = proc.wait()
        result = json.loads((folder / 'results.json').read_text()) if (folder / 'results.json').exists() else {}
        job.update(status='passed' if code == 0 and result.get('run', {}).get('status') == 'passed' else 'failed', exit_code=code, results=result)
    except Exception:
        (folder / 'dashboard_error.log').write_text(traceback.format_exc())
        job.update(status='failed', error='Could not complete the run. See logs.')
    finally:
        job['finished'] = now()
        job_update(job)
        BUSY.release()

def start_job(body):
    p = project(body.get('project_id'))
    if not p:
        raise ValueError('Select a project first.')
    if not BUSY.acquire(blocking=False):
        raise ValueError('A test is already running. Wait for it to finish.')
    try:
        jid = secrets.token_hex(8)
        folder = app_home() / 'runs' / jid
        folder.mkdir(parents=True)
        full = body.get('full') is True
        job = {'id': jid, 'project_id': p['id'], 'project': p['name'], 'status': 'queued', 'created': now(), 'folder': str(folder), 'kind': 'Full pipeline verification' if full else 'Isolated pipeline smoke test', 'full': full}
        job['settings_snapshot'] = settings()
        jobs = read('jobs', [])
        jobs.insert(0, job)
        save('jobs', jobs)
        threading.Thread(target=run_job, args=(job, settings()), daemon=True).start()
        return job
    except Exception:
        BUSY.release()
        raise

def retry_job(body):
    jobs = read('jobs', [])
    job = next((j for j in jobs if j['id'] == body.get('job_id')), None)
    if not job or not job.get('full') or job['status'] != 'failed':
        raise ValueError('Choose a failed full-pipeline test.')
    if job.get('settings_snapshot') != settings():
        raise ValueError('Settings changed. Start a fresh full test instead.')
    if not BUSY.acquire(blocking=False):
        raise ValueError('Another test is running.')
    try:
        folder = Path(job['folder'])
        job.setdefault('previous_attempts', []).append({'status': job['status'], 'finished': job.get('finished'), 'checks': job.get('results', {}).get('full_checks')})
        archive = folder/'attempts'/str(len(job['previous_attempts']))
        archive.mkdir(parents=True, exist_ok=True)
        for receipt in ['results.json', 'progress.json']:
            if (folder/receipt).exists():shutil.copy2(folder/receipt, archive/receipt)
        if (folder/'logs').exists():
            shutil.copytree(folder/'logs', archive/'logs', dirs_exist_ok=True)
        failed_log = folder/'logs/full_cpp.log'
        if failed_log.exists():
            shutil.copy2(failed_log, folder/'logs/full_cpp_previous_attempt.log')
        job.update(status='queued', resume=True)
        save('jobs', jobs)
        threading.Thread(target=run_job, args=(job, settings()), daemon=True).start()
        return job
    except Exception:
        BUSY.release()
        raise

class Handler(BaseHTTPRequestHandler):
    def send(self, data, status=200, mime='application/json'):
        content = json.dumps(data).encode() if mime == 'application/json' else data.encode()
        self.send_response(status)
        self.send_header('Content-Type', mime + '; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(content)

    def image_response(self, path, mime):
        raw = path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'private, no-store')
        self.end_headers()
        self.wfile.write(raw)

    def trusted_host(self):
        return self.headers.get('Host') in {f'127.0.0.1:{PORT}', f'localhost:{PORT}'}

    def do_GET(self):
        if not self.trusted_host():
            return self.send({'error': 'Invalid host'}, 403)
        if self.path == '/':
            return self.send((ROOT / 'index.html').read_text(encoding='utf-8').replace('__TOKEN__', TOKEN), mime='text/html')
        if self.path == '/api/health':
            return self.send({'app': 'gamefoundry', 'version': '0.2.0', 'instance': str(ROOT)})
        if self.path == '/api/owner/status':
            return self.send({'configured': BRIEFS.configured()})
        if self.path.startswith('/api/brief-pdf/'):
            try:
                _, _, _, pid, document_id = self.path.split('/')
                if not project(pid): raise ValueError('Project not found.')
                return self.image_response(BRIEFS.document(pid, document_id), 'application/pdf')
            except (ValueError, OSError): return self.send({'error': 'Reference PDF not found.'}, 404)
        if self.path.startswith('/api/brief-image/'):
            try:
                _, _, _, pid, image_id = self.path.split('/')
                if not project(pid): raise ValueError('Project not found.')
                path, mime = BRIEFS.image(pid, image_id)
                return self.image_response(path, mime)
            except (ValueError, OSError): return self.send({'error': 'Reference image not found.'}, 404)
        if self.path.startswith('/api/brief/'):
            pid = self.path.rsplit('/', 1)[-1]
            if not project(pid): return self.send({'error': 'Project not found.'}, 404)
            return self.send(BRIEFS.read(pid))
        if self.path == '/api/state':
            jobs = read('jobs', [])
            for job in jobs:
                progress = Path(job['folder']) / 'progress.json'
                if progress.exists():
                    try:
                        job['progress'] = json.loads(progress.read_text())
                    except (ValueError, OSError):
                        pass
            return self.send({'settings': settings(), 'projects': read('projects', []), 'jobs': jobs, 'busy': BUSY.locked()})
        if self.path == '/api/ollama':
            try:
                url = settings()['ollama_url']
                if not re.fullmatch(r'http://(127\.0\.0\.1|localhost):[0-9]{1,5}', url):
                    raise ValueError('Ollama address must be local.')
                with urllib.request.urlopen(url + '/api/ps', timeout=3) as response:
                    models = json.load(response).get('models', [])
                return self.send({'reachable': True, 'models': models, 'selected_model': settings()['model'], 'checked_at': now()})
            except Exception as e:
                return self.send({'reachable': False, 'models': [], 'error': str(e), 'selected_model': settings()['model'], 'checked_at': now()})
        if self.path.startswith('/api/chat/'):
            p = project(self.path.rsplit('/', 1)[-1])
            if not p:
                return self.send({'error': 'Project not found'}, 404)
            return self.send({'messages': read('chat_' + p['id'], []), 'model': settings()['model']})
        if self.path.startswith('/api/log/'):
            jid = self.path.rsplit('/', 1)[-1]
            j = next((j for j in read('jobs', []) if j['id'] == jid), None)
            if not j:
                return self.send({'error': 'Run not found'}, 404)
            folder = Path(j['folder'])
            text = []
            for p in [folder / 'console.log', folder / 'dashboard_error.log', *sorted((folder / 'logs').glob('*.log'))]:
                if p.exists():
                    text.append(f'--- {p.name} ---\n' + p.read_bytes()[-14000:].decode(errors='replace'))
            return self.send({'text': '\n'.join(text)})
        self.send({'error': 'Not found'}, 404)

    def do_POST(self):
        if not self.trusted_host() or self.headers.get('X-Dashboard-Token') != TOKEN or self.headers.get('Origin', ORIGIN) not in {ORIGIN, f'http://localhost:{PORT}'}:
            return self.send({'error': 'Request denied'}, 403)
        try:
            length = int(self.headers.get('Content-Length', 0))
            limit = 60*1024*1024 if self.path in {'/api/brief/save', '/api/projects/create'} else 20000
            if not 0 < length <= limit:
                raise ValueError('Invalid request size.')
            body = json.loads(self.rfile.read(length))
            if self.path == '/api/chat':
                return self.send(chat(body))
            with LOCK:
                if self.path == '/api/owner/unlock':
                    return self.send({'owner_token': BRIEFS.unlock(body.get('password'), setup=body.get('setup') is True, confirm=body.get('confirm'))})
                if self.path == '/api/owner/lock':
                    BRIEFS.lock(self.headers.get('X-Brief-Owner'))
                    return self.send({'locked': True})
                if self.path == '/api/brief/save':
                    if not project(body.get('project_id')): raise ValueError('Project not found.')
                    return self.send(BRIEFS.save(body['project_id'], body, self.headers.get('X-Brief-Owner')))
                if self.path == '/api/projects/create':
                    result = create_project(body, self.headers.get('X-Brief-Owner'))
                elif self.path == '/api/projects/register':
                    result = register_project(body)
                elif self.path == '/api/settings':
                    result = update_settings(body)
                elif self.path == '/api/jobs':
                    result = start_job(body)
                elif self.path == '/api/jobs/retry':
                    result = retry_job(body)
                elif self.path == '/api/open':
                    p = project(body.get('project_id'))
                    if not p:
                        raise ValueError('Select a project.')
                    app = body.get('app')
                    if app == 'vscode':
                        target = Path(p['folder']) / (p['name'] + '.code-workspace') if p['managed'] else Path(p['folder'])
                    elif app == 'unreal':
                        target = Path(p['uproject'])
                    elif app == 'blender':
                        target = ensure_blend(p)
                    else:
                        raise ValueError('Unsupported app.')
                    subprocess.Popen([executable(settings()[app])] + ([str(target)] if target else []))
                    result = {'opened': True}
                else:
                    return self.send({'error': 'Not found'}, 404)
            self.send(result)
        except OwnerRequired as e:
            self.send({'error': str(e)}, 403)
        except RevisionConflict as e:
            self.send({'error': str(e)}, 409)
        except (ValueError, FileExistsError, OSError) as e:
            self.send({'error': str(e)}, 400)
        except Exception:
            traceback.print_exc()
            self.send({'error': 'Unexpected error. Check the dashboard server log.'}, 500)

if __name__ == '__main__':
    server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    for job in read('jobs', []):
        if job['status'] in {'running', 'queued'}:
            job.update(status='interrupted', error='Dashboard restarted; previous completion is unknown.')
            job_update(job)
    print(f'Game dashboard: {ORIGIN}', flush=True)
    server.serve_forever()
