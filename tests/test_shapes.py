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


def test_rects_fill_rows_and_return_group(gl):
    from fastobjects.group import SpriteGroup
    from fastobjects.shapes import ShapeBatch

    ctx, _ = gl
    batch = ShapeBatch(capacity=100, ctx=ctx, view_size=(64, 64))
    g = batch.rects(5, x=10.0, y=20.0, w=4.0, h=6.0)
    assert isinstance(g, SpriteGroup)
    assert batch.count == 5
    np.testing.assert_allclose(g.x, 10.0)
    np.testing.assert_allclose(batch.data[:5, 9], KIND_RECT)


def test_circles_store_diameter(gl):
    from fastobjects.shapes import ShapeBatch

    ctx, _ = gl
    batch = ShapeBatch(capacity=10, ctx=ctx, view_size=(64, 64))
    g = batch.circles(3, x=1.0, y=2.0, radius=5.0)
    np.testing.assert_allclose(g.size, [[10.0, 10.0]] * 3)  # 2 * radius
    np.testing.assert_allclose(batch.data[:3, 9], KIND_CIRCLE)


def test_lines_convert_to_rotated_rects(gl):
    from fastobjects.shapes import ShapeBatch

    ctx, _ = gl
    batch = ShapeBatch(capacity=10, ctx=ctx, view_size=(64, 64))
    g = batch.lines(1, x1=0.0, y1=0.0, x2=30.0, y2=40.0, width=2.0)
    np.testing.assert_allclose(g.x, 15.0)
    np.testing.assert_allclose(g.y, 20.0)
    np.testing.assert_allclose(g.w, 50.0)  # hypot(30, 40)
    np.testing.assert_allclose(g.h, 2.0)
    np.testing.assert_allclose(g.rot, np.arctan2(40.0, 30.0))
    assert batch.data[0, 9] == KIND_RECT  # linha é retângulo para o shader


def test_line_paints_along_segment(gl):
    from fastobjects.shapes import ShapeBatch

    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    batch = ShapeBatch(capacity=10, ctx=ctx, view_size=(64, 64))
    batch.lines(1, x1=12.0, y1=48.0, x2=52.0, y2=48.0, width=3.0,
                color=(0.0, 0.0, 1.0, 1.0))
    batch.draw()
    px = read_pixels(fbo)
    assert px[48, 32][2] > 200  # meio do segmento azul
    assert px[48, 6][2] < 10  # antes do início (x=6 < 12)
    assert px[20, 32][2] < 10  # longe da linha


def test_mixed_shapes_one_draw_call(gl):
    from fastobjects.shapes import ShapeBatch

    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    batch = ShapeBatch(capacity=10, ctx=ctx, view_size=(64, 64))
    batch.rects(1, x=16.0, y=16.0, w=10.0, h=10.0, color=(1.0, 0.0, 0.0, 1.0))
    batch.circles(1, x=48.0, y=48.0, radius=8.0, color=(0.0, 1.0, 0.0, 1.0))
    batch.draw()
    px = read_pixels(fbo)
    assert px[16, 16][0] > 200  # retângulo vermelho
    assert px[48, 48][1] > 200  # círculo verde


def test_shape_capacity_and_negative_guards(gl):
    from fastobjects.errors import CapacityError
    from fastobjects.shapes import ShapeBatch

    ctx, _ = gl
    with pytest.raises(ValueError, match="capacity=0"):
        ShapeBatch(capacity=0, ctx=ctx, view_size=(64, 64))
    batch = ShapeBatch(capacity=10, ctx=ctx, view_size=(64, 64))
    batch.rects(8)
    with pytest.raises(CapacityError, match="capacity=13"):
        batch.rects(5)
    with pytest.raises(ValueError, match="negativo"):
        batch.circles(-1)


def test_shape_clear_resets(gl):
    from fastobjects.shapes import ShapeBatch

    ctx, _ = gl
    batch = ShapeBatch(capacity=5, ctx=ctx, view_size=(64, 64))
    batch.rects(5)
    batch.clear()
    assert batch.count == 0
    batch.circles(5)  # não deve levantar


def test_shapebatch_exported():
    import fastobjects as fo

    assert fo.ShapeBatch is not None


def test_diagonal_line_exercises_rotation(gl):
    from fastobjects.shapes import ShapeBatch

    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    batch = ShapeBatch(capacity=10, ctx=ctx, view_size=(64, 64))
    batch.lines(1, x1=10.0, y1=10.0, x2=54.0, y2=54.0, width=3.0,
                color=(1.0, 0.0, 1.0, 1.0))
    batch.draw()
    px = read_pixels(fbo)
    assert px[32, 32][0] > 200  # meio da diagonal
    assert px[16, 48][0] < 10  # fora da diagonal (canto oposto)
    assert px[48, 16][0] < 10
