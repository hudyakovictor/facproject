"""Allowlisted, isolated run manager with compact metadata and JSONL events."""
from __future__ import annotations
from dataclasses import asdict,dataclass
from datetime import datetime,timezone
import hashlib,json,os,queue,signal,subprocess,sys,threading,time,uuid
from pathlib import Path
from typing import Any

SCHEMA="dpo-run-event-v1";TERMINAL={"succeeded","failed","cancelled","timed_out","interrupted"}
def now()->str:return datetime.now(timezone.utc).isoformat()
@dataclass(frozen=True)
class RunnerSpec:
 id:str;title:str;module:str;fixed_args:tuple[str,...]=();timeout:int=300
@dataclass
class RunRecord:
 id:str;runner_id:str;status:str;created_at:str;started_at:str|None=None;finished_at:str|None=None;pid:int|None=None;exit_code:int|None=None;reason:str|None=None;code_hash:str="";config_hash:str="";seed:int=0
 def to_dict(self):return asdict(self)
class RunnerRegistry:
 def __init__(self,specs:list[RunnerSpec]):
  self._specs={s.id:s for s in specs}
  if len(self._specs)!=len(specs):raise ValueError("duplicate runner id")
 def get(self,id:str)->RunnerSpec:
  if id not in self._specs:raise ValueError("runner is not allowlisted")
  return self._specs[id]
 def list(self):return list(self._specs.values())
class EventLog:
 def __init__(self,path:Path):self.path=path;path.parent.mkdir(parents=True,exist_ok=True);self._lock=threading.Lock();self._seq=0
 def emit(self,type:str,**payload:Any):
  with self._lock:
   self._seq+=1;event={"schema":SCHEMA,"seq":self._seq,"ts":now(),"type":type,"payload":payload}
   with self.path.open("a",encoding="utf-8") as f:f.write(json.dumps(event,ensure_ascii=False)+"\n")
 def read(self,after:int=0)->list[dict]:
  out=[]
  if not self.path.exists():return out
  for line in self.path.read_text(encoding="utf-8",errors="replace").splitlines():
   try:e=json.loads(line)
   except json.JSONDecodeError:continue
   if e.get("schema")==SCHEMA and isinstance(e.get("seq"),int) and e["seq"]>after:out.append(e)
  return out
class RunManager:
 def __init__(self,registry:RunnerRegistry,app_root:Path,control_root:Path,heavy_root:Path,max_parallel:int=1):
  if max_parallel!=1:raise ValueError("MVP enforces max_parallel=1")
  self.registry=registry;self.app_root=app_root.resolve();self.control=control_root;self.heavy=heavy_root;self.records={};self.procs={};self.logs={};self.cancel_requested=set();self.q=queue.Queue();self.lock=threading.Lock();self.stop_event=threading.Event();self.worker=threading.Thread(target=self._worker,daemon=True);self.worker.start();self._recover()
 def _hash_tree(self)->str:
  h=hashlib.sha256()
  for p in sorted(self.app_root.rglob("*.py")):h.update(str(p.relative_to(self.app_root)).encode());h.update(p.read_bytes())
  return h.hexdigest()
 def _persist(self,r:RunRecord):
  p=self.control/"runs"/f"{r.id}.json";p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(r.to_dict(),sort_keys=True));tmp.replace(p)
 def _recover(self):
  for p in (self.control/"runs").glob("*.json") if (self.control/"runs").exists() else ():
   try:r=RunRecord(**json.loads(p.read_text()))
   except Exception:continue
   if r.status not in TERMINAL:r.status="interrupted";r.finished_at=now();r.reason="UI restarted";self._persist(r)
   self.records[r.id]=r
 def submit(self,runner_id:str,seed:int=0)->RunRecord:
  self.registry.get(runner_id);rid=uuid.uuid4().hex;r=RunRecord(rid,runner_id,"queued",now(),code_hash=self._hash_tree(),config_hash=hashlib.sha256(f"{runner_id}:{seed}".encode()).hexdigest(),seed=int(seed));self.records[rid]=r;self.logs[rid]=EventLog(self.heavy/"runs"/rid/"events.jsonl");self._persist(r);self.logs[rid].emit("queued",runner_id=runner_id);self.q.put(rid);return r
 def get(self,rid:str)->RunRecord:
  if rid not in self.records:raise KeyError(rid)
  return self.records[rid]
 def events(self,rid:str,after:int=0):return self.logs.setdefault(rid,EventLog(self.heavy/"runs"/rid/"events.jsonl")).read(after)
 def cancel(self,rid:str):
  r=self.get(rid)
  if r.status=="queued":r.status="cancelled";r.finished_at=now();r.reason="cancelled before start";self._persist(r);return
  self.cancel_requested.add(rid);r.reason="cancel requested"
  p=self.procs.get(rid)
  if p and p.poll() is None:os.killpg(p.pid,signal.SIGTERM)
 def _worker(self):
  while not self.stop_event.is_set():
   try:rid=self.q.get(timeout=.1)
   except queue.Empty:continue
   r=self.records[rid]
   if r.status=="cancelled":continue
   self._execute(r)
 def _execute(self,r:RunRecord):
  spec=self.registry.get(r.runner_id);log=self.logs[r.id];r.status="running";r.started_at=now();self._persist(r);log.emit("started",runner_id=spec.id)
  cmd=[sys.executable,"-m",spec.module,*spec.fixed_args];p=subprocess.Popen(cmd,cwd=self.app_root.parent,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,start_new_session=True,env={**os.environ,"PYTHONHASHSEED":str(r.seed),"PYTHONUNBUFFERED":"1"});self.procs[r.id]=p;r.pid=p.pid;self._persist(r);deadline=time.monotonic()+spec.timeout
  def stream_output():
   if p.stdout:
    for line in p.stdout:log.emit("log",text=line.rstrip()[:4000])
  reader=threading.Thread(target=stream_output,daemon=True);reader.start()
  while p.poll() is None:
   if time.monotonic()>deadline:os.killpg(p.pid,signal.SIGKILL);r.status="timed_out";r.reason=f"timeout {spec.timeout}s";break
   if r.id in self.cancel_requested:time.sleep(.15)
   if r.id in self.cancel_requested and p.poll() is None:os.killpg(p.pid,signal.SIGKILL);r.status="cancelled";break
   time.sleep(.03)
  r.exit_code=p.wait();reader.join(timeout=2)
  if p.stdout:p.stdout.close()
  r.finished_at=now()
  if r.id in self.cancel_requested:r.status="cancelled"
  elif r.status=="running":r.status="succeeded" if r.exit_code==0 else "failed"
  log.emit("finished",status=r.status,exit_code=r.exit_code,reason=r.reason);self._persist(r);self.procs.pop(r.id,None);self.cancel_requested.discard(r.id)
 def shutdown(self):self.stop_event.set();self.worker.join(timeout=1)
