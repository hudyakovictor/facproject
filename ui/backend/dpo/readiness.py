"""Policy-driven readiness. No averaging and no invented scientific thresholds."""
from __future__ import annotations
from dataclasses import asdict,dataclass
import hashlib,json
from pathlib import Path
from typing import Any

DIMENSIONS=("implementation","unit","synthetic","integration","real_photo","calibration","docs","observability")
POLICIES={
 "utility":("implementation","unit","docs"),
 "critical_stage1":DIMENSIONS,
 "calibration":("implementation","unit","synthetic","real_photo","calibration","docs","observability"),
 "evidence":DIMENSIONS,
 "visual_only":("implementation","unit","docs"),
}
@dataclass(frozen=True)
class Dimension:
 name:str;state:str;source:str;reason:str
 def to_dict(self):return asdict(self)
@dataclass(frozen=True)
class Readiness:
 function_id:str;policy:str;status:str;dimensions:tuple[Dimension,...];missing:tuple[str,...];blocked_by:tuple[str,...];explanation:str;code_hash:str
 def to_dict(self):return {**asdict(self),"dimensions":[x.to_dict() for x in self.dimensions]}

def choose_policy(entry:Any)->str:
 fid=entry.id.lower()
 if "uv" in fid or "texture" in fid:return "visual_only"
 if "calibr" in fid:return "calibration"
 if "evidence" in fid or "decision" in fid:return "evidence"
 if entry.criticality=="critical" and ".stage1." in fid:return "critical_stage1"
 return "utility"
def decide_status(policy:str,dims:dict[str,Dimension],deprecated=False,experimental=False)->tuple[str,tuple[str,...],str]:
 required=POLICIES[policy];missing=tuple(x for x in required if dims[x].state!="passed")
 failed=tuple(x for x in required if dims[x].state=="failed")
 if deprecated:return "deprecated",missing,"Функция помечена deprecated."
 if failed:return "failing",missing,"Провалены обязательные проверки: "+", ".join(failed)
 if not missing:return "release_ready",(),"Все обязательные условия policy подтверждены."
 if "calibration" in missing and policy in {"critical_stage1","calibration","evidence"}:return "calibration_required",missing,"Без актуальной калибровки зелёный статус запрещён."
 if dims["real_photo"].state=="passed":return "real_photo_verified",missing,"Есть проверка на реальных фото, но не все обязательные условия закрыты."
 if dims["integration"].state=="passed":return "integration_verified",missing,"Интеграция проверена; остаются обязательные условия."
 if dims["synthetic"].state=="passed":return "synthetic_verified",missing,"Synthetic подтверждает contracts/regression, но не accuracy."
 if dims["implementation"].state=="passed":return "experimental" if experimental else "implemented_unverified",missing,"Код обнаружен, но обязательные доказательства зрелости неполны."
 return "discovered",missing,"Функция обнаружена, реализация не подтверждена."

def evaluate(project:Any,catalog:list[Any],bindings:list[Any],approvals:dict[str,dict[str,str]]|None=None)->list[Readiness]:
 approvals=approvals or {};bound={b.function_id for b in bindings};functions={f.id:f for f in project.functions};module_paths={m.id:m.source_path for m in project.modules};out=[]
 for e in catalog:
  f=functions[e.id];policy=choose_policy(e);manual=approvals.get(e.id,{})
  signals=getattr(f,"signals",getattr(f,"unfinished_signals",())) or ();implemented="failed" if any("raise_not_implemented" in str(x) for x in signals) else "passed"
  has_test=e.id in bound
  dims={x:Dimension(x,"unknown","none","Нет подтверждённого источника.") for x in DIMENSIONS}
  dims["implementation"]=Dimension("implementation",implemented,"ast","Статический анализ реализации.")
  dims["unit"]=Dimension("unit","passed" if has_test else "unknown","test_binding","Есть связанный тест." if has_test else "Связанный тест не найден.")
  dims["synthetic"]=Dimension("synthetic","passed" if has_test and "test_module" in str(module_paths[f.module_id]) else "unknown","test_index","Synthetic contract; не является forensic accuracy.")
  dims["docs"]=Dimension("docs","passed" if not e.task_priority else "unknown","catalog","Есть журналистское описание." if not e.task_priority else "Требуется ручное описание.")
  dims["observability"]=Dimension("observability","passed" if has_test else "unknown","test_binding","Есть наблюдаемая regression-точка." if has_test else "Нет наблюдаемой regression-точки.")
  for name in ("integration","real_photo","calibration"):
   if manual.get(name)==f.fingerprint:dims[name]=Dimension(name,"passed","manual_approval","Подтверждено вручную для текущего code hash.")
  status,missing,why=decide_status(policy,dims,experimental=e.status=="experimental")
  out.append(Readiness(e.id,policy,status,tuple(dims[x] for x in DIMENSIONS),missing,(),why,f.fingerprint))
 # Block callers without changing their own evidence to failed.
 by={x.function_id:x for x in out};blocked={x.function_id for x in out if x.status in {"failing","calibration_required"}}
 reverse={}
 for edge in project.edges():reverse.setdefault(edge.target,set()).add(edge.source)
 changed=True
 while changed:
  changed=False
  for target in tuple(blocked):
   for caller in reverse.get(target,()):
    if caller not in blocked:blocked.add(caller);changed=True
 result=[]
 for x in out:
  deps=tuple(sorted(t for t in blocked if t!=x.function_id and x.function_id in reverse.get(t,set())))
  result.append(Readiness(x.function_id,x.policy,x.status,x.dimensions,x.missing,deps,x.explanation,x.code_hash))
 return result

class SnapshotStore:
 def __init__(self,root:Path):self.root=root
 def save(self,items:list[Readiness])->Path:
  digest=hashlib.sha256("".join(sorted(x.code_hash for x in items)).encode()).hexdigest();path=self.root/f"{digest}.json";path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps({"schema":"dpo-readiness-v1","code_hash":digest,"items":[x.to_dict() for x in items]},sort_keys=True));tmp.replace(path);return path
