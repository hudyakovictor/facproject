import hashlib,json
from pathlib import Path
def load_config(*paths,overrides=None):
 out={}
 def merge(a,b):
  for k,v in b.items():a[k]=merge(dict(a.get(k,{})),v) if isinstance(v,dict) else v
  return a
 for p in paths:merge(out,json.loads(Path(p).read_text()))
 if overrides:merge(out,overrides)
 return out,hashlib.sha256(json.dumps(out,sort_keys=True,separators=(',',':')).encode()).hexdigest()
