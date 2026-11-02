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
REFERENCE_POLICY = 'Explicit written brief sections take priority. Consult core-reference PDFs to fill missing descriptions. If references conflict or do not resolve a gap, ask the user; do not invent or overwrite their brief.'

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
        doc=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'schema_version':2,'owner':'user','assistant_access':'read-only','project_id':pid,'revision':0,'fields':{k:'' for k in FIELDS},'images':[],'updated_at':None}
        doc.setdefault('documents',[])
        doc['reference_policy']=REFERENCE_POLICY
        return doc

    def image(self,pid,image_id):
        if not re.fullmatch(r'[a-f0-9]{16}\.(png|jpg|webp)',image_id or ''): raise ValueError('Invalid reference image identifier.')
        path=self.folder(pid)/'images'/image_id
        if not path.is_file(): raise FileNotFoundError('Reference image not found.')
        return path,IMAGE_TYPES[path.suffix[1:]]

    def document(self,pid,document_id):
        if not re.fullmatch(r'[a-f0-9]{16}\.pdf',document_id or ''): raise ValueError('Invalid PDF identifier.')
        path=self.folder(pid)/'documents'/document_id
        if not path.is_file(): raise FileNotFoundError('Reference PDF not found.')
        return path

    def save(self,pid,body,token):
        self.authorize(token)
        old=self.read(pid)
        if body.get('revision') != old['revision']: raise RevisionConflict('The brief changed in another window. Reopen it before saving; your draft has not been saved.')
        fields=body.get('fields',{})
        if not isinstance(fields,dict) or set(fields)-set(FIELDS): raise ValueError('Unknown brief section.')
        if any(not isinstance(v,str) or len(v)>20000 for v in fields.values()): raise ValueError('Each section supports up to 20,000 characters.')
        refs=body.get('images',old.get('images',[]))
        if not isinstance(refs,list) or len(refs)>24: raise ValueError('Use up to 24 reference images.')
        images=[];pending=[];total=0
        for ref in refs:
            if not isinstance(ref,dict): raise ValueError('Invalid reference image entry.')
            section=ref.get('section','look_feel')
            if section not in FIELDS: raise ValueError('Choose a valid image section.')
            caption=ref.get('caption','');name=ref.get('name','Reference')
            if not isinstance(caption,str) or len(caption)>1000 or not isinstance(name,str) or len(name)>200: raise ValueError('Reference caption or name is too long.')
            role=ref.get('role','section_reference')
            if role not in {'section_reference','master_reference'}: raise ValueError('Invalid image role.')
            tags=ref.get('tags',[])
            if not isinstance(tags,list) or len(tags)>12 or any(not isinstance(tag,str) or not tag.strip() or len(tag)>60 for tag in tags): raise ValueError('Use up to 12 image tags, each 1–60 characters.')
            tags=list(dict.fromkeys(tag.strip() for tag in tags))
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
            images.append({'id':image_id,'name':name,'caption':caption,'section':section,'role':role,'tags':tags,'url':f'/api/brief-image/{pid}/{image_id}'})
        docs=body.get('documents',old.get('documents',[]))
        if not isinstance(docs,list) or len(docs)>12: raise ValueError('Use up to 12 core-reference PDFs.')
        documents=[];pending_documents=[]
        for ref in docs:
            if not isinstance(ref,dict): raise ValueError('Invalid reference PDF entry.')
            section=ref.get('section','all');name=ref.get('name','Reference.pdf');caption=ref.get('caption','')
            if section not in {'all',*FIELDS}: raise ValueError('Choose a valid PDF section.')
            if not isinstance(name,str) or len(name)>200 or not isinstance(caption,str) or len(caption)>1000: raise ValueError('PDF name or caption is too long.')
            if ref.get('data'):
                try: raw=base64.b64decode(ref['data'],validate=True)
                except Exception as e: raise ValueError('Invalid PDF encoding.') from e
                total+=len(raw)
                if len(raw)>20*1024*1024 or total>40*1024*1024: raise ValueError('PDFs must be under 20 MB each; new images and PDFs must total under 40 MB per save.')
                if not raw.startswith(b'%PDF-') or b'%%EOF' not in raw[-2048:]: raise ValueError('Upload a complete PDF file, not a renamed or truncated file.')
                document_id=secrets.token_hex(8)+'.pdf'
                pending_documents.append((document_id,raw))
                digest=hashlib.sha256(raw).hexdigest()
            else:
                document_id=ref.get('id');path=self.document(pid,document_id)
                digest=hashlib.sha256(path.read_bytes()).hexdigest()
            documents.append({'id':document_id,'name':name,'caption':caption,'section':section,'role':'core_reference','sha256':digest,'url':f'/api/brief-pdf/{pid}/{document_id}'})
        folder=self.folder(pid);folder.mkdir(parents=True,exist_ok=True)
        (folder/'images').mkdir(exist_ok=True)
        for image_id,raw in pending:
            with (folder/'images'/image_id).open('xb') as f:f.write(raw)
        if pending_documents:(folder/'documents').mkdir(exist_ok=True)
        for document_id,raw in pending_documents:
            with (folder/'documents'/document_id).open('xb') as f:f.write(raw)
        if old['revision']:
            (folder/'history').mkdir(exist_ok=True)
            with (folder/'history'/f'{old["revision"]}.json').open('x',encoding='utf-8') as f:json.dump(old,f,ensure_ascii=False,indent=2)
        doc={'schema_version':2,'owner':'user','assistant_access':'read-only','reference_policy':REFERENCE_POLICY,'project_id':pid,'revision':old['revision']+1,'fields':{k:fields.get(k,'') for k in FIELDS},'images':images,'documents':documents,'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
        temp=folder/'brief.tmp';temp.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(folder/'brief.json')
        return doc
