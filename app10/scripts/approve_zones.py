#!/usr/bin/env python3
"""Утвердить зоны вручную: записать validated=true вместе с zones_sha256 содержимого зон.

Если после этого границы зон поменять, канонический хеш перестанет совпадать со stored —
утверждение считается недействительным (его проверяет geometry_calibrate.py). Снять — --revoke.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.zones import zones_sha256  # noqa: E402


def main():
    p = argparse.ArgumentParser(description="Ручное утверждение зон (validated по хешу)")
    p.add_argument("--zones", required=True)
    p.add_argument("--revoke", action="store_true", help="снять утверждение (validated=false)")
    args = p.parse_args()

    path = Path(args.zones)
    d = json.loads(path.read_text())
    sha = zones_sha256(d["zones"])
    d["validated"] = not args.revoke
    d["zones_sha256"] = sha
    path.write_text(json.dumps(d, ensure_ascii=False))
    print(("ОТЗВАНО" if args.revoke else "УТВЕРЖДЕНО"), args.zones, "zones_sha256", sha[:16])


if __name__ == "__main__":
    main()
