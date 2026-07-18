#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,os,subprocess,sys,threading,time,uuid
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent; PROJECT=ROOT.parent; WORK=PROJECT/'ui_workspace'; WORK.mkdir(exist_ok=True)
JOBS={}; SESSIONS={}
def ready(p): return (Path(p)/'reconstruction.npz').is_file()
def kabsch(a,b):
 ca=a.mean(0);cb=b.mean(0);u,_,vt=np.linalg.svd((b-cb).T@(a-ca));r=u@vt
 if np.linalg.det(r)<0:vt[-1]*=-1;r=u@vt
 return (b-cb)@r+ca
class H(SimpleHTTPRequestHandler):
 def end_headers(self): self.send_header('Cache-Control','no-store');super().end_headers()
 def json(self,x,status=200):
  b=json.dumps(x,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def body(self): return json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or b'{}')
 def do_GET(self):
  if self.path.startswith('/api/system/doctor'):
   mods={x:importlib.util.find_spec(x) is not None for x in ['cv2','numpy','torch','skimage','skan','scipy']};assets={x:(PROJECT/'3ddfav3/assets'/x).is_file() for x in ['face_model.npy','net_recon.pth','large_base_net.pth']};return self.json({'platform':sys.platform,'python':sys.version.split()[0],'modules':mods,'assets':assets,'ready':all(mods.values()) and all(assets.values())})
  if self.path=='/api/jobs': return self.json(list(JOBS.values()))
  if self.path.startswith('/api/comparison/'):
   sid=self.path.rsplit('/',1)[-1];return self.json(SESSIONS.get(sid,{}),200 if sid in SESSIONS else 404)
  return super().do_GET()
 def do_POST(self):
  try:
   if self.path=='/api/system/recheck': return self.do_GET()
   if self.path=='/api/calibration/start':
    x=self.body();jid=uuid.uuid4().hex[:10];log=WORK/f'{jid}.log';cmd=[sys.executable,str(PROJECT/'run_calibration.py'),'--input',x['input'],'--output',x.get('output','runs/calibration'),'--target-false-anomaly',str(x.get('target_false_anomaly',.01))];job={'id':jid,'kind':'calibration','status':'running','progress':0,'log':str(log)};JOBS[jid]=job
    def run():
     with log.open('w') as f:p=subprocess.run(cmd,cwd=PROJECT,stdout=f,stderr=subprocess.STDOUT);job.update(status='completed' if p.returncode==0 else 'failed',progress=1,returncode=p.returncode)
    threading.Thread(target=run,daemon=True).start();return self.json(job,201)
   if self.path=='/api/comparison/prepare':
    x=self.body();pa,pb=Path(x['record_a']).resolve(),Path(x['record_b']).resolve()
    if not ready(pa) or not ready(pb):return self.json({'error':'Both paths must be Stage-1 record directories'},400)
    with np.load(pa/'reconstruction.npz',allow_pickle=False) as za,np.load(pb/'reconstruction.npz',allow_pickle=False) as zb:
     a=np.asarray(za['vertices_identity_only'],np.float32);b=kabsch(a,np.asarray(zb['vertices_identity_only'],np.float32));tri=np.asarray(za['triangles'],np.int64);uv=np.asarray(za['uv_coords'],np.float32)
    if len(a)!=len(b):return self.json({'error':'Topology mismatch'},400)
    d=np.linalg.norm(a-b,axis=1);sid=uuid.uuid4().hex[:10];mesh={'a':a.reshape(-1).round(6).tolist(),'b':b.reshape(-1).round(6).tolist(),'uv':uv[:,:2].reshape(-1).round(6).tolist(),'tri':tri.reshape(-1).tolist(),'metrics':{'rmse':float(np.sqrt(np.mean(d*d))),'p95':float(np.percentile(d,95)),'max':float(d.max())}}
    SESSIONS[sid]={'id':sid,'metrics':mesh['metrics'],'mesh':mesh};return self.json(SESSIONS[sid],201)
   return self.json({'error':'not found'},404)
  except Exception as e:return self.json({'error':f'{type(e).__name__}: {e}'},500)
def main():
 p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8765);a=p.parse_args();os.chdir(ROOT/'dist');ThreadingHTTPServer(('127.0.0.1',a.port),H).serve_forever()
if __name__=='__main__':main()
