#!/usr/bin/env python3
from __future__ import annotations
import subprocess,sys,time,webbrowser
from pathlib import Path
ROOT=Path(__file__).resolve().parent
if not (ROOT/'dist/app.js').is_file(): subprocess.run(['node','build.mjs'],cwd=ROOT,check=True)
p=subprocess.Popen([sys.executable,str(ROOT/'server.py'),'--port','8765'],cwd=ROOT)
try:
 time.sleep(.8); webbrowser.open('http://127.0.0.1:8765'); print('Forensic UI: http://127.0.0.1:8765'); p.wait()
except KeyboardInterrupt: p.terminate()
