import sys
from pathlib import Path

APP10 = Path(__file__).resolve().parents[1]
if str(APP10) not in sys.path:
    sys.path.insert(0, str(APP10))
