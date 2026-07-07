import moderngl
import numpy as np
import pytest

from fastobjects.shapes import KIND_CIRCLE, KIND_RECT, _ShapeRenderer


@pytest.fixture(scope="module")
def gl():
    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.BLEND)
    fbo = ctx.framebuffer(color_attachments=[ctx.texture((64, 64), 4)])
    fbo.use()
    yield ctx, fbo
    ctx.release()


def read_pixels(fbo) -> np.ndarray:
    """(64, 64, 4) uint8, indexado [linha_do_topo, coluna]."""
    raw = np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(64, 64, 4)
    return raw[::-1]


def shape_row(x, y, w, h, rot, color, kind) -> np.ndarray:
    row = np.zeros((1, 10), dtype="f4")
    row[0] = [x, y, w, h, rot, *color, kind]
    return row


def test_rect_fills_pixels(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    r = _ShapeRenderer(ctx, capacity=16, view_size=(64, 64))
    r.render(shape_row(32, 32, 20, 20, 0.0, (1.0, 0.0, 0.0, 1.0), KIND_RECT), 1)
    px = read_pixels(fbo)
    assert px[32, 32][0] > 200  # centro vermelho
    assert px[32, 24][0] > 200  # dentro da borda esquerda (22 < 24)
    assert px[2, 2][0] < 10  # fundo intacto


def test_circle_sdf_cuts_corners(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    r = _ShapeRenderer(ctx, capacity=16, view_size=(64, 64))
    # bounding box 24x24 -> raio 12, centrado em (32, 32)
    r.render(shape_row(32, 32, 24, 24, 0.0, (0.0, 1.0, 0.0, 1.0), KIND_CIRCLE), 1)
    px = read_pixels(fbo)
    assert px[32, 32][1] > 200  # centro verde
    assert px[22, 32][1] > 200  # 10px acima do centro: dentro do raio 12
    assert px[21, 21][1] < 30  # canto do bounding box: dist ~15.6 > 12, fora


def test_render_zero_count_is_noop(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    r = _ShapeRenderer(ctx, capacity=4, view_size=(64, 64))
    r.render(np.zeros((4, 10), dtype="f4"), 0)
    px = read_pixels(fbo)
    assert px[:, :, :3].max() < 10
