import numpy as np
import pytest
from PIL import Image

from fastobjects.atlas import Atlas
from fastobjects.errors import AtlasOverflowError


def solid(w, h, rgba):
    return Image.new("RGBA", (w, h), rgba)


def test_uvs_and_sizes_match_inputs():
    imgs = [solid(10, 20, (255, 0, 0, 255)), solid(30, 5, (0, 255, 0, 255))]
    atlas = Atlas(imgs, max_size=1024)
    assert atlas.uvs.shape == (2, 4)
    assert atlas.sizes.shape == (2, 2)
    np.testing.assert_array_equal(atlas.sizes[0], [10, 20])
    np.testing.assert_array_equal(atlas.sizes[1], [30, 5])
    W, H = atlas.size
    for i, (w, h) in enumerate([(10, 20), (30, 5)]):
        u0, v0, u1, v1 = atlas.uvs[i]
        assert 0.0 <= u0 < u1 <= 1.0 and 0.0 <= v0 < v1 <= 1.0
        assert round((u1 - u0) * W) == w
        assert round((v1 - v0) * H) == h


def test_images_do_not_overlap_in_uv_space():
    imgs = [solid(20, 20, (255, 0, 0, 255)) for _ in range(4)]
    atlas = Atlas(imgs, max_size=1024)
    W, H = atlas.size
    boxes = []
    for u0, v0, u1, v1 in atlas.uvs:
        boxes.append((round(u0 * W), round(v0 * H), round(u1 * W), round(v1 * H)))
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            ax0, ay0, ax1, ay1 = boxes[i]
            bx0, by0, bx1, by1 = boxes[j]
            overlap = ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1
            assert not overlap


def test_pixels_contain_each_image_color():
    imgs = [solid(8, 8, (255, 0, 0, 255)), solid(8, 8, (0, 255, 0, 255))]
    atlas = Atlas(imgs, max_size=1024)
    W, H = atlas.size
    arr = np.frombuffer(atlas.pixels, dtype="u1").reshape(H, W, 4)
    for i, color in enumerate([(255, 0, 0), (0, 255, 0)]):
        u0, v0, u1, v1 = atlas.uvs[i]
        cx = int((u0 + u1) / 2 * W)
        cy = int((v0 + v1) / 2 * H)
        assert tuple(arr[cy, cx, :3]) == color


def test_edge_extruded_padding_no_transparent_gutter():
    imgs = [solid(8, 8, (255, 0, 0, 255)), solid(8, 8, (0, 255, 0, 255))]
    atlas = Atlas(imgs, max_size=1024, padding=1)
    W, H = atlas.size
    arr = np.frombuffer(atlas.pixels, dtype="u1").reshape(H, W, 4)
    u0, v0, u1, v1 = atlas.uvs[0]
    x0 = round(u0 * W)
    ymid = int((v0 + v1) / 2 * H)
    assert tuple(arr[ymid, x0 - 1, :3]) == (255, 0, 0)  # borda extrudada, não vizinho


def test_overflow_raises_actionable():
    imgs = [solid(200, 200, (255, 0, 0, 255))]
    with pytest.raises(AtlasOverflowError, match="não cabem"):
        Atlas(imgs, max_size=64)


def test_deterministic():
    imgs = [solid(10, 20, (1, 2, 3, 255)), solid(15, 15, (4, 5, 6, 255))]
    a = Atlas(imgs, max_size=1024)
    b = Atlas(imgs, max_size=1024)
    assert a.size == b.size
    np.testing.assert_array_equal(a.uvs, b.uvs)
