"""User-owned creative briefs. Build/chat code has no write credential."""
import base64
import datetime
import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets
import time

FIELDS = {'vision':'Game description', 'look_feel':'Look and feel', 'layout':'World and level layout', 'characters':'Characters', 'mechanics':'Game mechanics', 'audio':'Audio and music', 'constraints':'Must-haves and things to avoid', 'notes':'Additional direction'}
IMAGE_TYPES = {'png':'image/png','jpg':'image/jpeg','webp':'image/webp'}

class OwnerRequired(PermissionError): pass
class RevisionConflict(ValueError): pass

class BriefStore:
    def __init__(self, root):
        self.root = Path(root)
        self.sessions = {}

    def configured(self): return (self.root/'owner.json').exists()

    def unlock(self, password, setup=False, confirm=None):
        if not isinstance(password,str) or not 8 <= len(password) <= 200:
            raise ValueError('Use a brief passphrase with 8–200 characters.')
        path = self.root/'owner.json'
        if setup:
            if path.exists(): raise ValueError('Brief owner is already configured. Unlock with your existing passphrase.')
            if confirm != password: raise ValueError('The passphrases do not match.')
            self.root.mkdir(parents=True,exist_ok=True)
            salt=secrets.token_bytes(16)
            digest=hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1)
            with path.open('x',encoding='utf-8') as f: json.dump({'salt':salt.hex(),'digest':digest.hex()},f)
        elif not path.exists():
            raise OwnerRequired('Set up your brief passphrase first.')
        else:
            record=json.loads(path.read_text(encoding='utf-8'))
            digest=hashlib.scrypt(password.encode(),salt=bytes.fromhex(record['salt']),n=16384,r=8,p=1)
            if not hmac.compare_digest(digest.hex(),record['digest']): raise OwnerRequired('Incorrect brief passphrase.')
        token=secrets.token_urlsafe(32)
        self.sessions[token]=time.monotonic()+5400
        return token

    def authorize(self, token):
        if self.sessions.get(token or '',0) < time.monotonic():
            raise OwnerRequired('Unlock brief editing with your private passphrase. Builds and assistants have read-only access.')

    def lock(self,token): self.sessions.pop(token or '',None)

    def folder(self,pid):
        if not re.fullmatch(r'[a-f0-9]{16}',pid or ''): raise ValueError('Invalid project identifier.')
        return self.root/pid

    def read(self,pid):
        path=self.folder(pid)/'brief.json'
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'schema_version':1,'owner':'user','assistant_access':'read-only','project_id':pid,'revision':0,'fields':{k:'' for k in FIELDS},'images':[],'updated_at':None}

    def image(self,pid,image_id):
        if not re.fullmatch(r'[a-f0-9]{16}\.(png|jpg|webp)',image_id or ''): raise ValueError('Invalid reference image identifier.')
        path=self.folder(pid)/'images'/image_id
        if not path.is_file(): raise FileNotFoundError('Reference image not found.')
        return path,IMAGE_TYPES[path.suffix[1:]]

    def save(self,pid,body,token):
        self.authorize(token)
        old=self.read(pid)
        if body.get('revision') != old['revision']: raise RevisionConflict('The brief changed in another window. Reopen it before saving; your draft has not been saved.')
        fields=body.get('fields',{})
        if not isinstance(fields,dict) or set(fields)-set(FIELDS): raise ValueError('Unknown brief section.')
        if any(not isinstance(v,str) or len(v)>20000 for v in fields.values()): raise ValueError('Each section supports up to 20,000 characters.')
        refs=body.get('images',[])
        if not isinstance(refs,list) or len(refs)>24: raise ValueError('Use up to 24 reference images.')
        images=[];pending=[];total=0
        for ref in refs:
            if not isinstance(ref,dict): raise ValueError('Invalid reference image entry.')
            section=ref.get('section','look_feel')
            if section not in FIELDS: raise ValueError('Choose a valid image section.')
            caption=ref.get('caption','');name=ref.get('name','Reference')
            if not isinstance(caption,str) or len(caption)>1000 or not isinstance(name,str) or len(name)>200: raise ValueError('Reference caption or name is too long.')
            if ref.get('data'):
                try: raw=base64.b64decode(ref['data'],validate=True)
                except Exception as e: raise ValueError('Invalid reference image encoding.') from e
                total+=len(raw)
                if len(raw)>8*1024*1024 or total>20*1024*1024: raise ValueError('Use images under 8 MB each and 20 MB total per save.')
                if raw.startswith(b'\x89PNG\r\n\x1a\n') and len(raw)>24: ext='png'
                elif raw.startswith(b'\xff\xd8\xff') and raw.endswith(b'\xff\xd9'): ext='jpg'
                elif raw.startswith(b'RIFF') and raw[8:12]==b'WEBP': ext='webp'
                else: raise ValueError('Reference files must be PNG, JPEG or WebP images. SVG and other file types are not accepted.')
                image_id=secrets.token_hex(8)+'.'+ext
                pending.append((image_id,raw))
            else:
                image_id=ref.get('id')
                self.image(pid,image_id)
            images.append({'id':image_id,'name':name,'caption':caption,'section':section,'url':f'/api/brief-image/{pid}/{image_id}'})
        folder=self.folder(pid);folder.mkdir(parents=True,exist_ok=True)
        (folder/'images').mkdir(exist_ok=True)
        for image_id,raw in pending:
            with (folder/'images'/image_id).open('xb') as f:f.write(raw)
        if old['revision']:
            (folder/'history').mkdir(exist_ok=True)
            with (folder/'history'/f'{old["revision"]}.json').open('x',encoding='utf-8') as f:json.dump(old,f,ensure_ascii=False,indent=2)
        doc={'schema_version':1,'owner':'user','assistant_access':'read-only','project_id':pid,'revision':old['revision']+1,'fields':{k:fields.get(k,'') for k in FIELDS},'images':images,'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
        temp=folder/'brief.tmp';temp.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(folder/'brief.json')
        return doc
