"""Robust per-vertex reconstruction noise baseline from repeated views per subject."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from server.config import ROOT


def calculate_noise(participants: list[dict], load_mesh, *, min_people: int = 7) -> dict:
    if not isinstance(participants, list) or len(participants) < min_people:
        raise ValueError(f"Нужно не менее {min_people} участников")
    if any(not isinstance(p, dict) for p in participants):
        raise ValueError("Участники должны быть объектами с label и photo_ids")
    ids_seen: set[str] = set()
    labels_seen: set[str] = set()
    per_person = []
    n_vertices = None
    used = []
    for person in participants:
        label = str(person.get("label", "")).strip()
        photo_ids = list(dict.fromkeys(map(str, person.get("photo_ids", []))))
        if not label or label in labels_seen or not 2 <= len(photo_ids) <= 3:
            raise ValueError("Для каждого участника задайте уникальное имя и 2–3 фото")
        labels_seen.add(label)
        if ids_seen.intersection(photo_ids):
            raise ValueError("Одно фото нельзя использовать для нескольких участников")
        ids_seen.update(photo_ids)
        meshes = [np.asarray(load_mesh(pid), np.float32).reshape(-1, 3) for pid in photo_ids]
        if any(m.shape != meshes[0].shape for m in meshes):
            raise ValueError("Разный размер меша в calibration sample")
        n_vertices = meshes[0].shape[0]
        # Per-person centering removes true between-person shape; pooled residual
        # magnitude estimates repeatability/noise, not a population face template.
        stack = np.stack(meshes)
        center = np.median(stack, axis=0)
        residual = np.linalg.norm(stack - center[None, :, :], axis=2)
        per_person.append(np.median(residual, axis=0))
        used.append({"label": label, "photo_ids": photo_ids})
    noise = np.percentile(np.stack(per_person), 75, axis=0).astype(np.float32)
    payload = {"version": 1, "method": "per-person median-centered vertex displacement; 75th percentile across participants",
               "participants": used, "participant_count": len(used), "photo_count": len(ids_seen),
               "vertex_count": int(n_vertices), "units": "template_IOD", "threshold": noise.round(7).tolist()}
    path = ROOT / "cache" / "calibration" / "noise-v1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False))
    tmp.replace(path)
    return payload


def load_noise() -> dict | None:
    path = ROOT / "cache" / "calibration" / "noise-v1.json"
    return json.loads(path.read_text()) if path.exists() else None
