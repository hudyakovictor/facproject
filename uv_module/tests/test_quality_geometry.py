import cv2
import numpy as np
import pandas as pd
import pytest

from uv_module.dataset_manifest import assign_grouped_splits, filename_date, source_stem
from uv_module.hd_uv_generator import HDUVConfig, HDUVTextureGenerator
from uv_module.provenance import MISSING, measurement_mask
from uv_module.uv_baker import UVBaker, UVBakerConfig
from uv_module.visibility import compute_triangle_visibility
from uv_module.warp_metrics import triangle_warp_metrics, weighted_quantiles


def fixture():
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    y, x = np.indices(image.shape[:2])
    image[..., 0], image[..., 1], image[..., 2] = x, y, x + y
    uv = np.array([[0, 1], [1, 1], [0, 0]], dtype=float)
    photo = np.array([[4, 5], [19, 5], [4, 20]], dtype=float)
    vertices = np.array([[0, 0, 1], [1, 0, 1], [0, 1, 1]], dtype=float)
    return image, uv, photo, vertices, np.array([[0, 1, 2]])


@pytest.mark.parametrize("method", ["bake", "bake_via_barycentric"])
def test_coordinate_grid_transfer_and_uv_v_direction(method):
    image, uv, photo, _, faces = fixture()
    baker = UVBaker(16, 1, UVBakerConfig(interpolation=cv2.INTER_LINEAR))
    raw, visible, confidence, original = getattr(baker, method)(image, photo, uv, faces, np.ones(1), collect_provenance=True)
    assert np.array_equal(raw[5, 5], image[10, 9])
    assert visible[5, 5] and original[5, 5] and confidence[5, 5] == 1
    trace = baker.last_provenance
    assert trace["triangle_id"][5, 5] == 0
    assert trace["source_xy"][5, 5] == pytest.approx([9, 10])
    assert trace["barycentric"][5, 5].sum() == pytest.approx(1)
    assert trace["external_occlusion"][5, 5] == -1
    assert not trace["measurement_suitable"].any()


def test_backfaces_and_grazing_faces_have_zero_weight():
    _, _, photo, vertices, _ = fixture()
    faces = np.array([[0, 1, 2], [0, 2, 1]])
    weights = compute_triangle_visibility(vertices, faces, angle_threshold_deg=75)
    assert weights[0] == 1 and weights[1] == 0


def test_full_triangle_depth_occlusion_not_just_shared_centroid():
    _, uv, photo, vertices, _ = fixture()
    all_vertices = np.concatenate((vertices, vertices + [0, 0, 1]))
    all_photo = np.concatenate((photo, photo))
    faces = np.array([[0, 1, 2], [3, 4, 5]])
    weights, buffers = compute_triangle_visibility(all_vertices, faces, use_zbuffer=True,
                                                   vertices_2d=all_photo, image_size=(64, 64),
                                                   z_tolerance=0.01, return_buffers=True)
    assert weights[0] == 1 and weights[1] == 0
    image = np.ones((64, 64, 3), dtype=np.uint8) * 100
    baker = UVBaker(16, 1)
    raw, visible, _, _ = baker.bake_via_barycentric(image, all_photo, np.concatenate((uv, uv)), faces,
                                                   weights, collect_provenance=True, visibility_buffers=buffers)
    assert visible[5, 5] and raw[5, 5, 0] == 100
    assert baker.last_provenance["triangle_id"][5, 5] == 0


def test_out_of_image_coordinates_are_not_border_replicated_observations():
    image, uv, photo, _, faces = fixture()
    baker = UVBaker(16, 1)
    raw, mask, _, _ = baker.bake_via_barycentric(image, photo - [8, 9], uv, faces, np.ones(1), collect_provenance=True)
    assert not mask[0, 0]
    assert np.all(raw[0, 0] == 0)
    assert baker.last_provenance["raw_method"][0, 0] == MISSING
    assert not baker.last_provenance["in_image"][0, 0]


def test_supersampling_does_not_blend_missing_pixels_into_black_edges():
    baker = UVBaker(1, 2)
    raw = np.zeros((2, 2, 3), dtype=np.float32)
    raw[0, 0] = 200
    mask = np.array([[True, False], [False, False]])
    confidence = mask.astype(np.float32) * 0.7
    result, visible, conf, original = baker._downsample_results(raw, mask, confidence, mask)
    assert np.all(result == 200)
    assert visible[0, 0] and original[0, 0]
    assert conf[0, 0] == pytest.approx(0.7)


def test_overlapping_charts_use_one_real_source_not_an_average_coordinate():
    image, uv, photo, _, _ = fixture()
    faces = np.array([[0, 1, 2], [3, 4, 5]])
    baker = UVBaker(16, 1, UVBakerConfig(interpolation=cv2.INTER_LINEAR))
    raw, _, _, _ = baker.bake_via_barycentric(image, np.concatenate((photo, photo + 20)), np.concatenate((uv, uv)),
                                             faces, np.array([0.2, 0.8]), collect_provenance=True)
    assert np.array_equal(raw[5, 5], image[30, 29])
    assert baker.last_provenance["triangle_id"][5, 5] == 1
    assert baker.last_provenance["contribution_count"][5, 5] == 2


def test_two_transform_channels_keep_separate_scales_and_orientation():
    _, _, _, _, faces = fixture()
    vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float)
    uv = np.array([[0, 0], [1, 0], [0, 1]], dtype=float)
    photo = np.array([[0, 0], [20, 0], [0, 40]], dtype=float)
    metrics = triangle_warp_metrics(vertices, faces, uv, photo, 33)
    assert metrics["anisotropy_3d_uv"][0] == pytest.approx(1)
    assert metrics["anisotropy_uv_photo"][0] == pytest.approx(2)
    assert metrics["density_uv_photo"][0] == pytest.approx(20 * 40 / 32 ** 2)
    assert metrics["orientation_uv_photo"][0] == -1
    scaled = triangle_warp_metrics(vertices * 2, faces, uv, photo, 33)
    assert np.allclose(scaled["scales_3d_uv"], metrics["scales_3d_uv"] / 2)
    assert np.allclose(scaled["jacobian_uv_photo"], metrics["jacobian_uv_photo"])


def test_degenerate_uv_is_unmeasurable_not_infinite_anomaly():
    _, uv, photo, vertices, faces = fixture()
    uv[:] = 0.5
    metrics = triangle_warp_metrics(vertices, faces, uv, photo, 16)
    assert not metrics["valid_3d_uv"].any()
    assert np.isnan(metrics["anisotropy_uv_photo"]).all()


def test_generator_preserves_raw_and_requires_declared_projection_for_diagnostics():
    image, uv, photo, vertices, faces = fixture()
    config = HDUVConfig(uv_size=16, super_sample=1, collect_provenance=True, enable_detail_boost=False,
                        enable_symmetry_fill=False, device="cpu")
    generator = HDUVTextureGenerator(config)
    recon = {"vertices": vertices, "vertices_3d": vertices, "vertices_2d": photo, "uv_coords": uv, "triangles": faces}
    with pytest.raises(ValueError, match="original-pixel"):
        generator.generate(image, recon)
    recon["projection_space"] = "original"
    result = generator.generate(image, recon)
    assert len(result) == 5
    aux = result[4]
    assert aux["uv_texture_raw"][5, 5] == pytest.approx(image[10, 9], abs=1)
    assert aux["provenance"]["triangle_id"][5, 5] == 0
    assert not measurement_mask(aux["provenance"]).any()


def test_area_weights_do_not_let_many_tiny_triangles_dominate():
    values = np.r_[np.zeros(100), 10]
    weights = np.r_[np.ones(100) * 0.001, 10]
    assert weighted_quantiles(values, weights, (0.5,))[0] > 9


def test_source_name_and_grouped_closed_split():
    from pathlib import Path
    assert source_stem(Path("2008_02_14_3__d6f0e64ab9bf.png")) == "2008_02_14_3"
    assert filename_date("2008_02_14_3") == "2008-02-14"
    frame = pd.DataFrame({"sample_id": range(12), "split_group": [f"g{i // 2}" for i in range(12)],
                          "quality_label_reference": ["normal", "distorted"] * 6})
    assignments = assign_grouped_splits(frame)
    frame["partition"] = frame.split_group.map(assignments)
    assert frame.groupby("split_group").partition.nunique().max() == 1
    assert set(frame.partition) == {"train", "validation", "test"}


def test_exif_matrix_and_inverse_pixel_mapping():
    from uv_module.reconstruction_adapter import exif_pixel_matrix
    matrix = exif_pixel_matrix(6, 10, 20)
    points = np.array([[0, 0, 1], [9, 19, 1]], dtype=float)
    transformed = points @ matrix.T
    assert transformed[:, :2] == pytest.approx(np.array([[19, 0], [0, 9]]))
    assert transformed @ np.linalg.inv(matrix).T == pytest.approx(points)


def test_exporter_retains_raw_float_and_provenance(tmp_path):
    from uv_module.uvio import UVIOExporter
    image, uv, photo, vertices, faces = fixture()
    generator = HDUVTextureGenerator(HDUVConfig(uv_size=16, super_sample=1, collect_provenance=True,
                                                enable_detail_boost=False, enable_symmetry_fill=False))
    recon = {"vertices": vertices, "vertices_2d": photo, "uv_coords": uv, "triangles": faces, "projection_space": "original"}
    analysis, beauty, mask, confidence, aux = generator.generate(image, recon)
    saved = UVIOExporter(save_auxiliary=True).save_all(str(tmp_path), "sample", vertices, faces, uv, analysis, beauty, mask, confidence, aux)
    assert saved.texture_raw_path and saved.provenance_path
    with np.load(tmp_path / "sample_raw_float.npz") as original:
        assert np.array_equal(original["texture"], aux["uv_texture_raw"])
    with np.load(saved.provenance_path) as trace:
        assert trace["triangle_id"][5, 5] == 0
