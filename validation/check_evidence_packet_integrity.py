#!/usr/bin/env python3
"""Executable scaffold for check_evidence_packet_integrity.py; contract-specific checks follow baseline discovery."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

SCRIPT_NAME = 'check_evidence_packet_integrity.py'
ARG_NAMES = ['stage2_root']


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validation scaffold: " + SCRIPT_NAME)
    p.add_argument("stage2_root", type=Path, help='Path to Stage 2 output')
    p.add_argument("--sample-limit", type=int, default=20)
    return p.parse_args()


def inspect_input(path: Path, reporter: list[tuple[str, str, str]]) -> None:
    if not path.exists():
        reporter.append(("ERROR", "INPUT_MISSING", str(path)))
        return
    if path.is_file() and path.stat().st_size == 0:
        reporter.append(("ERROR", "INPUT_EMPTY", str(path)))
        return
    if path.is_dir():
        files = [p for p in path.rglob("*") if p.is_file() and p.name != ".DS_Store" and not p.name.startswith("._")]
        if not files:
            reporter.append(("WARN", "INPUT_NO_USABLE_FILES", str(path)))


def main() -> int:
    args = parse_args()
    events: list[tuple[str, str, str]] = []
    for name in ARG_NAMES:
        inspect_input(Path(getattr(args, name)).resolve(), events)
    if not any(level == "ERROR" for level, _, _ in events):
        events.append(("WARN", "SCAFFOLD_ONLY", SCRIPT_NAME))
    shown = 0
    for level, code, subject in events:
        if shown >= args.sample_limit:
            break
        print(f"{level} code={code} subject={subject} detail=baseline scaffold check")
        shown += 1
    errors = sum(level == "ERROR" for level, _, _ in events)
    warnings = sum(level == "WARN" for level, _, _ in events)
    status = "BLOCKED" if errors else "PASS"
    print(f"SUMMARY script={SCRIPT_NAME} status={status} checked_inputs={len(ARG_NAMES)} errors={errors} warnings={warnings}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
