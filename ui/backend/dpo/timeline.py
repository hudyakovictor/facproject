"""Best-effort Timeline/Replay reconstruction from observable run events.

Honesty constraint: app6 is read-only observation (project.example.yaml sets
`read_only_observation: true`), so there is no per-function start/end
instrumentation inside a photo's processing -- we must not invent one.

This module reconstructs a *sequential* replay timeline strictly from what
the underlying process actually prints, as captured by runtime.EventLog:

  - unittest verbose ("-v") result lines:  "test_x (module.Class.test_x) ... ok"
  - stage1 per-photo progress lines:       "[3/12] IMG_0001.jpg"

Because RunManager enforces max_parallel_runs=1 and both of the above
processes execute strictly one item after another (no concurrency), the
*end* timestamp of a matched log line is a real observed fact (the ts the
UI received that complete line), while the *start* timestamp of the
reconstructed span is only ever an estimate: "the end of the previous span
on the same track" (or the run's started_at for the first span). Every
span says so explicitly via `start_is_estimated`, and callers/UI must not
present these as measured per-function durations.

Unrecognized log lines are never silently dropped: they are kept as
zero-structure "note" spans on a dedicated `log` track so a human can still
see everything that was printed, without the module claiming structure it
did not actually observe.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_UNITTEST_RESULT_RE = re.compile(
    r"^(?P<name>test_[A-Za-z0-9_]+) \((?P<dotted>[A-Za-z0-9_.]+)\) \.\.\. "
    r"(?P<status>ok|FAIL|ERROR|skipped(?: '.*')?|expected failure|unexpected success)\s*$"
)
_STAGE1_PROGRESS_RE = re.compile(r"^\[(?P<index>\d+)/(?P<total>\d+)\]\s+(?P<name>.+)$")
_STAGE_HINT_RE = re.compile(r"(stage\d[a-z]?)", re.IGNORECASE)

_STATUS_MAP = {
    "ok": "succeeded",
    "FAIL": "failed",
    "ERROR": "failed",
    "expected failure": "succeeded",
    "unexpected success": "failed",
}


def _status_for(raw: str) -> str:
    if raw.startswith("skipped"):
        return "skipped"
    return _STATUS_MAP.get(raw, "unknown")


def _stage_hint(dotted: str) -> str | None:
    m = _STAGE_HINT_RE.search(dotted)
    return m.group(1).lower() if m else None


@dataclass
class TimelineTrack:
    id: str
    title: str
    kind: str  # "run" | "test" | "photo" | "log"

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "title": self.title, "kind": self.kind}


@dataclass
class TimelineSpan:
    seq: int
    track_id: str
    label: str
    status: str
    start_ts: str
    end_ts: str
    start_is_estimated: bool
    module_guess: str | None = None
    stage_guess: str | None = None
    raw_line: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "track_id": self.track_id,
            "label": self.label,
            "status": self.status,
            "start_ts": self.start_ts,
            "end_ts": self.end_ts,
            "start_is_estimated": self.start_is_estimated,
            "module_guess": self.module_guess,
            "stage_guess": self.stage_guess,
            "raw_line": self.raw_line,
        }


_TRACK_DEFS = {
    "run": ("run", "Run lifecycle", "run"),
    "tests": ("tests", "Test cases (sequential)", "test"),
    "photos": ("photos", "Photo progress (sequential)", "photo"),
    "log": ("log", "Unparsed output", "log"),
}


def build_timeline(events: list[dict], run_created_at: str) -> dict[str, Any]:
    """Build a best-effort sequential replay timeline from RunManager events.

    `events` must be shaped like runtime.EventLog.read() entries
    (schema dpo-run-event-v1: seq/ts/type/payload).
    """
    tracks: dict[str, TimelineTrack] = {}
    spans: list[TimelineSpan] = []
    cursor_ts: dict[str, str] = {}
    run_started_at = run_created_at

    def track(track_id: str) -> None:
        if track_id not in tracks:
            tid, title, kind = _TRACK_DEFS[track_id]
            tracks[track_id] = TimelineTrack(tid, title, kind)

    def cursor_for(track_id: str) -> str:
        return cursor_ts.get(track_id, run_started_at)

    for e in events:
        etype = e.get("type")
        payload = e.get("payload") or {}
        ts = str(e.get("ts"))
        seq = int(e.get("seq", 0))

        if etype == "started":
            run_started_at = ts
            track("run")
            spans.append(TimelineSpan(seq, "run", "run started", "succeeded", ts, ts, False, raw_line="started"))
            cursor_ts["tests"] = ts
            cursor_ts["photos"] = ts
            continue
        if etype == "finished":
            track("run")
            status = str(payload.get("status", "unknown"))
            spans.append(TimelineSpan(seq, "run", f"run {status}", status, ts, ts, False, raw_line="finished"))
            continue
        if etype != "log":
            continue

        text = str(payload.get("text", ""))
        stripped = text.strip()

        m = _UNITTEST_RESULT_RE.match(stripped)
        if m:
            track("tests")
            start = cursor_for("tests")
            status = _status_for(m.group("status"))
            spans.append(TimelineSpan(
                seq, "tests", m.group("name"), status, start, ts,
                start_is_estimated=True, module_guess=m.group("dotted"),
                stage_guess=_stage_hint(m.group("dotted")), raw_line=text,
            ))
            cursor_ts["tests"] = ts
            continue

        m = _STAGE1_PROGRESS_RE.match(stripped)
        if m:
            track("photos")
            start = cursor_for("photos")
            spans.append(TimelineSpan(
                seq, "photos", m.group("name"), "succeeded", start, ts,
                start_is_estimated=True, stage_guess="stage1", raw_line=text,
            ))
            cursor_ts["photos"] = ts
            continue

        track("log")
        start = cursor_for("log")
        spans.append(TimelineSpan(seq, "log", text[:120], "unknown", start, ts, True, raw_line=text))
        cursor_ts["log"] = ts

    return {
        "tracks": [tracks[k].to_dict() for k in tracks],
        "spans": [s.to_dict() for s in spans],
    }


def timeline_state_at(timeline: dict[str, Any], at_seq: int) -> dict[str, Any]:
    """Split spans into completed/active/pending relative to a scrubber
    position expressed as an event `seq` number (inclusive of completed).

    All reconstructed spans here represent already-completed log lines, so
    "active" is always empty for this reconstruction -- reported as such
    honestly rather than guessed from elapsed-time heuristics.
    """
    completed: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    for s in timeline.get("spans", []):
        (completed if s["seq"] <= at_seq else pending).append(s)
    return {"completed": completed, "active": [], "pending": pending, "at_seq": at_seq}
