"""Stable pipeline-canvas graph and local layout persistence."""
from __future__ import annotations
from dataclasses import asdict, dataclass
import json, re
from pathlib import Path
from typing import Any
from .indexer.project_index import ProjectIndex

STAGES=("stage1","stage2","stage2b","stage3","test_module","shared")
@dataclass(frozen=True)
class CanvasNode:
 id:str;kind:str;title:str;technical_name:str;parent_id:str|None;stage:str;status:str;criticality:str;x:float;y:float;badges:tuple[str,...]=()
 def to_dict(self)->dict[str,Any]:return asdict(self)
@dataclass(frozen=True)
class CanvasEdge:
 id:str;source:str;target:str;confidence:str;label:str
 def to_dict(self)->dict[str,Any]:return asdict(self)

def stage_of(path:str)->str:
 return next((p for p in path.split('/') if p in STAGES),"shared")
def build_canvas_graph(project:ProjectIndex,catalog:list[Any],readiness:list[Any]|None=None)->dict[str,Any]:
 cat={x.id:x for x in catalog};ready={x.function_id:x for x in (readiness or [])};nodes=[];edges=[];module_map={m.id:m for m in project.modules};used_stages=sorted({stage_of(m.source_path) for m in project.modules},key=lambda x:STAGES.index(x))
 for si,stage in enumerate(used_stages):nodes.append(CanvasNode(f"stage:{stage}","stage",stage.upper(),stage,None,stage,"discovered","normal",si*520,0))
 modules=sorted(project.modules,key=lambda m:(STAGES.index(stage_of(m.source_path)),m.source_path))
 module_row={}
 for m in modules:
  stage=stage_of(m.source_path);row=module_row.get(stage,0);module_row[stage]=row+1;mid=f"module:{m.id}";nodes.append(CanvasNode(mid,"module",Path(m.source_path).stem.replace('_',' ').title(),m.id,f"stage:{stage}",stage,"discovered","normal",STAGES.index(stage)*520,120+row*190))
  edges.append(CanvasEdge(f"contains:{stage}:{m.id}",f"stage:{stage}",mid,"confirmed_static","contains"))
 for f in project.functions:
  m=module_map[f.module_id];entry=cat.get(f.id);stage=stage_of(m.source_path);mid=f"module:{m.id}";row=sorted(x.id for x in m.functions).index(f.id);badges=[]
  if entry and entry.task_priority:badges.append(entry.task_priority)
  if f.id in ready and ready[f.id].blocked_by:badges.append('downstream-blocked')
  if any(x in m.source_path.lower() for x in ('uv','texture')):badges.append('visual-only')
  nodes.append(CanvasNode(f"function:{f.id}","function",entry.title if entry else f.technical_name.replace('_',' ').title(),f.id,mid,stage,ready[f.id].status if f.id in ready else (entry.status if entry else 'discovered'),entry.criticality if entry else 'normal',STAGES.index(stage)*520+220,150+row*86,tuple(badges)))
  edges.append(CanvasEdge(f"contains:{m.id}:{f.id}",mid,f"function:{f.id}","confirmed_static","contains"))
  if f.technical_name.startswith(('save_','write_')) or 'report' in f.technical_name:
   aid=f"artifact:{f.id}";nodes.append(CanvasNode(aid,"artifact",f"Результат: {f.technical_name.replace('_',' ')}",f.technical_name,f"function:{f.id}",stage,"discovered","normal",STAGES.index(stage)*520+430,150+row*86,('visual-only',) if 'texture' in f.id or 'uv' in f.id else ()))
   edges.append(CanvasEdge(f"produces:{f.id}",f"function:{f.id}",aid,"heuristic_static","produces"))
 for e in project.edges():edges.append(CanvasEdge(f"call:{e.source}:{e.target}:{e.line}",f"function:{e.source}",f"function:{e.target}",e.confidence.value,"calls"))
 presets={"Full":[n.id for n in nodes],"Stage1":[n.id for n in nodes if n.stage=='stage1'],"Geometry":[n.id for n in nodes if 'geometry' in n.technical_name.lower()],"Calibration":[n.id for n in nodes if 'calibr' in n.technical_name.lower()],"Evidence":[n.id for n in nodes if 'evidence' in n.technical_name.lower()],"Testing":[n.id for n in nodes if n.stage=='test_module'],"Blockers":[n.id for n in nodes if n.status in {'need_testing','in_progress','blocked'}]}
 return {"nodes":[n.to_dict() for n in nodes],"edges":[e.to_dict() for e in edges],"presets":presets,"summary":{"nodes":len(nodes),"edges":len(edges)}}

class LayoutStore:
 def __init__(self,root:Path):self.root=root
 def _path(self,name:str)->Path:
  if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}",name):raise ValueError('invalid layout name')
  return self.root/f"{name}.json"
 def save(self,name:str,positions:dict[str,dict[str,float]])->Path:
  path=self._path(name);path.parent.mkdir(parents=True,exist_ok=True);clean={k:{"x":float(v['x']),"y":float(v['y'])} for k,v in positions.items()};tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps({"schema":"dpo-layout-v1","positions":clean},sort_keys=True));tmp.replace(path);return path
 def load(self,name:str)->dict[str,Any]|None:
  path=self._path(name);return json.loads(path.read_text()) if path.exists() else None
