"""Dependency-light CLI for setup and health checks."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .health import collect_health
from .settings import ProjectSettings, SettingsError
from .storage import StorageManager, StorageUnavailable


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dpo")
    p.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[2] / "config" / "project.example.yaml")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("health")
    init = sub.add_parser("init-storage")
    init.add_argument("--volume-id", required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        settings = ProjectSettings.load(args.config)
        if args.command == "health":
            print(json.dumps(collect_health(settings).to_dict(), ensure_ascii=False, indent=2))
            return 0
        if args.command == "init-storage":
            manager = StorageManager(settings.storage, protected_roots=(settings.app6_root, settings.datasets.main_root))
            print(json.dumps(manager.initialize(args.volume_id).to_dict(), ensure_ascii=False, indent=2))
            return 0
    except (SettingsError, StorageUnavailable, OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
