"""📖 API быстрого чтения и доступа к данным Stage 1 (app8).

Предоставляет мгновенный доступ к 134/106 точкам, полной сетке и костным структурам
напрямую из `reconstruction.npz` без чтения устаревших CSV.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
import numpy as np

from .visibility import unpack_mask


@dataclass
class App8Record:
    photo_id: str
    date_iso: str
    pose_bin: str
    canonical_yaw: float
    angles_deg: np.ndarray             # (3,) pitch, yaw, roll
    alpha_id: np.ndarray               # (80,)
    alpha_exp: np.ndarray              # (64,)
    vertices_object: np.ndarray        # (35709, 3)
    vertices_identity_only: np.ndarray # (35709, 3)
    vertices_chronology: np.ndarray    # (35709, 3)
    normals_object: np.ndarray         # (35709, 3)
    vertex_confidence: np.ndarray      # (35709,)
    visible_mask: np.ndarray           # (35709,) bool
    ldm134_indices: np.ndarray         # (134,)
    ldm106_indices: np.ndarray         # (106,)
    uv_coords: np.ndarray              # (35709, 2)
    triangles: np.ndarray              # (70789, 3)
    rotation_matrix: np.ndarray        # (3, 3)
    translation: np.ndarray            # (3,)
    chronology_corr_matrix: np.ndarray # (3, 3)


def load_record(path_or_dir: str | Path) -> App8Record:
    """Загружает запись реконструкции из каталога кадра или напрямую из npz."""
    p = Path(path_or_dir)
    if p.is_dir():
        npz_file = p / "reconstruction.npz"
    else:
        npz_file = p
        
    if not npz_file.is_file():
        raise FileNotFoundError(f"reconstruction.npz not found at {npz_file}")
        
    with np.load(npz_file, allow_pickle=False) as data:
        n_vert = int(data["vertices_object"].shape[0])
        vis = unpack_mask(data["full_mesh_visible_packbits"], n_vert)
        
        return App8Record(
            photo_id=str(data["photo_id"]),
            date_iso=str(data["date_iso"]),
            pose_bin=str(data["pose_bin"]),
            canonical_yaw=float(data["canonical_yaw"][0]),
            angles_deg=data["angle_deg_pitch_yaw_roll"],
            alpha_id=data["alpha_id"],
            alpha_exp=data["alpha_exp"],
            vertices_object=data["vertices_object"],
            vertices_identity_only=data["vertices_identity_only"],
            vertices_chronology=data["vertices_chronology_aligned"],
            normals_object=data["normals_object"],
            vertex_confidence=data["vertex_confidence"],
            visible_mask=vis,
            ldm134_indices=data["ldm134_vertex_indices"],
            ldm106_indices=data["ldm106_vertex_indices"],
            uv_coords=data["uv_coords"],
            triangles=data["triangles"],
            rotation_matrix=data["rotation_matrix"],
            translation=data["translation"],
            chronology_corr_matrix=data["chronology_correction_matrix"],
        )


@dataclass
class App8PackedBin:
    bin_name: str
    canonical_yaw: float
    photo_ids: list[str]
    dates_iso: list[str]
    angles_deg: np.ndarray             # (N, 3)
    alpha_id: np.ndarray               # (N, 80)
    alpha_exp: np.ndarray              # (N, 64)
    ldm106_chronology: np.ndarray      # (N, 106, 3)
    ldm134_chronology: np.ndarray      # (N, 134, 3)
    ldm106_confidence: np.ndarray      # (N, 106)
    ldm134_confidence: np.ndarray      # (N, 134)


def load_packed_bin(path_or_dir: str | Path) -> App8PackedBin:
    """Загружает агрегированный пакет ракурса (только ключевые точки, коэффициенты и уверенности)."""
    p = Path(path_or_dir)
    if p.is_dir():
        npz_files = list(p.glob("*.npz"))
        if not npz_files:
            raise FileNotFoundError(f"No .npz file found in {p}")
        npz_file = npz_files[0]
    else:
        npz_file = p
        
    with np.load(npz_file, allow_pickle=False) as data:
        return App8PackedBin(
            bin_name=str(data["bin_name"]),
            canonical_yaw=float(data["canonical_yaw"][0]),
            photo_ids=list(data["photo_ids"]),
            dates_iso=list(data["dates_iso"]),
            angles_deg=data["angles_deg"],
            alpha_id=data["alpha_id"],
            alpha_exp=data["alpha_exp"],
            ldm106_chronology=data["ldm106_chronology"],
            ldm134_chronology=data["ldm134_chronology"],
            ldm106_confidence=data["ldm106_confidence"],
            ldm134_confidence=data["ldm134_confidence"],
        )


def get_ldm134(rec: App8Record,
               space: Literal["identity_only", "object", "chronology"] = "identity_only") -> np.ndarray:
    """Извлекает 134 опорных анатомических ориентира в выбранном пространстве (134, 3)."""
    if space == "identity_only":
        return rec.vertices_identity_only[rec.ldm134_indices]
    elif space == "object":
        return rec.vertices_object[rec.ldm134_indices]
    elif space == "chronology":
        return rec.vertices_chronology[rec.ldm134_indices]
    raise ValueError(f"Unknown space: {space}")


def get_ldm106(rec: App8Record,
               space: Literal["identity_only", "object", "chronology"] = "identity_only") -> np.ndarray:
    """Извлекает 106 ориентиров в выбранном пространстве (106, 3)."""
    if space == "identity_only":
        return rec.vertices_identity_only[rec.ldm106_indices]
    elif space == "object":
        return rec.vertices_object[rec.ldm106_indices]
    elif space == "chronology":
        return rec.vertices_chronology[rec.ldm106_indices]
    raise ValueError(f"Unknown space: {space}")
