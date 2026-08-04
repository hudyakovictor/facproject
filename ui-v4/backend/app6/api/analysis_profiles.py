"""Analysis Profiles + manual curation journal (Iteration 04).

Profiles live under ``storage/profiles/<profile_id>/`` and never mutate Stage 1.
Each photo gets an unambiguous curation status; every manual override is journaled.
"""
from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .runtime_config import RuntimePaths, ensure_runtime_write_dirs, load_runtime_paths
from .selection_filters import (
    DEFAULT_FILTER_STATE,
    build_selection_manifest,
    evaluate_selection,
)

PROFILE_SCHEMA = "deeputin-analysis-profile-v1.0"
CURATION_SCHEMA = "deeputin-curation-v1.0"
JOURNAL_SCHEMA = "deeputin-curation-journal-v1.0"

PHOTO_STATUSES = (
    "primary",
    "diagnostic_only",
    "automatic_exclusion",
    "manual_exclusion",
    "manual_include",
    "manual_review",
    "invalid",
)

REASON_CODES = (
    "quality_gate",
    "pose_outlier",
    "expression",
    "date_conflict",
    "near_duplicate",
    "missing_artifact",
    "manual_reviewer",
    "restored_automatic",
    "bulk_action",
    "other",
)


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _profiles_root(paths: RuntimePaths | None = None) -> Path:
    current = paths or load_runtime_paths()
    ensure_runtime_write_dirs(current)
    root = current.storage_root / "profiles"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", text.strip().lower()).strip("_")
    return cleaned[:48] or "profile"


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _empty_curation() -> dict[str, Any]:
    return {
        "schema": CURATION_SCHEMA,
        "not_a_verdict": True,
        "photos": {},  # photo_id -> {status, reason_code, comment, updated_at, source}
        "updated_at": _utc(),
    }


def _empty_journal() -> dict[str, Any]:
    return {"schema": JOURNAL_SCHEMA, "not_a_verdict": True, "entries": []}


def _profile_dir(profile_id: str, paths: RuntimePaths | None = None) -> Path:
    return _profiles_root(paths) / profile_id


def _profile_paths(profile_id: str, paths: RuntimePaths | None = None) -> dict[str, Path]:
    root = _profile_dir(profile_id, paths)
    return {
        "root": root,
        "config": root / "analysis_config.json",
        "curation": root / "curation.json",
        "journal": root / "journal.jsonl",
        "manifest": root / "selection_manifest.json",
        "lock": root / "LOCKED",
    }


def _is_locked(profile_id: str, paths: RuntimePaths | None = None) -> bool:
    return _profile_paths(profile_id, paths)["lock"].is_file()


def _require_unlocked(profile_id: str, paths: RuntimePaths | None = None) -> None:
    if _is_locked(profile_id, paths):
        raise PermissionError(f"profile is locked: {profile_id}")


def _append_journal(profile_id: str, entry: dict[str, Any], paths: RuntimePaths | None = None) -> None:
    journal_path = _profile_paths(profile_id, paths)["journal"]
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema": JOURNAL_SCHEMA, "ts": _utc(), **entry}
    with journal_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def list_profiles(paths: RuntimePaths | None = None) -> dict[str, Any]:
    root = _profiles_root(paths)
    profiles: list[dict[str, Any]] = []
    for child in sorted(root.iterdir() if root.is_dir() else [], key=lambda item: item.name):
        if not child.is_dir() or child.name in {"current"}:
            continue
        config = _read_json(child / "analysis_config.json")
        if not config:
            continue
        curation = _read_json(child / "curation.json") or _empty_curation()
        profiles.append(
            {
                "id": child.name,
                "name": config.get("name") or child.name,
                "description": config.get("description") or "",
                "locked": (child / "LOCKED").is_file(),
                "created_at": config.get("created_at"),
                "updated_at": config.get("updated_at"),
                "photo_status_counts": _status_counts(curation),
                "has_manifest": (child / "selection_manifest.json").is_file(),
            }
        )
    return {"schema": PROFILE_SCHEMA, "not_a_verdict": True, "profiles": profiles, "count": len(profiles)}


def _status_counts(curation: dict[str, Any]) -> dict[str, int]:
    counts = {status: 0 for status in PHOTO_STATUSES}
    for item in (curation.get("photos") or {}).values():
        status = str((item or {}).get("status") or "")
        if status in counts:
            counts[status] += 1
    return counts


def get_profile(profile_id: str, paths: RuntimePaths | None = None) -> dict[str, Any]:
    files = _profile_paths(profile_id, paths)
    config = _read_json(files["config"])
    if not config:
        raise FileNotFoundError(f"profile not found: {profile_id}")
    curation = _read_json(files["curation"]) or _empty_curation()
    manifest = _read_json(files["manifest"])
    journal_entries = _read_journal_entries(profile_id, paths, limit=200)
    return {
        "schema": PROFILE_SCHEMA,
        "not_a_verdict": True,
        "id": profile_id,
        "locked": files["lock"].is_file(),
        "config": config,
        "curation": curation,
        "selection_manifest": manifest,
        "journal_tail": journal_entries,
        "photo_status_counts": _status_counts(curation),
        "paths": {key: str(value) for key, value in files.items()},
    }


def _read_journal_entries(profile_id: str, paths: RuntimePaths | None = None, limit: int = 200) -> list[dict[str, Any]]:
    path = _profile_paths(profile_id, paths)["journal"]
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    entries: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            entries.append(value)
    return entries


def create_profile(
    *,
    name: str,
    description: str = "",
    filter_state: dict[str, Any] | None = None,
    paths: RuntimePaths | None = None,
    profile_id: str | None = None,
) -> dict[str, Any]:
    current = paths or load_runtime_paths()
    pid = profile_id or f"profile_{_slug(name)}_{uuid.uuid4().hex[:8]}"
    files = _profile_paths(pid, current)
    if files["root"].exists():
        raise FileExistsError(f"profile already exists: {pid}")
    files["root"].mkdir(parents=True, exist_ok=False)
    now = _utc()
    config = {
        "schema": PROFILE_SCHEMA,
        "not_a_verdict": True,
        "id": pid,
        "name": name.strip() or pid,
        "description": description,
        "created_at": now,
        "updated_at": now,
        "filter_state": filter_state or json.loads(json.dumps(DEFAULT_FILTER_STATE)),
        "analysis_config": {
            "stage2_ready": False,
            "notes": "Selection profile for reproducible Stage 2 runs",
        },
    }
    curation = _empty_curation()
    _atomic_json(files["config"], config)
    _atomic_json(files["curation"], curation)
    files["journal"].write_text("", encoding="utf-8")
    _append_journal(pid, {"action": "create_profile", "name": config["name"]}, current)
    return get_profile(pid, current)


def clone_profile(source_id: str, *, new_name: str | None = None, paths: RuntimePaths | None = None) -> dict[str, Any]:
    source = get_profile(source_id, paths)
    name = new_name or f"{source['config'].get('name', source_id)} copy"
    cloned = create_profile(
        name=name,
        description=str(source["config"].get("description") or ""),
        filter_state=source["config"].get("filter_state"),
        paths=paths,
    )
    # copy curation + optional unlocked manifest snapshot as draft
    src_files = _profile_paths(source_id, paths)
    dst_files = _profile_paths(cloned["id"], paths)
    if src_files["curation"].is_file():
        shutil.copy2(src_files["curation"], dst_files["curation"])
    if src_files["manifest"].is_file():
        shutil.copy2(src_files["manifest"], dst_files["manifest"])
    _append_journal(cloned["id"], {"action": "clone_profile", "source_id": source_id}, paths)
    return get_profile(cloned["id"], paths)


def rename_profile(profile_id: str, *, name: str, description: str | None = None, paths: RuntimePaths | None = None) -> dict[str, Any]:
    _require_unlocked(profile_id, paths)
    files = _profile_paths(profile_id, paths)
    config = _read_json(files["config"])
    if not config:
        raise FileNotFoundError(profile_id)
    old_name = config.get("name")
    config["name"] = name.strip() or old_name
    if description is not None:
        config["description"] = description
    config["updated_at"] = _utc()
    _atomic_json(files["config"], config)
    _append_journal(profile_id, {"action": "rename_profile", "old_name": old_name, "new_name": config["name"]}, paths)
    return get_profile(profile_id, paths)


def set_profile_lock(profile_id: str, locked: bool, paths: RuntimePaths | None = None) -> dict[str, Any]:
    files = _profile_paths(profile_id, paths)
    if not files["config"].is_file():
        raise FileNotFoundError(profile_id)
    if locked:
        files["lock"].write_text(_utc() + "\n", encoding="utf-8")
        action = "lock_profile"
    else:
        if files["lock"].is_file():
            files["lock"].unlink()
        action = "unlock_profile"
    _append_journal(profile_id, {"action": action}, paths)
    return get_profile(profile_id, paths)


def update_profile_filters(profile_id: str, filter_state: dict[str, Any], paths: RuntimePaths | None = None) -> dict[str, Any]:
    _require_unlocked(profile_id, paths)
    files = _profile_paths(profile_id, paths)
    config = _read_json(files["config"])
    if not config:
        raise FileNotFoundError(profile_id)
    config["filter_state"] = filter_state
    config["updated_at"] = _utc()
    _atomic_json(files["config"], config)
    _append_journal(profile_id, {"action": "update_filters"}, paths)
    return get_profile(profile_id, paths)


def _normalize_status(status: str) -> str:
    value = status.strip().lower().replace("-", "_")
    aliases = {
        "auto_exclusion": "automatic_exclusion",
        "automatic": "automatic_exclusion",
        "manual_exclude": "manual_exclusion",
        "exclude": "manual_exclusion",
        "include": "manual_include",
        "review": "manual_review",
        "diagnostic": "diagnostic_only",
    }
    value = aliases.get(value, value)
    if value not in PHOTO_STATUSES:
        raise ValueError(f"unsupported status: {status}; allowed={PHOTO_STATUSES}")
    return value


def apply_curation(
    profile_id: str,
    *,
    photo_ids: list[str],
    status: str,
    reason_code: str = "manual_reviewer",
    comment: str = "",
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    """Set curation status for one or many photos; journal every override."""
    _require_unlocked(profile_id, paths)
    if not photo_ids:
        raise ValueError("photo_ids required")
    normalized = _normalize_status(status)
    reason = reason_code if reason_code in REASON_CODES else "other"
    files = _profile_paths(profile_id, paths)
    curation = _read_json(files["curation"]) or _empty_curation()
    photos = dict(curation.get("photos") or {})
    now = _utc()
    changed: list[str] = []
    for photo_id in photo_ids:
        pid = str(photo_id).strip()
        if not pid:
            continue
        previous = dict(photos.get(pid) or {})
        entry = {
            "status": normalized,
            "reason_code": reason,
            "comment": comment or "",
            "updated_at": now,
            "source": "manual",
            "previous_status": previous.get("status"),
        }
        photos[pid] = entry
        changed.append(pid)
        _append_journal(
            profile_id,
            {
                "action": "set_status",
                "photo_id": pid,
                "status": normalized,
                "reason_code": reason,
                "comment": comment or "",
                "previous_status": previous.get("status"),
            },
            paths,
        )
    curation["photos"] = photos
    curation["updated_at"] = now
    _atomic_json(files["curation"], curation)
    config = _read_json(files["config"]) or {}
    config["updated_at"] = now
    _atomic_json(files["config"], config)
    return {
        "schema": CURATION_SCHEMA,
        "not_a_verdict": True,
        "profile_id": profile_id,
        "changed_count": len(changed),
        "changed_ids": changed,
        "photo_status_counts": _status_counts(curation),
        "curation": curation,
    }


def restore_automatic(
    profile_id: str,
    *,
    photo_ids: list[str],
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    """Remove manual override so automatic filter decision applies again."""
    _require_unlocked(profile_id, paths)
    files = _profile_paths(profile_id, paths)
    curation = _read_json(files["curation"]) or _empty_curation()
    photos = dict(curation.get("photos") or {})
    restored: list[str] = []
    for photo_id in photo_ids:
        pid = str(photo_id).strip()
        if pid in photos:
            previous = photos.pop(pid)
            restored.append(pid)
            _append_journal(
                profile_id,
                {
                    "action": "restore_automatic",
                    "photo_id": pid,
                    "previous_status": (previous or {}).get("status"),
                    "reason_code": "restored_automatic",
                },
                paths,
            )
    curation["photos"] = photos
    curation["updated_at"] = _utc()
    _atomic_json(files["curation"], curation)
    return {
        "schema": CURATION_SCHEMA,
        "not_a_verdict": True,
        "profile_id": profile_id,
        "restored_count": len(restored),
        "restored_ids": restored,
        "photo_status_counts": _status_counts(curation),
        "curation": curation,
    }


def _merge_curation_into_filter_state(filter_state: dict[str, Any], curation: dict[str, Any]) -> dict[str, Any]:
    state = json.loads(json.dumps(filter_state or DEFAULT_FILTER_STATE))
    manual_exclude: list[str] = []
    manual_include: list[str] = []
    for photo_id, item in (curation.get("photos") or {}).items():
        status = str((item or {}).get("status") or "")
        if status in {"manual_exclusion", "invalid"}:
            manual_exclude.append(photo_id)
        elif status in {"manual_include", "primary", "diagnostic_only"}:
            # primary/diagnostic still included; manual_include forces include over auto exclude
            if status == "manual_include":
                manual_include.append(photo_id)
        elif status == "manual_review":
            # review stays visible but marked; treat as include for Stage2 planning unless later gated
            manual_include.append(photo_id)
    # Preserve any existing filter manual lists then extend uniquely
    state["manualExclude"] = sorted(set(list(state.get("manualExclude") or []) + manual_exclude))
    state["manualInclude"] = sorted(set(list(state.get("manualInclude") or []) + manual_include))
    return state


def build_profile_photo_statuses(
    photos: list[dict[str, Any]],
    *,
    filter_state: dict[str, Any] | None,
    curation: dict[str, Any] | None,
) -> dict[str, Any]:
    """Resolve final status for every photo: curation overrides automatic filters."""
    evaluation = evaluate_selection(photos, filter_state)
    auto_excluded = set(evaluation.get("excluded_ids") or [])
    curation_photos = (curation or {}).get("photos") or {}
    resolved: dict[str, dict[str, Any]] = {}
    for photo in photos:
        photo_id = str(photo.get("id") or "")
        if not photo_id:
            continue
        manual = curation_photos.get(photo_id)
        if isinstance(manual, dict) and manual.get("status") in PHOTO_STATUSES:
            status = str(manual["status"])
            source = "manual"
            reasons = [str(manual.get("reason_code") or "manual_reviewer")]
            comment = str(manual.get("comment") or "")
        elif photo_id in auto_excluded:
            status = "automatic_exclusion"
            source = "automatic"
            decision = next((d for d in evaluation.get("decisions") or [] if d.get("photo_id") == photo_id), {})
            reasons = list(decision.get("reasons") or ["automatic_filter"])
            comment = ""
        else:
            status = "primary"
            source = "automatic"
            reasons = []
            comment = ""
        resolved[photo_id] = {
            "photo_id": photo_id,
            "status": status,
            "source": source,
            "reasons": reasons,
            "comment": comment,
            "included": status in {"primary", "diagnostic_only", "manual_include", "manual_review"},
        }
    # Ensure curation-only ids still appear
    for photo_id, manual in curation_photos.items():
        if photo_id not in resolved and isinstance(manual, dict):
            status = str(manual.get("status") or "manual_review")
            resolved[photo_id] = {
                "photo_id": photo_id,
                "status": status,
                "source": "manual",
                "reasons": [str(manual.get("reason_code") or "manual_reviewer")],
                "comment": str(manual.get("comment") or ""),
                "included": status in {"primary", "diagnostic_only", "manual_include", "manual_review"},
            }
    included_ids = sorted(pid for pid, item in resolved.items() if item["included"])
    excluded_ids = sorted(pid for pid, item in resolved.items() if not item["included"])
    counts = {status: 0 for status in PHOTO_STATUSES}
    for item in resolved.values():
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return {
        "schema": CURATION_SCHEMA,
        "not_a_verdict": True,
        "photos": resolved,
        "included_ids": included_ids,
        "excluded_ids": excluded_ids,
        "included_count": len(included_ids),
        "excluded_count": len(excluded_ids),
        "status_counts": counts,
        "filter_evaluation": {
            "included_count": evaluation.get("included_count"),
            "excluded_count": evaluation.get("excluded_count"),
            "reason_counts": evaluation.get("reason_counts"),
        },
    }


def freeze_selection_manifest(
    profile_id: str,
    photos: list[dict[str, Any]],
    *,
    paths: RuntimePaths | None = None,
    stage1_root: str | None = None,
) -> dict[str, Any]:
    """Build immutable selection_manifest.json for the profile."""
    _require_unlocked(profile_id, paths)
    files = _profile_paths(profile_id, paths)
    config = _read_json(files["config"])
    if not config:
        raise FileNotFoundError(profile_id)
    curation = _read_json(files["curation"]) or _empty_curation()
    filter_state = _merge_curation_into_filter_state(config.get("filter_state") or DEFAULT_FILTER_STATE, curation)
    resolved = build_profile_photo_statuses(photos, filter_state=filter_state, curation=curation)
    # Use evaluate_selection with merged manual lists for deterministic filter reasons,
    # then overlay final included set from resolved statuses.
    evaluation = evaluate_selection(photos, filter_state)
    manifest = {
        "schema": "deeputin-selection-manifest-v1.1",
        "not_a_verdict": True,
        "profile_id": profile_id,
        "profile_name": config.get("name"),
        "label": config.get("name") or profile_id,
        "stage1_root": stage1_root,
        "filter_state": filter_state,
        "curation_snapshot": curation,
        "included_ids": resolved["included_ids"],
        "excluded_ids": resolved["excluded_ids"],
        "included_count": resolved["included_count"],
        "excluded_count": resolved["excluded_count"],
        "status_counts": resolved["status_counts"],
        "photo_statuses": resolved["photos"],
        "filter_reason_counts": evaluation.get("reason_counts") or {},
        "immutable_stage1": True,
        "frozen_at": _utc(),
        "locked_after_freeze": False,
    }
    _atomic_json(files["manifest"], manifest)
    config["updated_at"] = _utc()
    config["last_manifest_at"] = manifest["frozen_at"]
    _atomic_json(files["config"], config)
    _append_journal(
        profile_id,
        {
            "action": "freeze_selection_manifest",
            "included_count": manifest["included_count"],
            "excluded_count": manifest["excluded_count"],
        },
        paths,
    )
    return {"schema": PROFILE_SCHEMA, "not_a_verdict": True, "path": str(files["manifest"]), "manifest": manifest}


def diff_profiles(profile_a: str, profile_b: str, paths: RuntimePaths | None = None) -> dict[str, Any]:
    a = get_profile(profile_a, paths)
    b = get_profile(profile_b, paths)
    a_cur = (a.get("curation") or {}).get("photos") or {}
    b_cur = (b.get("curation") or {}).get("photos") or {}
    keys = sorted(set(a_cur) | set(b_cur))
    status_changes = []
    for key in keys:
        sa = (a_cur.get(key) or {}).get("status")
        sb = (b_cur.get(key) or {}).get("status")
        if sa != sb:
            status_changes.append({"photo_id": key, "a": sa, "b": sb})
    a_filter = json.dumps((a.get("config") or {}).get("filter_state") or {}, sort_keys=True)
    b_filter = json.dumps((b.get("config") or {}).get("filter_state") or {}, sort_keys=True)
    return {
        "schema": PROFILE_SCHEMA,
        "not_a_verdict": True,
        "a": profile_a,
        "b": profile_b,
        "filter_state_equal": a_filter == b_filter,
        "status_change_count": len(status_changes),
        "status_changes": status_changes[:500],
        "a_counts": a.get("photo_status_counts"),
        "b_counts": b.get("photo_status_counts"),
    }


def export_profile(profile_id: str, paths: RuntimePaths | None = None) -> dict[str, Any]:
    profile = get_profile(profile_id, paths)
    return {
        "schema": "deeputin-analysis-profile-export-v1.0",
        "not_a_verdict": True,
        "exported_at": _utc(),
        "profile": {
            "id": profile["id"],
            "config": profile["config"],
            "curation": profile["curation"],
            "selection_manifest": profile.get("selection_manifest"),
        },
    }


def import_profile(payload: dict[str, Any], paths: RuntimePaths | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("payload must be object")
    body = payload.get("profile") if isinstance(payload.get("profile"), dict) else payload
    config = body.get("config") if isinstance(body.get("config"), dict) else {}
    name = str(config.get("name") or body.get("name") or "imported")
    created = create_profile(
        name=name,
        description=str(config.get("description") or ""),
        filter_state=config.get("filter_state"),
        paths=paths,
    )
    pid = created["id"]
    files = _profile_paths(pid, paths)
    curation = body.get("curation") if isinstance(body.get("curation"), dict) else _empty_curation()
    _atomic_json(files["curation"], curation)
    manifest = body.get("selection_manifest")
    if isinstance(manifest, dict):
        _atomic_json(files["manifest"], manifest)
    _append_journal(pid, {"action": "import_profile", "source_name": name}, paths)
    return get_profile(pid, paths)
