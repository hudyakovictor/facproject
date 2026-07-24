"""Investigation Feedback Loop: root cause, prioritized spec, Fix Capsule, safe patch/backup/rollback."""
from __future__ import annotations
import hashlib,json,re,shutil,subprocess,tempfile,time,uuid
from dataclasses import asdict,dataclass
from datetime import datetime,timezone
from pathlib import Path
from typing import Any

PRIORITIES=("P0","P1","P2","P3")
_EXC_RE=re.compile(r"(Traceback \(most recent call last\)|\b\w*Error\b:|\bException\b)")
CRITICAL_CHECKS={"pair_status","pair_status_not","status_present","status_absent","corroboration","no_red_pairs","baseline_return_events","fdr_significant_fraction_max"}

def now()->str:return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class Classification:
 priority:str;category:str;human_summary:str;technical_summary:str;evidence:tuple[str,...]
 def to_dict(self)->dict:return asdict(self)

def classify_failure(run_record:dict,log_lines:list[str],check_result:dict|None=None)->Classification|None:
 status=run_record.get("status")
 if status=="succeeded" and (check_result is None or check_result.get("passed")):return None
 tail="\n".join(log_lines[-60:])
 has_exception=bool(_EXC_RE.search(tail))
 if status=="cancelled":
  return Classification("P3","cancelled_by_user","Запуск был отменён пользователем.","status=cancelled; "+str(run_record.get("reason") or ""),tuple(log_lines[-10:]))
 if status=="timed_out":
  return Classification("P1","timeout","Пайплайн не успел завершиться за отведённое время.",f"status=timed_out; reason={run_record.get('reason')}",tuple(log_lines[-15:]))
 if check_result is not None and not check_result.get("passed",True):
  failed=[c for c in check_result.get("checks",[]) if not c.get("ok")]
  if any(c.get("check")=="pipeline_complete" or "no measured pairs" in str(c.get("detail","")) for c in failed):
   return Classification("P0","no_measurable_output","Пайплайн не дал ни одной измеримой пары — результат нельзя доверять целиком.",json.dumps(failed[:3],ensure_ascii=False),tuple(log_lines[-15:]))
  if any(c.get("check") in CRITICAL_CHECKS for c in failed):
   return Classification("P1","scientific_contract_violation","Пайплайн нарушил научный контракт сценария (неверный статус пары или пропущенное подтверждение).",json.dumps(failed[:5],ensure_ascii=False),tuple(log_lines[-15:]))
  return Classification("P2","secondary_check_violation","Второстепенная проверка сценария не прошла.",json.dumps(failed[:5],ensure_ascii=False),tuple(log_lines[-15:]))
 if status=="failed" and has_exception:
  return Classification("P0","pipeline_crash","Пайплайн упал с исключением до получения результата.",tail[-1200:],tuple(log_lines[-20:]))
 if status=="failed":
  return Classification("P2","unclassified_failure","Запуск завершился ошибкой без распознанного исключения — нужен ручной разбор.",tail[-800:],tuple(log_lines[-15:]))
 return Classification("P3","informational","Запуск завершился без явной ошибки, но проверки не подтверждены.",tail[-400:],tuple(log_lines[-10:]))

def suspected_functions(scenario_block:str|None,function_matrix:list[dict])->list[dict]:
 if not scenario_block:return []
 return [{"code":r["code"],"what":r["what"],"status":r["status"]} for r in function_matrix if scenario_block in r.get("blocks",())]

def build_spec(run_record:dict,classification:Classification,*,scenario_id:str|None=None,scenario_block:str|None=None,function_matrix:list[dict]|None=None)->dict:
 funcs=suspected_functions(scenario_block,function_matrix or [])
 acceptance=["Повторный запуск того же runner/seed завершается со статусом succeeded."]
 if classification.category=="no_measurable_output":acceptance.append("pair_metrics.csv содержит хотя бы одну измеренную пару для использованных ракурсов.")
 if classification.category=="scientific_contract_violation":acceptance.append("Статус пары соответствует ожиданию сценария (any_of/none_of) без ослабления порогов.")
 if classification.category=="timeout":acceptance.append("Runner укладывается в текущий timeout без изменения timeout в runners.yaml.")
 return {"schema":"dpo-fix-spec-v1","priority":classification.priority,"category":classification.category,"title":f"[{classification.priority}] {classification.category}"+(f" — {scenario_id}" if scenario_id else ""),"human_summary":classification.human_summary,"technical_summary":classification.technical_summary,"reproduction":{"runner_id":run_record.get("runner_id"),"run_id":run_record.get("id"),"seed":run_record.get("seed"),"scenario_id":scenario_id,"code_hash":run_record.get("code_hash")},"suspected_functions":funcs,"acceptance_criteria":acceptance,"created_at":now()}

def build_capsule(spec:dict,evidence:tuple[str,...],*,capsule_root:Path)->dict:
 cid=uuid.uuid4().hex[:12]
 capsule={"schema":"dpo-fix-capsule-v1","id":cid,"spec":spec,"log_excerpt":list(evidence)[-40:],"created_at":now()}
 path=capsule_root/f"{cid}.json";path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(capsule,ensure_ascii=False,indent=1),encoding="utf-8")
 return {"id":cid,"path":str(path),"capsule":capsule}

def _sha256(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else ""

class BackupManager:
 """Text-file backups scoped to an allowlisted root; never touches .git."""
 def __init__(self,backup_root:Path,allowed_root:Path):
  self.backup_root=backup_root;self.allowed_root=allowed_root.resolve()
 def _check(self,rel:str)->Path:
  p=(self.allowed_root/rel).resolve()
  if ".git" in Path(rel).parts:raise ValueError("refusing to touch .git")
  if not str(p).startswith(str(self.allowed_root)+"/") and p!=self.allowed_root:raise ValueError(f"path escapes allowed root: {rel}")
  return p
 def create(self,relative_paths:list[str])->str:
  bid=uuid.uuid4().hex[:12];dest=self.backup_root/bid;dest.mkdir(parents=True,exist_ok=True)
  manifest={"schema":"dpo-backup-v1","id":bid,"created_at":now(),"files":[]}
  for rel in relative_paths:
   src=self._check(rel);target=dest/rel;target.parent.mkdir(parents=True,exist_ok=True)
   existed=src.is_file()
   if existed:shutil.copy2(src,target)
   manifest["files"].append({"path":rel,"existed":existed,"sha256":_sha256(src)})
  (dest/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=1),encoding="utf-8")
  return bid
 def rollback(self,backup_id:str)->list[str]:
  dest=self.backup_root/backup_id
  manifest=json.loads((dest/"manifest.json").read_text(encoding="utf-8"))
  restored=[]
  for entry in manifest["files"]:
   target=self._check(entry["path"])
   if entry["existed"]:
    shutil.copy2(dest/entry["path"],target)
   elif target.is_file():
    target.unlink()
   restored.append(entry["path"])
  return restored
 def list(self)->list[dict]:
  out=[]
  if self.backup_root.exists():
   for d in sorted(self.backup_root.iterdir()):
    mp=d/"manifest.json"
    if mp.is_file():out.append(json.loads(mp.read_text(encoding="utf-8")))
  return out

_DIFF_PATH_RE=re.compile(r"^\+\+\+ b/(.+)$",re.MULTILINE)

def diff_touched_paths(diff_text:str)->list[str]:
 out=[p for p in _DIFF_PATH_RE.findall(diff_text) if p!="/dev/null"]
 if not out:raise ValueError("diff does not reference any target file (+++ b/...)")
 return out

def _repo_root(path:Path)->Path:
 r=subprocess.run(["git","rev-parse","--show-toplevel"],cwd=str(path),capture_output=True,text=True)
 if r.returncode!=0:raise RuntimeError(f"not inside a git repository: {r.stderr.strip()[:300]}")
 return Path(r.stdout.strip())

def _apply_args(repo_root:Path,allowed_root:Path)->tuple[list[str],str]:
 """git apply must run from the repo root with --directory=<rel>, never with cwd set to a
 subdirectory: git apply can silently emit "Skipped patch" (returncode 0, no file changed)
 when cwd is a non-root subdirectory, so paths-relative-to-allowed_root diffs are only safe
 when prefixed via --directory from the true repo root."""
 rel=allowed_root.resolve().relative_to(repo_root)
 return (["--directory",str(rel)] if str(rel)!="." else []),str(repo_root)

def apply_patch(diff_text:str,*,allowed_root:Path,backup_manager:BackupManager)->dict:
 paths=diff_touched_paths(diff_text)
 for p in paths:backup_manager._check(p)
 repo_root=_repo_root(allowed_root)
 dir_args,cwd=_apply_args(repo_root,allowed_root)
 check=subprocess.run(["git","apply","--check","-p1",*dir_args,"-"],input=diff_text,text=True,capture_output=True,cwd=cwd)
 if check.returncode!=0:raise ValueError(f"patch failed dry-run check: {check.stderr.strip()[:600]}")
 backup_id=backup_manager.create(paths)
 applied=subprocess.run(["git","apply","-p1",*dir_args,"-"],input=diff_text,text=True,capture_output=True,cwd=cwd)
 if applied.returncode!=0:
  raise RuntimeError(f"patch apply failed after passing dry-run: {applied.stderr.strip()[:600]}")
 return {"backup_id":backup_id,"applied_files":paths}

@dataclass(frozen=True)
class IsolatedPatchResult:
 passed:bool;test_output:str;applied:bool;commit_sha:str|None;error:str|None;backup_id:str|None
 def to_dict(self)->dict:return asdict(self)

def run_isolated_patch(diff_text:str,*,allowed_root:Path,backup_manager:BackupManager,test_cmd:list[str],timeout:int=600,commit_message:str="dpo: apply investigated patch")->dict:
 """Apply a diff in a disposable git worktree, run test_cmd there, and only touch the
 real allowed_root (creating a file backup first, then a real commit) if those tests pass.
 If tests fail or the worktree apply fails, the real tree is never modified."""
 paths=diff_touched_paths(diff_text)
 for p in paths:backup_manager._check(p)
 repo_root=_repo_root(allowed_root)
 rel_allowed=allowed_root.resolve().relative_to(repo_root)
 staging=Path(tempfile.mkdtemp(prefix="dpo-patch-"))
 try:
  add=subprocess.run(["git","worktree","add","-f","--detach",str(staging),"HEAD"],cwd=str(repo_root),capture_output=True,text=True)
  if add.returncode!=0:raise RuntimeError(f"failed to create isolated worktree: {add.stderr.strip()[:400]}")
  # Apply from the worktree TOP with --directory=<rel_allowed>, not by cd-ing into the
  # subdirectory: git apply can silently "Skipped patch" a file (returncode 0, no file changed)
  # when invoked with cwd set to a non-root subdirectory, leaving the tree untouched with no error.
  directory_args=["--directory",str(rel_allowed)] if str(rel_allowed)!="." else []
  check=subprocess.run(["git","apply","--check","-p1",*directory_args,"-"],input=diff_text,text=True,capture_output=True,cwd=str(staging))
  if check.returncode!=0:
   return IsolatedPatchResult(False,"",False,None,f"dry-run check failed in isolated worktree: {check.stderr.strip()[:600]}",None).to_dict()
  applied=subprocess.run(["git","apply","-p1",*directory_args,"-"],input=diff_text,text=True,capture_output=True,cwd=str(staging))
  if applied.returncode!=0:
   return IsolatedPatchResult(False,"",False,None,f"patch apply failed in isolated worktree: {applied.stderr.strip()[:600]}",None).to_dict()
  try:
   test=subprocess.run(test_cmd,cwd=str(staging),capture_output=True,text=True,timeout=timeout)
  except subprocess.TimeoutExpired:
   return IsolatedPatchResult(False,f"isolated test run timed out after {timeout}s",False,None,"timeout",None).to_dict()
  test_output=(test.stdout[-4000:]+"\n"+test.stderr[-4000:]).strip()
  if test.returncode!=0:
   return IsolatedPatchResult(False,test_output,False,None,"tests failed in isolated worktree; real files were not touched",None).to_dict()
  backup_id=backup_manager.create(paths)
  real_check=subprocess.run(["git","apply","--check","-p1",*directory_args,"-"],input=diff_text,text=True,capture_output=True,cwd=str(repo_root))
  if real_check.returncode!=0:
   raise RuntimeError(f"patch passed isolated dry-run but failed against real tree: {real_check.stderr.strip()[:600]}")
  real_apply=subprocess.run(["git","apply","-p1",*directory_args,"-"],input=diff_text,text=True,capture_output=True,cwd=str(repo_root))
  if real_apply.returncode!=0:
   raise RuntimeError(f"patch passed isolated apply but failed against real tree: {real_apply.stderr.strip()[:600]}")
  add_git=subprocess.run(["git","add","--",*paths],cwd=str(allowed_root),capture_output=True,text=True)
  if add_git.returncode!=0:raise RuntimeError(f"git add failed after apply: {add_git.stderr.strip()[:400]}")
  commit=subprocess.run(["git","-c","user.email=dpo@local","-c","user.name=DPO Patch Center","commit","-q","-m",commit_message],cwd=str(repo_root),capture_output=True,text=True)
  if commit.returncode!=0:
   raise RuntimeError(f"real tree was patched and staged but commit failed: {commit.stderr.strip()[:600]}")
  sha=subprocess.run(["git","rev-parse","HEAD"],cwd=str(repo_root),capture_output=True,text=True)
  commit_sha=sha.stdout.strip() if sha.returncode==0 else None
  return IsolatedPatchResult(True,test_output,True,commit_sha,None,backup_id).to_dict()
 finally:
  subprocess.run(["git","worktree","remove","--force",str(staging)],cwd=str(repo_root),capture_output=True,text=True)
  shutil.rmtree(staging,ignore_errors=True)

def revert_patch_commit(commit_sha:str,*,allowed_root:Path)->dict:
 """Safely undo a commit created by run_isolated_patch via git revert (keeps history, unlike file backups)."""
 repo_root=_repo_root(allowed_root)
 result=subprocess.run(["git","-c","user.email=dpo@local","-c","user.name=DPO Patch Center","revert","--no-edit",commit_sha],cwd=str(repo_root),capture_output=True,text=True)
 if result.returncode!=0:
  subprocess.run(["git","revert","--abort"],cwd=str(repo_root),capture_output=True,text=True)
  raise RuntimeError(f"revert failed: {result.stderr.strip()[:600]}")
 sha=subprocess.run(["git","rev-parse","HEAD"],cwd=str(repo_root),capture_output=True,text=True)
 return {"reverted_commit":commit_sha,"revert_commit":sha.stdout.strip() if sha.returncode==0 else None}
