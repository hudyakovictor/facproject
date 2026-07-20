from __future__ import annotations
import hashlib,platform,sys,time
from pathlib import Path
from .contracts import SCHEMAS
from .serialization import atomic_json,canonical_hash,inventory,sha256_file

def decoded_sha256(image)->str:return hashlib.sha256(memoryview(image).cast('B')).hexdigest()
def create_manifest(photo_id,input_path,image,*,capture_event_id=None,coordinate_chain=None,models=None,atlas=None,config=None,backend=None,warnings=()):
 return {'schema':SCHEMAS['manifest'],'photo_id':photo_id,'input_sha256':sha256_file(input_path),'decoded_sha256':decoded_sha256(image),'capture_event_id':capture_event_id,'source':{'path':str(input_path),'width':int(image.shape[1]),'height':int(image.shape[0]),'channels':int(image.shape[2]) if image.ndim==3 else 1},'coordinate_chain':coordinate_chain or {},'models':models or {},'atlas':atlas or {},'config_sha256':canonical_hash(config or {}),'backend':backend or {'python':sys.version.split()[0],'platform':platform.platform()},'products':{},'warnings':list(warnings),'state':'partial'}
def finalize_manifest(root:Path,manifest:dict,state='success'):
 manifest=dict(manifest);manifest['products']=inventory(root);manifest['state']=state;manifest['finalized_unix']=time.time();atomic_json(root/'manifest.json',manifest)
 if state=='success':(root/'SUCCESS').write_text(manifest['config_sha256']+'\n',encoding='ascii')
 return manifest
