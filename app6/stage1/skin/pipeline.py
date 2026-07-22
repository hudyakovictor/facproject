"""Skin Stage1 pipeline — evidence-path v5.

Key fixes vs previous:
- pose CSV is soft prior, not hard kill of quality_weight
- separate physical / evidence quality maps
- usable-evidence previews
- per-zone applicability diagnostics
- density no longer hard-clipped to 100 (handled in quality.py)
- production_evidence_allowed more honest until gates mature
🎯 CONVENTIONS v2 → CRITICAL: сборка skin-пакета; статус: ⚠️ IN PROGRESS
"""
from __future__ import annotations
from pathlib import Path
import cv2
import numpy as np
from .atlas_registry import AtlasRegistry
from .contracts import SCHEMAS
from .manifest import create_manifest, finalize_manifest
from .projection import rasterize_surface, project_atlas
from .quality import quality_maps, applicability, per_zone_applicability
from .serialization import atomic_json, atomic_npz, sha256_file
from .texture.basic import extract_basic
from .texture.features import FEATURES, extract_texture_features
from .wrinkles.classical import detect as detect_wrinkles
from .wrinkles.ffhq_adapter import FFHQWrinkleAdapter
from .local_features.detector import detect as detect_local
from .material.evidence import build as material_evidence
from .sensitivity.degradation import benchmark
from .pose_policy import PosePolicy
from .contamination import FaceParsingAdapter
from .patch_sampler import sample_zone_patches
from .photometric import branches as photometric_branches
from .previews import save_previews, save_wrinkle_overlay
from ..status_logger import log_status, log_blocker, log_warning


def _resolve_pose_policy_csv(atlas_path: Path) -> Path:
    atlas_path = Path(atlas_path)
    candidates = [
        atlas_path.with_name('pose_policy_v3_9bins.csv'),
        atlas_path.parent / 'pose_policy_v3_9bins.csv',
        Path(__file__).resolve().parents[2] / 'atlas' / 'pose_policy_v3_9bins.csv',
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError(
        'pose_policy_v3_9bins.csv not found. Tried: ' + ', '.join(str(c) for c in candidates)
    )


def build_skin_package(*, photo_id, input_path, bgr, out_dir, triangles, vertices_original_xy, vertices_depth, normals, surface_vertices, vertex_visibility, face_mask_data_path, atlas_path, coordinate_chain, models, config, pose):
    """🎯 CRITICAL → Извлечение skin features из оригинальных пикселей фото.

    НЕ использует UV текстуру для анализа! Вся аналитика на оригинальных пикселях
    через face_mask (skin segmentation) и atlas projection.

    🔗 DEPENDS ON:
      - engine._one() — вызывается после 3DDFA inference
      - face_mask.npz — семантическая маска кожи
      - atlas (texture_zones_bfm35709_v3.npz) — 20 зон атласа

    ⚠️ IN PROGRESS:
      - Нет проверки что face_mask покрывает достаточно кожи
      - Нет валидации качества texture features (blur, noise)
      - Нет проверки что atlas projection корректен

    💡 NOTE:
      - Использует soft pose policy (не убирает evidence полностью)
      - Quality weight = physical * pose_soft (не zero-kill)
      - Результаты в out_dir/skin/

    🚨 WARNING:
      - При отсутствии face_mask — ValueError (не создаёт заглушку)
      - При отсутствии весов FFHQ — wrinkle/ffhq.npz не создаётся
    """
    log_status("build_skin_package", "complete")
    face_mask_data_path = Path(face_mask_data_path)
    if not face_mask_data_path.is_file():
        raise ValueError('face_mask.npz unavailable; refusing UV or resized fallback for skin evidence')
    with np.load(face_mask_data_path, allow_pickle=False) as fm:
        skin_mask_original = fm['mask_original'].astype(bool)
        if skin_mask_original.shape != bgr.shape[:2]:
            raise ValueError('face_mask mask_original/source shape mismatch')
    root = Path(out_dir) / 'skin'
    root.mkdir(parents=True, exist_ok=True)
    atlas = AtlasRegistry(atlas_path, triangles)
    manifest = create_manifest(
        photo_id, input_path, bgr,
        coordinate_chain=coordinate_chain, models=models, atlas=atlas.describe(), config=config,
        backend={'rasterizer': 'numpy_cpu_zbuffer_v2_physics_density'},
        warnings=[
            'v5 evidence-path: soft pose prior, usable previews, density winsor (no hard clip 100)',
        ],
    )
    manifest['source_mask'] = {
        'path': '../face_mask.npz',
        'preview': '../face_mask.png',
        'sha256': sha256_file(face_mask_data_path),
        'array': 'mask_original',
        'semantics': 'existing facial-skin mask; background/eyes/brows/lips excluded',
    }
    H, W = bgr.shape[:2]
    xy = np.asarray(vertices_original_xy, np.float32)
    x0 = max(0, int(np.floor(xy[:, 0].min())) - 2)
    y0 = max(0, int(np.floor(xy[:, 1].min())) - 2)
    x1 = min(W, int(np.ceil(xy[:, 0].max())) + 3)
    y1 = min(H, int(np.ceil(xy[:, 1].max())) + 3)
    if x1 <= x0 or y1 <= y0:
        raise ValueError('projected face outside original image')
    crop = bgr[y0:y1, x0:x1]
    seg = skin_mask_original[y0:y1, x0:x1]
    contamination_meta = {'state': 'weights_unavailable'}
    contamination_keep = np.ones(seg.shape, bool)
    repo = Path(atlas_path).resolve().parents[2] / 'FFHQ-detect-face-wrinkles'
    fp = repo / 'res/cp/face_segmentation.pth'
    if fp.is_file():
        parser = FaceParsingAdapter(repo, fp)
        cont = parser.predict(crop)
        contamination_keep = ~(cont['hair'] | cont['glasses'] | cont['external_occlusion'])
        atomic_npz(root / 'contamination_maps.npz', hair=cont['hair'], glasses=cont['glasses'], external_occlusion=cont['external_occlusion'])
        contamination_meta = {'state': 'complete', **parser.metadata()}

    local_xy = xy - [x0, y0]

    try:
        sv = np.asarray(surface_vertices, np.float64)
        tri = np.asarray(triangles, np.int64)
        v0 = sv[tri[:, 0]]; v1 = sv[tri[:, 1]]; v2 = sv[tri[:, 2]]
        tri_area = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1).astype(np.float32)
    except Exception:
        tri_area = None

    r = rasterize_surface(
        local_xy, vertices_depth, normals, triangles, crop.shape, vertex_visibility,
        surface_vertices=surface_vertices, triangle_surface_areas=tri_area,
    )
    valid = r.triangle_id >= 0
    r.source_xy[..., 0][valid] += x0
    r.source_xy[..., 1][valid] += y0
    p = project_atlas(r, atlas, seg)
    projected_density_map = p.pop('projected_density_map', None)
    domain = p.pop('domain_mask')
    w14 = p.pop('wrinkle_membership_w14')

    # analysis mask: intersection of segmentation, contamination and atlas domain
    analysis_mask = (seg & contamination_keep & domain).astype(bool)
    cv2.imwrite(str(root / 'analysis_mask.png'), analysis_mask.astype(np.uint8) * 255)

    qm = quality_maps(
        crop, domain, r.incidence, r.projection_confidence, r.triangle_id,
        projected_density_map=projected_density_map,
    )
    qm['contamination_keep'] = contamination_keep
    safe_tid = np.clip(r.triangle_id, 0, len(atlas.skin) - 1)
    mesh_skin = (r.triangle_id >= 0) & atlas.skin[safe_tid]
    union = np.sum(seg | mesh_skin)
    qm['semantic_projection_iou'] = np.array(float(np.sum(seg & mesh_skin) / union) if union else 0., np.float32)

    # physical quality after contamination (NO pose hard-kill)
    qm['quality_weight_physical'] = (qm['quality_weight'] * contamination_keep.astype(np.float32)).astype(np.float32)
    qm['effective_resolution'] = (qm['effective_resolution'] * contamination_keep.astype(np.float32)).astype(np.float32)

    policy_csv = _resolve_pose_policy_csv(Path(atlas_path))
    policy = PosePolicy(policy_csv, allow_default=False)
    pose_prior, pm = policy.weights(p['zone_id_a20'], pose.get('yaw', 0))
    soft_pose, soft_meta, observed = policy.soft_evidence_weights(
        p['zone_id_a20'], pose.get('yaw', 0),
        domain=domain,
        projection_confidence=r.projection_confidence,
        incidence=r.incidence,
        visibility=r.visibility,
    )
    pm.update(soft_meta)

    qm['pose_weight'] = pose_prior.astype(np.float32)          # CSV prior (may be 0)
    qm['pose_soft_weight'] = soft_pose.astype(np.float32)      # evidence multiplier
    qm['observed_mask'] = observed.astype(np.uint8)

    # evidence weight used by extractors
    qm['quality_weight'] = (qm['quality_weight_physical'] * soft_pose).astype(np.float32)
    # effective resolution: scale by soft pose (sqrt), no fake floor on hard zeros
    er_scale = np.sqrt(np.clip(soft_pose, 0.0, 1.0)).astype(np.float32)
    qm['effective_resolution'] = (qm['effective_resolution'] * er_scale).astype(np.float32)

    usable_mask = analysis_mask & (qm['quality_weight'] > 1e-6) & observed

    er_valid = usable_mask & np.isfinite(qm['effective_resolution'])
    er_med = float(np.median(qm['effective_resolution'][er_valid])) if er_valid.any() else 1.2

    ap = applicability(qm, domain, W, H)
    zone_app = per_zone_applicability(
        p['zone_id_a20'], domain, qm['quality_weight'], pose_weight=pose_prior,
    )
    geom_wo_ev = sum(1 for z in zone_app if z['geometry_without_evidence'])
    usable_zones = sum(1 for z in zone_app if z['state'] == 'usable')

    surface_area = tri_area if tri_area is not None else np.ones(len(triangles), np.float32)

    atomic_npz(
        root / 'surface_observations.npz',
        schema=np.array(SCHEMAS['surface']),
        triangle_id=r.triangle_id,
        barycentric=r.barycentric.astype(np.float16),
        source_xy=r.source_xy,
        depth=r.depth,
        normal=r.normal.astype(np.float16),
        incidence=r.incidence.astype(np.float16),
        visibility=r.visibility.astype(np.float16),
        projection_confidence=r.projection_confidence.astype(np.float16),
        triangle_surface_area=surface_area.astype(np.float32),
        surface_vertices=np.asarray(surface_vertices, np.float32),
        triangles=np.asarray(triangles, np.int32),
        map_origin_xy=np.array([x0, y0]),
        original_shape=np.array([H, W]),
        projected_density_map=projected_density_map.astype(np.float32) if projected_density_map is not None else np.zeros_like(r.triangle_id, dtype=np.float32),
    )
    atomic_npz(root / 'atlas_projection.npz', schema=np.array(SCHEMAS['atlas']), **p)
    save_previews(root / 'previews', crop, p['zone_id_a20'], domain, qm['quality_weight'], usable_mask=usable_mask)
    atomic_npz(root / 'quality_maps.npz', schema=np.array(SCHEMAS['quality']), **qm)
    atomic_npz(root / 'photometric_branches.npz', **photometric_branches(crop, domain))

    # production flag: true only if enough usable zones and low geometry-without-evidence rate
    prod_ok = usable_zones >= 6 and geom_wo_ev <= 4
    dens_meta = {}
    try:
        import ast
        dens_meta = ast.literal_eval(str(qm.get('density_meta_json', '')))
    except Exception:
        dens_meta = {}

    hole_px = int((analysis_mask & (p['zone_id_a20'] < 0)).sum())
    atomic_json(root / 'quality.json', {
        'schema': SCHEMAS['quality'],
        'implementation_status': 'v5_soft_pose_evidence_path',
        'production_evidence_allowed': bool(prod_ok),
        'applicability': ap,
        'per_zone_applicability': zone_app,
        'components': {
            'domain_pixels': int(domain.sum()),
            'analysis_mask_pixels': int(analysis_mask.sum()),
            'usable_pixels': int(usable_mask.sum()),
            'image_pixels': int(domain.size),
            'usable_zones_a20': int(usable_zones),
            'geometry_without_evidence_zones': int(geom_wo_ev),
            'mask_without_zone_pixels': hole_px,
        },
        'missing_components': (['hair_probability', 'external_occlusion_probability'] if contamination_meta['state'] != 'complete' else []),
        'contamination': contamination_meta,
        'pose': pose,
        'pose_policy': pm,
        'density_meta': dens_meta,
        'evidence_contract': {
            'geometry': 'atlas domain_mask / zone_id_a20',
            'support': 'quality_weight_physical * pose_soft_weight',
            'evidence': 'features/wrinkles gated by quality_weight (soft pose)',
            'pose_csv_hard_kill': False,
            'preview_usable_file': 'previews/atlas_A20_overlay_usable.png',
            'preview_geometry_file': 'previews/atlas_A20_overlay.png',
        },
        'effective_resolution_physics': 'projected_density * focus * sqrt(inc) * processing_survival * noise_survival * sqrt(pose_soft)',
    })

    patches = []
    for level, zmap, n in [('A20', p['zone_id_a20'], 20), ('S40', p['zone_id_s40'], 40)]:
        for zi in range(n):
            for q in sample_zone_patches(zmap, zi, qm['quality_weight']):
                patches.append((level, zi, q['patch_id'], *q['bbox_xyxy'], q['pixel_count'], q['effective_support']))
    pd = np.dtype([
        ('level', 'U3'), ('zone', 'i2'), ('patch_id', 'U24'),
        ('x0', 'i4'), ('y0', 'i4'), ('x1', 'i4'), ('y1', 'i4'),
        ('pixels', 'i4'), ('support', 'f4'),
    ])
    atomic_npz(root / 'patch_index.npz', schema=np.array('skin-patch-index-v1'), patches=np.array(patches, dtype=pd))

    basic = extract_basic(crop, qm['quality_weight'], p['zone_id_a20'], p['zone_id_s40'])
    atomic_npz(
        root / 'features/basic_macro.npz',
        schema=np.array(SCHEMAS['features']),
        zone_level=np.array([x['zone_level'] for x in basic]),
        zone_id=np.array([x['zone_id'] for x in basic]),
        state=np.array([x['state'] for x in basic]),
        effective_support=np.array([x['effective_support'] for x in basic]),
        values=np.array([[x['luminance_median'], x['luminance_mad'], x['luminance_iqr']] for x in basic], np.float32),
        columns=np.array(['luminance_median', 'luminance_mad', 'luminance_iqr']),
        provenance_ref=np.array([
            f"atlas_projection.npz#{x['zone_level']}:{x['zone_id']}|surface_observations.npz:source_xy|../face_mask.npz:mask_original"
            for x in basic
        ]),
    )

    texture = extract_texture_features(crop, qm['quality_weight'], p['zone_id_a20'], p['zone_id_s40'])
    if ap['micro_texture']['state'] not in {'usable', 'coarse_only'}:
        for row in texture:
            row['values'][10] = np.nan       # LoG blobs
    if ap['pigmentation']['state'] not in {'usable', 'coarse_only'}:
        for row in texture:
            row['values'][21:24] = np.nan    # spectral low/mid/slope also micro/meso gated
    atomic_npz(
        root / 'features/texture.npz',
        schema=np.array(SCHEMAS['features']),
        zone_level=np.array([x['zone_level'] for x in texture]),
        zone_id=np.array([x['zone_id'] for x in texture]),
        state=np.array([x['state'] for x in texture]),
        effective_support=np.array([x['effective_support'] for x in texture]),
        values=np.stack([x['values'] for x in texture]),
        columns=np.array(FEATURES),
        provenance_ref=np.array([
            f"atlas_projection.npz#{x['zone_level']}:{x['zone_id']}|surface_observations.npz:source_xy|../face_mask.npz:mask_original"
            for x in texture
        ]),
    )
    atomic_json(root / 'features/summary.json', {
        'schema': SCHEMAS['features'],
        'state': 'complete',
        'implementation_status': 'v5_soft_pose_gated',
        'production_evidence_allowed': bool(prod_ok),
        'implemented_families': ['macro', 'LBP', 'masked_GLCM_full_6metrics', 'Gabor', 'spectrum_full_low_mid_high_slope', 'structure_tensor', 'LoG', 'pigmentation_Lab'],
        'texture_matrix': 'features/texture.npz',
        'source': 'original photo pixels gated by face_mask + soft pose evidence weight',
        'usable_zones_a20': int(usable_zones),
    })

    lr, lc, lm = detect_local(crop, qm['quality_weight'], r.triangle_id, r.barycentric, triangles, surface_vertices)
    atomic_npz(root / 'features/local_candidates.npz', schema=np.array(SCHEMAS['features']), response=lr.astype(np.float16), candidates=lc)
    atomic_json(root / 'features/local_candidates.json', {'schema': SCHEMAS['features'], 'state': 'complete', 'metadata': lm})

    ridge, sk, points, branches, wm = detect_wrinkles(
        crop, qm['quality_weight'], r.triangle_id, r.barycentric,
        triangles, surface_vertices, w14, er_median=er_med,
    )
    atomic_npz(root / 'wrinkles/classical.npz', schema=np.array(SCHEMAS['wrinkles']), ridge_probability=ridge.astype(np.float16), skeleton=sk, points=points)

    ffstate = 'not_run_weights_unavailable'
    ffmeta = {}
    prob = None
    cpdir = Path(atlas_path).resolve().parents[2] / 'FFHQ-detect-face-wrinkles/res/cp'
    cp = next((x for x in (cpdir / 'wrinkle_model.pth', cpdir / 'best_checkpoint_iou032.pth') if x.is_file()), cpdir / 'wrinkle_model.pth')
    if cp.is_file():
        ad = FFHQWrinkleAdapter(cp.parents[2], cp)
        ffhq_input = np.where(seg[..., None], crop, 0).astype(np.uint8)
        prob = ad.predict(ffhq_input)
        # zero outside usable evidence, not only geometry domain
        prob[~usable_mask] = 0
        atomic_npz(root / 'wrinkles/ffhq.npz', schema=np.array(SCHEMAS['wrinkles']), probability=prob.astype(np.float16))
        ffstate = 'complete'
        ffmeta = ad.metadata()
    atomic_json(root / 'wrinkles/summary.json', {
        'schema': SCHEMAS['wrinkles'],
        'state': 'complete' if ffstate == 'complete' else 'partial',
        'implementation_status': 'v5_scale_adaptive_frangi_meijering_skan',
        'production_evidence_allowed': bool(prod_ok),
        'classical': 'complete',
        'ffhq': ffstate,
        'classical_metadata': wm,
        'ffhq_metadata': ffmeta,
        'branches': branches,
        'surface_units': 'canonical_surface_units_not_mm',
        'detector_policy': 'independent channels scale-adaptive; gated by usable evidence mask',
    })
    save_wrinkle_overlay(root / 'previews', crop, sk, ridge, prob if ffstate == 'complete' else None, domain, usable_mask=usable_mask)

    atomic_json(root / 'material/evidence.json', material_evidence(texture, qm, ap))

    # 💡 Вспомогательный crop/фокус ROI перед извлечением
    def focus(x, m):
        g = cv2.cvtColor(x, cv2.COLOR_BGR2GRAY)
        gx = cv2.Sobel(g, cv2.CV_32F, 1, 0)
        gy = cv2.Sobel(g, cv2.CV_32F, 0, 1)
        return float(np.median(np.hypot(gx[m], gy[m]))) if m.any() else None

    atomic_json(root / 'sensitivity/degradation.json', benchmark(crop, domain, focus))
    return finalize_manifest(root, manifest, 'success')
