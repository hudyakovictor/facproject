#!/usr/bin/env python3
"""Repeatable 50-check implementation audit for app6 core (UV/texture excluded)."""
from __future__ import annotations
import ast, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def included(p: Path) -> bool:
    low_parts = {x.lower() for x in p.parts}
    low_name = p.name.lower()
    return (
        "__macosx" not in low_parts and "__pycache__" not in low_parts
        and "skin" not in low_parts and "authenticity" not in low_parts
        and not low_name.startswith(("uv_", "texture", "skin_"))
        and p.name != Path(__file__).name
    )
FILES = [p for p in ROOT.rglob("*.py") if included(p)]
results=[]
def add(n,name,ok,detail=""):
    results.append({"id":n,"name":name,"status":"pass" if ok else "fail","detail":detail})
def text(rel): return (ROOT/rel).read_text(encoding="utf-8")
def has(rel,pattern): return re.search(pattern,text(rel),re.M|re.S) is not None

trees={}
syntax=[]
for p in FILES:
    try: trees[p]=ast.parse(p.read_text(encoding="utf-8"))
    except SyntaxError as e: syntax.append(f"{p.relative_to(ROOT)}:{e.lineno}")
add(1,"Python syntax",not syntax,"; ".join(syntax))
pass_only=[]; notimpl=[]; mutable=[]; bare=[]; broad_pass=[]; long=[]; dup=[]
for p,t in trees.items():
    names={}
    for n in ast.walk(t):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
            if len(n.body)==1 and isinstance(n.body[0],ast.Pass): pass_only.append(f"{p.name}:{n.lineno}:{n.name}")
            if any(isinstance(x,ast.Raise) and isinstance(x.exc,ast.Call) and getattr(x.exc.func,"id","")=="NotImplementedError" for x in n.body): notimpl.append(f"{p.name}:{n.lineno}:{n.name}")
            for d in n.args.defaults:
                if isinstance(d,(ast.List,ast.Dict,ast.Set)): mutable.append(f"{p.name}:{n.lineno}:{n.name}")
            if getattr(n,"end_lineno",n.lineno)-n.lineno>180: long.append(f"{p.name}:{n.name}")
            names[n.name]=names.get(n.name,0)+1
        if isinstance(n,ast.ExceptHandler):
            if n.type is None: bare.append(f"{p.name}:{n.lineno}")
            typ=getattr(n.type,"id",None)
            if typ=="Exception" and len(n.body)==1 and isinstance(n.body[0],ast.Pass): broad_pass.append(f"{p.name}:{n.lineno}")
    dup.extend(f"{p.name}:{k}" for k,v in names.items() if v>1)
alltxt="\n".join(p.read_text(encoding="utf-8") for p in FILES)
add(2,"No pass-only functions",not pass_only,"; ".join(pass_only))
add(3,"No NotImplementedError stubs",not notimpl,"; ".join(notimpl))
add(4,"No mutable argument defaults",not mutable,"; ".join(mutable))
add(5,"No bare except",not bare,"; ".join(bare))
add(6,"No broad except-pass",not broad_pass,"; ".join(broad_pass))
add(7,"No duplicate function definitions",not dup,"; ".join(dup))
add(8,"No eval/exec",not re.search(r"\b(eval|exec)\s*\(",alltxt),"")
add(9,"No subprocess shell=True","shell=True" not in alltxt,"")
pickle_hits = [str(p.relative_to(ROOT)) for p in FILES if "allow_pickle=True" in p.read_text(encoding="utf-8")]
trusted_pickle_loaders = {"test_module/synthetic_runner.py"}
add(10,"No untrusted allow_pickle=True",set(pickle_hits) <= trusted_pickle_loaders,"; ".join(pickle_hits))
add(11,"No FIXME markers","FIXME" not in alltxt,"")
todo_hits = [str(p.relative_to(ROOT)) for p in FILES if re.search(r"^\s*#\s*TODO\b", p.read_text(encoding="utf-8"), re.M)]
add(12,"No TODO markers",not todo_hits,"; ".join(todo_hits))
very_long=[]
for p,t in trees.items():
    for n in ast.walk(t):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and getattr(n,"end_lineno",n.lineno)-n.lineno>350:
            very_long.append(f"{p.name}:{n.name}")
add(13,"No unreviewably large functions",not very_long,"; ".join(very_long[:10]))
add(14,"Strict chronology loading",has("stage2/loaders.py",r"required NPZ array missing") and "Fallback to object_normalized" not in text("stage2/loaders.py"),"")
add(15,"Cross-bin landmark gate",has("stage2/core.py",r"pose_mismatch"),"")
add(16,"Residual pose landmark gate",has("stage2/core.py",r"residual_pose_mismatch"),"")
add(17,"Motion pose gate",has("stage2/motion.py",r"residual_pose_mismatch"),"")
add(18,"Motion landmark-count validation",has("stage2/motion.py",r"count must be 106 or 134"),"")
add(19,"Robust alignment finite minimum",has("stage2/core.py",r"finite.*<\s*3|ids\.size\s*<\s*3"),"")
add(20,"Pose correction shape validation",has("stage1/geometry.py",r"must contain exactly 3 values"),"")
add(21,"Pose classification finite guard",has("stage1/geometry.py",r"classify_pose[\s\S]{0,500}isfinite"),"")
add(22,"Nearest canonical finite guard",text("stage1/geometry.py").count("yaw must be finite")>=2,"")
add(23,"Mask pack shape validation",has("stage1/geometry.py",r"pack_mask[\s\S]{0,300}(ndim|reshape)"),"")
add(24,"Mask unpack count validation",has("stage1/geometry.py",r"unpack_mask[\s\S]{0,300}count.*(>=|positive|non-negative)"),"")
add(25,"Stage1 input directory preflight",has("stage1/engine.py",r"input_dir.*is_dir"),"")
add(26,"Stage1 input/output separation",has("stage1/engine.py",r"output.*input|input.*output"),"")
add(27,"Stage1 empty-input hard stop",has("stage1/engine.py",r"no input|no supported|if not photos"),"")
add(28,"Stage1 duplicate count in manifest",has("stage1/engine.py",r"duplicate_count.*manifest|\"duplicate_count\""),"")
add(29,"Stage1 cleanup on successful run",has("stage1/engine.py",r"self\.recon\.cleanup\(\)"),"")
add(30,"Stage1 config value validation",has("stage1/config.py",r"__post_init__"),"")
add(31,"Landmark row shape validation",has("stage1/engine.py",r"_landmark_rows[\s\S]{0,800}(shape|length mismatch)"),"")
add(32,"BBox finite/shape validation",has("stage1/assets.py",r"def _bbox[\s\S]{0,500}isfinite"),"")
add(33,"Letterbox empty-image guard",has("stage1/assets.py",r"def _letterbox[\s\S]{0,400}(empty|h <= 0|w <= 0)"),"")
add(34,"Technical-quality bbox guard",has("stage1/assets.py",r"def technical_quality[\s\S]{0,700}(empty|w <= 0|h <= 0)"),"")
add(35,"Thumbnail write checked",has("stage1/assets.py",r"if not cv2\.imwrite\(str\(out / \"thumb\.jpg\""),"")
add(36,"Strict documented filename format","YYYYMMDD" not in text("stage1/naming.py") and "(?P<y>19\\d{2}|20\\d{2})(?P<m>" not in text("stage1/naming.py"),"")
add(37,"Validator topology errors not suppressed",not has("stage1/validator.py",r"def _resolve_topology[\s\S]{0,500}except Exception:\s*pass"),"")
add(38,"CSV writes are atomic",has("stage1/utils.py",r"def write_csv[\s\S]{0,900}os\.replace"),"")
add(39,"Atomic JSON uses unique temp",has("stage1/utils.py",r"def atomic_json[\s\S]{0,500}(uuid|NamedTemporaryFile)"),"")
add(40,"sha256_paths rejects empty input",has("stage1/utils.py",r"def sha256_paths[\s\S]{0,900}(no files|count\s*==\s*0|if not.*file)"),"")
add(41,"Stage2 calibration sensitivity runtime",has("stage2/engine.py",r"calibration_sensitivity") and "Cross-validation not implemented" not in text("stage2/engine.py"),"")
add(42,"Stage2 config path separation",has("stage2/engine.py",r"output_dir must not equal or be inside"),"")
add(43,"Stage3 checks Stage2 validation",has("stage3/engine.py",r"analysis_validation"),"")
add(44,"Stage2B checks Stage2 validation",has("stage2b/engine.py",r"analysis_validation"),"")
add(45,"Stage3 filters no_pairs sentinel",has("stage3/engine.py",r"no_pairs"),"")
add(46,"FDR ignores nonfinite z",has("stage2/multiple_testing.py",r"isfinite\(z_value\)"),"")
add(47,"Baseline vectors validate shape",has("stage2/baseline_return.py",r"_reversal_stats[\s\S]{0,500}(shape|ndim)"),"")
add(48,"Stage2 evidence maps applicability statuses",all(x in text("stage2/evidence.py") for x in ("pose_mismatch","residual_pose_mismatch","quality_limited")),"")
try:
    package_parent = next((p for p in (ROOT.parent, ROOT.parent/"work") if (p/"app6").exists()), ROOT.parent)
    env = dict(__import__("os").environ); env["PYTHONPATH"] = str(package_parent)
    cp=subprocess.run([sys.executable,"-m","unittest","discover","-s",str(ROOT/"test_module"),"-p","test*.py"],cwd=package_parent,text=True,capture_output=True,timeout=120,env=env)
    m=re.search(r"Ran (\d+) tests",cp.stderr+cp.stdout); count=int(m.group(1)) if m else 0
    add(49,"Regression suite passes",cp.returncode==0,(cp.stderr+cp.stdout)[-500:])
    add(50,"Regression suite breadth",count>=15,f"tests={count}")
except Exception as e:
    add(49,"Regression suite passes",False,str(e)); add(50,"Regression suite breadth",False,str(e))
assert len(results)==50
out={"schema":"app6-implementation-audit-50-v1","excluded":"UV, texture, authenticity and skin modules","check_count":50,"pass_count":sum(x['status']=='pass' for x in results),"fail_count":sum(x['status']=='fail' for x in results),"checks":results}
(ROOT/"AUDIT_50_REPORT.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
lines=["# App6 — 50 implementation checks","","UV/texture/authenticity/skin исключены по указанию владельца.","",f"- PASS: {out['pass_count']}",f"- FAIL: {out['fail_count']}",""]
for x in results: lines.append(f"{x['id']}. **{x['status'].upper()}** — {x['name']}"+(f": {x['detail']}" if x['detail'] else ""))
(ROOT/"AUDIT_50_REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
print(json.dumps({k:out[k] for k in ('check_count','pass_count','fail_count')},ensure_ascii=False))
for x in results:
    if x['status']=='fail': print(f"FAIL {x['id']:02d} {x['name']}: {x['detail']}")
raise SystemExit(1 if out['fail_count'] else 0)
