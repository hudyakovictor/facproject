import numpy as np
import pytest
from server.uv_texture import bake_photo_to_uv
from server import calibration


def test_uv_baker_maps_template_triangle_and_masks_outside():
    image = np.zeros((32, 32, 3), np.uint8)
    image[..., 0] = np.arange(32)[None, :]
    image[..., 1] = np.arange(32)[:, None]
    uv = np.array([[.1, .1], [.9, .1], [.5, .9]], np.float32)
    atlas, mask = bake_photo_to_uv(image, uv, uv, np.array([[0, 1, 2]]), 96)
    assert atlas.shape == (96, 96, 3)
    assert mask.sum() > 1500
    assert mask[2, 2] == 0
    assert np.max(atlas[..., 0]) > 20


def test_noise_calibration_uses_within_person_only_and_saves_atomically(tmp_path, monkeypatch):
    monkeypatch.setattr(calibration, "ROOT", tmp_path)
    meshes = {}
    for person in range(7):
        for view, delta in enumerate((0.0, .002, .003)):
            meshes[f"{person}-{view}"] = np.full((8, 3), person * .4 + delta, np.float32)
    groups = [{"label": f"P{i}", "photo_ids": [f"{i}-0", f"{i}-1", f"{i}-2"]} for i in range(7)]
    result = calibration.calculate_noise(groups, lambda photo_id: meshes[photo_id])
    assert result["participant_count"] == 7
    assert result["photo_count"] == 21
    # Person-to-person offset is excluded; only per-person view variation remains.
    assert 0 < result["threshold"][0] < .01
    assert calibration.load_noise()["vertex_count"] == 8


@pytest.mark.parametrize("size", [16, 24, 32, 48, 64, 96, 128, 192, 256, 384])
def test_uv_baker_resolution_sweep(size):
    image = np.zeros((48, 64, 3), np.uint8)
    image[..., 0] = np.arange(64)[None, :] * 4
    image[..., 1] = np.arange(48)[:, None] * 5
    uv = np.array([[.12, .10], [.88, .10], [.50, .90]], np.float32)
    atlas, mask = bake_photo_to_uv(image, uv, uv, np.array([[0, 1, 2]]), size)
    assert atlas.shape == (size, size, 3)
    assert mask.shape == (size, size) and mask.any()
    assert np.isfinite(atlas).all()


@pytest.mark.parametrize("image,src,uv,tri,size", [
    (np.zeros((8,8),np.uint8), np.zeros((3,2)), np.zeros((3,2)), np.array([[0,1,2]]), 16),
    (np.zeros((1,8,3),np.uint8), np.zeros((3,2)), np.zeros((3,2)), np.array([[0,1,2]]), 16),
    (np.zeros((8,8,3),np.uint8), np.zeros((3,2)), np.zeros((3,2)), np.array([[0,1,2]]), 1),
    (np.zeros((8,8,3),np.uint8), np.zeros((4,2)), np.zeros((3,2)), np.array([[0,1,2]]), 16),
    (np.zeros((8,8,3),np.uint8), np.array([[0,0],[1,0],[np.nan,1]]), np.zeros((3,2)), np.array([[0,1,2]]), 16),
    (np.zeros((8,8,3),np.uint8), np.zeros((3,2)), np.zeros((3,2)), np.array([[0,1,3]]), 16),
    (np.zeros((8,8,3),np.uint8), np.zeros((3,2)), np.zeros((3,2)), np.array([[0.,1.5,2.]]), 16),
])
def test_uv_baker_rejects_malformed_inputs(image,src,uv,tri,size):
    with pytest.raises(ValueError):
        bake_photo_to_uv(image,src,uv,tri,size)


@pytest.mark.parametrize("offset", [1.1, 1.5, 2.0, 5.0, 20.0])
def test_uv_baker_outside_source_is_not_clamped_or_filled(offset):
    image=np.full((32,32,3),180,np.uint8)
    uv=np.array([[.1,.1],[.9,.1],[.5,.9]],np.float32)
    src=uv+offset
    atlas,mask=bake_photo_to_uv(image,src,uv,np.array([[0,1,2]]),64)
    assert not mask.any()
    assert not atlas.any()
