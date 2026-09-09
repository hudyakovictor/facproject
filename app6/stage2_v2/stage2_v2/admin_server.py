"""Stage 2 admin panel - zero-dependency HTTP server.

Why stdlib only
---------------
The existing app6/api backend is FastAPI, but Stage 2 configuration must be
usable on a machine where only the Stage 2 venv exists (and in CI, and in a
sandbox). This server needs nothing but the standard library, so it always
runs. If you want it inside the FastAPI app instead, mount `handle_api` from a
single catch-all route - the API surface is plain JSON in, JSON out.

What it gives you
-----------------
* Every parameter, grouped, with bounds, units, defaults, impact and the
  reasoning behind each default, rendered straight from the registry.
* Named profiles on disk, plus the built-in default / strict_evidence /
  exploratory / fast_smoke presets.
* Server-side validation with the same code path the pipeline uses, so the UI
  can never save a profile the pipeline would reject.
* Diff against defaults or against any other profile, with an explicit warning
  when a change invalidates an existing checkpoint.
* A dry-run endpoint that reports how many Stage 1 records and candidate pairs
  survive the current gates, before committing to a full run.

Usage
-----
    python -m app6.stage2_v2.admin_server --profiles ./stage2_profiles --port 8770
"""
from __future__ import annotations

import argparse
import json
import re
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import contract
from .params import (
    BUILTIN_PROFILES,
    ParamError,
    Params,
    builtin,
    registry_json,
)

SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class ProfileStore:
    """Named parameter profiles persisted as JSON files."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        if not SAFE_NAME.match(name):
            raise ParamError(
                "profile name may only contain letters, digits, dot, dash and "
                "underscore"
            )
        return self.root / f"{name}.json"

    def list_names(self) -> list[str]:
        saved = sorted(p.stem for p in self.root.glob("*.json"))
        return sorted(set(saved) | set(BUILTIN_PROFILES))

    def load(self, name: str) -> Params:
        path = self._path(name)
        if path.exists():
            return Params.load(path)
        return builtin(name)

    def save(self, name: str, values: dict[str, Any], notes: str = "") -> Params:
        params = Params.from_dict(values, name=name, notes=notes)
        params.save(self._path(name))
        return params

    def delete(self, name: str) -> bool:
        path = self._path(name)
        if path.exists():
            path.unlink()
            return True
        return False

    def is_builtin(self, name: str) -> bool:
        return name in BUILTIN_PROFILES and not self._path(name).exists()


def inspect_stage1(root: Path) -> dict[str, Any]:
    """Read-only survey of a Stage 1 output directory.

    Deliberately shallow: it only reads the index and per-photo validation, so
    the admin panel stays responsive on thousands of photos and never needs
    numpy or the reconstruction arrays.
    """
    root = Path(root)
    report: dict[str, Any] = {
        "root": str(root),
        "exists": root.is_dir(),
        "index_present": False,
        "records": 0,
        "complete": 0,
        "incomplete": [],
        "missing_files": [],
        "pose_bins": {},
        "dates": {"dated": 0, "undated": 0, "distinct": 0},
        "problems": [],
    }
    if not report["exists"]:
        report["problems"].append(f"Stage 1 root does not exist: {root}")
        return report

    index = root / contract.MAIN_INDEX
    if not index.exists():
        report["problems"].append(f"missing index {contract.MAIN_INDEX}")
        return report
    report["index_present"] = True

    import csv

    distinct_dates: set[str] = set()
    with index.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    missing_cols = [c for c in contract.MAIN_INDEX_COLUMNS if rows and c not in rows[0]]
    if missing_cols:
        report["problems"].append(f"index missing columns: {missing_cols}")

    for row in rows:
        photo_id = (row.get("photo_id") or "").strip()
        if not photo_id:
            report["problems"].append("index row without photo_id")
            continue
        report["records"] += 1
        pose_bin = (row.get("pose_bin") or "unknown").strip() or "unknown"
        report["pose_bins"][pose_bin] = report["pose_bins"].get(pose_bin, 0) + 1
        date = (row.get("date") or "").strip()
        if date:
            report["dates"]["dated"] += 1
            distinct_dates.add(date)
        else:
            report["dates"]["undated"] += 1

        photo_dir = root / photo_id
        if not photo_dir.is_dir():
            report["missing_files"].append(f"{photo_id}: directory missing")
            continue
        absent = [
            name
            for name in contract.REQUIRED_PHOTO_FILES
            if not (photo_dir / name).exists()
        ]
        if absent:
            report["missing_files"].append(f"{photo_id}: {', '.join(absent)}")
            continue
        try:
            validation = json.loads(
                (photo_dir / "validation.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            report["incomplete"].append(f"{photo_id}: validation.json unreadable ({exc})")
            continue
        status = validation.get("status")
        if status == "complete":
            report["complete"] += 1
        else:
            report["incomplete"].append(f"{photo_id}: status={status!r}")

    report["dates"]["distinct"] = len(distinct_dates)
    # Truncate the long lists so the UI stays readable.
    for key in ("incomplete", "missing_files"):
        if len(report[key]) > 50:
            extra = len(report[key]) - 50
            report[key] = report[key][:50] + [f"... and {extra} more"]
    return report


def dry_run(params: Params, stage1_root: Path) -> dict[str, Any]:
    """Estimate what the current parameters would admit, without measuring.

    This answers the question the admin panel exists for: 'if I tighten the yaw
    gate, how much data do I lose?' It only needs the index and info.json, so
    it runs in seconds.
    """
    survey = inspect_stage1(stage1_root)
    result: dict[str, Any] = {
        "stage1": survey,
        "params_hash": params.hash(),
        "profile": params.name,
        "temporal_axis": {},
        "pairs": {},
        "blocking": [],
    }
    if not survey["index_present"]:
        result["blocking"].append("no Stage 1 index to plan against")
        return result

    dated = survey["dates"]["dated"]
    distinct = survey["dates"]["distinct"]
    axis_ok = (
        dated >= params["min_dated_records"]
        and distinct >= params["min_distinct_dates"]
    )
    result["temporal_axis"] = {
        "usable": axis_ok,
        "dated_records": dated,
        "required_dated": params["min_dated_records"],
        "distinct_dates": distinct,
        "required_distinct": params["min_distinct_dates"],
    }
    if not axis_ok:
        result["blocking"].append(
            "no usable temporal axis: every temporal detector would be skipped"
        )

    per_bin: dict[str, dict[str, Any]] = {}
    total = 0
    for bin_name, count in sorted(survey["pose_bins"].items()):
        adjacent = max(count - 1, 0) if params["pair_adjacent"] else 0
        anchor = max(count - 1, 0) if params["pair_anchor"] else 0
        if params["pair_all_within_bin"]:
            planned = count * (count - 1) // 2
        else:
            planned = adjacent + anchor
        cap = params["max_pairs_per_bin"]
        if cap:
            planned = min(planned, cap)
        limited = bin_name in params["limited_bins"]
        per_bin[bin_name] = {
            "photos": count,
            "planned_pairs": planned,
            "structurally_limited": limited,
            "is_profile": bin_name in contract.PROFILE_BINS,
        }
        total += planned
    result["pairs"] = {
        "per_bin": per_bin,
        "planned_total": total,
        "note": (
            "Upper bound before pose, expression, quality and visibility gates. "
            "Gates need the reconstruction arrays and are applied during the run."
        ),
    }
    if total == 0:
        result["blocking"].append(
            "no pairs would be planned with the current pairing parameters"
        )
    if not params["pair_adjacent"] and not params["pair_anchor"] and not params[
        "pair_all_within_bin"
    ]:
        result["blocking"].append("all pairing strategies are disabled")
    return result


class AdminHandler(BaseHTTPRequestHandler):
    server_version = "Stage2Admin/2.0"
    store: ProfileStore
    stage1_root: Path | None = None
    ui_html: str = ""

    # -- plumbing ----------------------------------------------------------
    def log_message(self, fmt: str, *args: Any) -> None:  # quieter default log
        print(f"[admin] {self.address_string()} {fmt % args}")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ParamError(f"request body is not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ParamError("request body must be a JSON object")
        return payload

    # -- routing -----------------------------------------------------------
    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")

    def _dispatch(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        try:
            self._route(method, path, query)
        except ParamError as exc:
            self._json({"ok": False, "error": str(exc)}, status=400)
        except FileNotFoundError as exc:
            self._json({"ok": False, "error": str(exc)}, status=404)
        except Exception as exc:  # noqa: BLE001 - surface real errors to the UI
            self._json(
                {
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(limit=6),
                },
                status=500,
            )

    def _route(self, method: str, path: str, query: dict[str, list[str]]) -> None:
        if method == "GET" and path in {"/", "/index.html"}:
            self._send(200, self.ui_html.encode("utf-8"), "text/html; charset=utf-8")
            return

        if method == "GET" and path == "/api/registry":
            self._json(registry_json())
            return

        if method == "GET" and path == "/api/profiles":
            self._json(
                {
                    "ok": True,
                    "profiles": [
                        {"name": n, "builtin": self.store.is_builtin(n)}
                        for n in self.store.list_names()
                    ],
                    "stage1_root": str(self.stage1_root) if self.stage1_root else None,
                }
            )
            return

        if path.startswith("/api/profiles/"):
            name = path[len("/api/profiles/") :]
            if method == "GET":
                params = self.store.load(name)
                self._json(
                    {
                        "ok": True,
                        "profile": params.to_json(),
                        "builtin": self.store.is_builtin(name),
                        "non_default": params.non_default(),
                        "diff_vs_default": Params.defaults().diff(params),
                    }
                )
                return
            if method == "POST":
                payload = self._read_json()
                params = self.store.save(
                    name,
                    payload.get("values") or {},
                    notes=payload.get("notes") or "",
                )
                self._json(
                    {
                        "ok": True,
                        "saved": name,
                        "profile": params.to_json(),
                        "diff_vs_default": Params.defaults().diff(params),
                    }
                )
                return
            if method == "DELETE":
                self._json({"ok": True, "deleted": self.store.delete(name)})
                return

        if method == "POST" and path == "/api/validate":
            payload = self._read_json()
            try:
                params = Params.from_dict(
                    payload.get("values") or {},
                    name=payload.get("name") or "draft",
                )
            except ParamError as exc:
                self._json({"ok": False, "valid": False, "errors": str(exc).split("; ")})
                return
            self._json(
                {
                    "ok": True,
                    "valid": True,
                    "hash": params.hash(),
                    "resume_hash": params.resume_hash(),
                    "non_default": params.non_default(),
                    "diff_vs_default": Params.defaults().diff(params),
                    "derived": {
                        "max_pitch_gap_deg": round(params.max_pitch_gap_deg, 4),
                        "max_roll_gap_deg": round(params.max_roll_gap_deg, 4),
                        "quality_inflation": params.quality_inflation_map,
                        "angle_tolerance": params.angle_tolerance_map,
                    },
                }
            )
            return

        if method == "POST" and path == "/api/diff":
            payload = self._read_json()
            left = self.store.load(payload["left"])
            right = (
                Params.from_dict(payload["values"], name="draft")
                if "values" in payload
                else self.store.load(payload["right"])
            )
            changes = left.diff(right)
            self._json(
                {
                    "ok": True,
                    "left": left.name,
                    "right": right.name,
                    "changes": changes,
                    "breaks_resume": any(c["breaks_resume"] for c in changes.values()),
                    "critical": [
                        k for k, c in changes.items() if c["impact"] == "critical"
                    ],
                }
            )
            return

        if method == "GET" and path == "/api/stage1":
            root = query.get("root", [None])[0] or self.stage1_root
            if not root:
                raise ParamError("no Stage 1 root configured or supplied")
            self._json({"ok": True, "survey": inspect_stage1(Path(root))})
            return

        if method == "POST" and path == "/api/dry-run":
            payload = self._read_json()
            params = (
                Params.from_dict(payload["values"], name=payload.get("name") or "draft")
                if "values" in payload
                else self.store.load(payload.get("profile") or "default")
            )
            root = payload.get("stage1_root") or self.stage1_root
            if not root:
                raise ParamError("no Stage 1 root configured or supplied")
            self._json({"ok": True, "dry_run": dry_run(params, Path(root))})
            return

        if method == "GET" and path == "/api/health":
            self._json(
                {
                    "ok": True,
                    "version": "2.0.0",
                    "params_schema": registry_json()["schema"],
                    "profiles_root": str(self.store.root),
                    "stage1_root": str(self.stage1_root) if self.stage1_root else None,
                }
            )
            return

        raise FileNotFoundError(f"no route for {method} {path}")


def build_server(
    profiles_root: Path,
    stage1_root: Path | None,
    host: str,
    port: int,
) -> ThreadingHTTPServer:
    ui_path = Path(__file__).with_name("admin_ui.html")
    handler = type(
        "BoundAdminHandler",
        (AdminHandler,),
        {
            "store": ProfileStore(profiles_root),
            "stage1_root": Path(stage1_root) if stage1_root else None,
            "ui_html": ui_path.read_text(encoding="utf-8")
            if ui_path.exists()
            else "<h1>admin_ui.html is missing</h1>",
        },
    )
    return ThreadingHTTPServer((host, port), handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage 2 admin panel")
    parser.add_argument(
        "--profiles",
        default="./stage2_profiles",
        help="directory holding named parameter profiles",
    )
    parser.add_argument(
        "--stage1",
        default=None,
        help="default Stage 1 output root to survey and dry-run against",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args(argv)

    server = build_server(Path(args.profiles), args.stage1, args.host, args.port)
    print("Stage 2 admin panel listening on " + args.host + ":" + str(args.port))
    print(f"  profiles: {Path(args.profiles).resolve()}")
    print(f"  stage1:   {args.stage1 or '(not set)'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
