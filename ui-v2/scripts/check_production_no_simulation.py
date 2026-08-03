from pathlib import Path
import re,sys
root=Path(__file__).resolve().parents[1]
patterns={"generated_data":r"loadDemoPhotos|buildDemoPhotos|mulberry32|Math\.random\(","illustrative_geometry":r"illustrativeLandmarks|Synthetic PCA|source_mode\s*[:=]\s*[\"\']demo","fabricated_zone":r"z[A-Za-z]+\s*\*\s*0\.[0-9]"}
errors=[]
for path in (root/"src").rglob("*"):
    if not path.is_file() or path.suffix not in {".ts",".tsx"} or "test" in path.parts or path.name == "demoData.ts": continue
    text=path.read_text(encoding="utf-8")
    for name,pattern in patterns.items():
        if re.search(pattern,text,re.I): errors.append(f"{name}: {path.relative_to(root)}")
api=(root/"src/api.ts").read_text()
for marker in ["Non-research timeline rejected","Non-research comparison rejected","Non-research photo detail rejected","Non-research mesh rejected"]:
    if marker not in api: errors.append(f"missing fail-closed gate: {marker}")
if errors:
    print("FAIL\n"+"\n".join(errors));sys.exit(1)
print("PASS production UI: no generated evidence; research provenance gates present")
