#!/usr/bin/env python3
"""Fetch and verify the pinned official MediaPipe Face Landmarker task (Apache-2.0)."""
import hashlib,json,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
URL='https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task'
SHA256='64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff'
target=ROOT/'.cache/models/mediapipe/face_landmarker.task'
target.parent.mkdir(parents=True,exist_ok=True)
if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==SHA256:print('MediaPipe task SHA-256 OK');raise SystemExit(0)
tmp=target.with_suffix('.download')
with urllib.request.urlopen(URL,timeout=60) as response,tmp.open('wb') as output:
 while chunk:=response.read(1<<20):output.write(chunk)
actual=hashlib.sha256(tmp.read_bytes()).hexdigest()
if actual!=SHA256:tmp.unlink(missing_ok=True);raise SystemExit(f'Hash mismatch: {actual}')
tmp.replace(target)
(ROOT/'reports/mediapipe-asset.json').write_text(json.dumps({'url':URL,'sha256':SHA256,'bytes':target.stat().st_size,'license':'Apache-2.0','version':'0.10.35'},indent=2))
print('Official MediaPipe task restored and hash verified')
