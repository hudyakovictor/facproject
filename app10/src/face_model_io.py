"""Загрузка топологии и разметки из face_model.npy (3DDFA_V3). Топология одна для всех кадров."""
from pathlib import Path

import numpy as np

ANNOTATION_NAMES = ["right_eye", "left_eye", "right_eyebrow", "left_eyebrow", "nose", "up_lip", "down_lip", "skin"]


def load_face_model(path):
    """Возвращает dict с ключами tri (F,3 int64), annotation (список из 8 массивов), ldm106, ldm134
    и mean_shape (N,3, средняя форма BFM из ключа `u`), если они есть в файле."""
    obj = np.load(Path(path), allow_pickle=True)
    if getattr(obj, "shape", None) == ():
        obj = obj.item()
    if not hasattr(obj, "keys"):
        raise ValueError("face_model.npy: ожидался словарь с ключами tri/annotation/ldm106/ldm134")
    out = {}
    if "tri" not in obj:
        raise ValueError("в face_model.npy нет ключа 'tri'")
    out["tri"] = np.asarray(obj["tri"], dtype=np.int64)
    if out["tri"].ndim != 2 or out["tri"].shape[1] != 3:
        raise ValueError(f"tri имеет форму {out['tri'].shape}, ожидалось (F,3)")
    if "annotation" in obj:
        ann = [np.asarray(a, dtype=np.int64).ravel() for a in obj["annotation"]]
        if len(ann) != len(ANNOTATION_NAMES):
            raise ValueError(f"annotation: {len(ann)} групп, ожидалось {len(ANNOTATION_NAMES)}")
        out["annotation"] = ann
    for key in ("ldm106", "ldm134"):
        if key in obj:
            out[key] = np.asarray(obj[key], dtype=np.int64).ravel()
    if "u" in obj:
        u = np.asarray(obj["u"], dtype=np.float64).ravel()
        if u.size % 3 != 0:
            raise ValueError(f"u (средняя форма): размер {u.size} не делится на 3")
        out["mean_shape"] = u.reshape(-1, 3)
    return out
