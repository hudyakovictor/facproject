"""Build/verify immutable manifests for calibration utility/prior artifacts."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

def digest(path:Path)->str:
 h=hashlib.sha256()
 with path.open("rb") as f:
  for chunk in iter(lambda:f.read(1<<20),b""):h.update(chunk)
 return h.hexdigest()

def build(root:Path,patterns=("landmark_utility*.npy","prior*.json","*calibration*.json"))->dict:
 files=[]
 for pattern in patterns:
  for path in sorted(root.rglob(pattern)):
   if path.is_file() and path.name!="calibration_artifact_manifest.json":files.append({"path":path.relative_to(root).as_posix(),"bytes":path.stat().st_size,"sha256":digest(path)})
 files={row["path"]:row for row in files}.values()
 return {"schema":"deeputin-calibration-artifacts-v1","root_role":"calibration_only","files":list(files)}

def verify(root:Path,manifest:dict)->list[str]:
 errors=[]
 for row in manifest.get("files",[]):
  path=root/row["path"]
  if not path.is_file():errors.append(f"missing:{row['path']}")
  elif digest(path)!=row["sha256"]:errors.append(f"digest_mismatch:{row['path']}")
 return errors

def main():
 p=argparse.ArgumentParser();p.add_argument("root",type=Path);p.add_argument("--verify",action="store_true");a=p.parse_args();out=a.root/"calibration_artifact_manifest.json"
 if a.verify:
  errors=verify(a.root,json.loads(out.read_text()));print(json.dumps({"status":"complete" if not errors else "invalid","errors":errors},indent=2));raise SystemExit(bool(errors))
 out.write_text(json.dumps(build(a.root),indent=2)+"\n");print(out)
if __name__=="__main__":main()
