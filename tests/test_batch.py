import moderngl
import numpy as np
import pytest

from fastobjects.batch import SpriteBatch
from fastobjects.errors import CapacityError

BUNNY = "benchmarks/arena/assets/bunny.png"


@pytest.fixture(scope="module")
def gl():
    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.BLEND)
    fbo = ctx.framebuffer(color_attachments=[ctx.texture((64, 64), 4)])
    fbo.use()
    yield ctx, fbo
    ctx.release()


def test_spawn_scalar_fills_rows(gl):
    ctx, _ = gl
    batch = SpriteBatch(BUNNY, capacity=100, ctx=ctx, view_size=(64, 64))
    s = batch.spawn(10, x=5.0, y=7.0)
    assert batch.count == 10
    assert s.slice == slice(0, 10)
    np.testing.assert_allclose(s.x, 5.0)
    np.testing.assert_allclose(s.y, 7.0)
    assert batch.size[0, 0] == 26.0  # largura da textura bunny.png
    assert batch.size[0, 1] == 37.0


def test_spawn_vectorized(gl):
    ctx, _ = gl
    batch = SpriteBatch(BUNNY, capacity=100, ctx=ctx, view_size=(64, 64))
    xs = np.arange(20, dtype=np.float32)
    batch.spawn(20, x=xs, y=0.0)
    np.testing.assert_array_equal(batch.pos[:20, 0], xs)


def test_spawn_appends_after_existing(gl):
    ctx, _ = gl
    batch = SpriteBatch(BUNNY, capacity=100, ctx=ctx, view_size=(64, 64))
    batch.spawn(10)
    s2 = batch.spawn(5, x=99.0)
    assert s2.slice == slice(10, 15)
    assert batch.count == 15


def test_spawn_over_capacity_raises_actionable_error(gl):
    ctx, _ = gl
    batch = SpriteBatch(BUNNY, capacity=10, ctx=ctx, view_size=(64, 64))
    batch.spawn(8)
    with pytest.raises(CapacityError, match="capacity=13"):
        batch.spawn(5)


def test_spawn_negative_n_raises_value_error(gl):
    ctx, _ = gl
    batch = SpriteBatch(BUNNY, capacity=10, ctx=ctx, view_size=(64, 64))
    with pytest.raises(ValueError, match="negativo"):
        batch.spawn(-5)


def test_init_non_positive_capacity_raises_value_error(gl):
    ctx, _ = gl
    with pytest.raises(ValueError, match="capacity=0"):
        SpriteBatch(BUNNY, capacity=0, ctx=ctx, view_size=(64, 64))
    with pytest.raises(ValueError, match="capacity=-1"):
        SpriteBatch(BUNNY, capacity=-1, ctx=ctx, view_size=(64, 64))


def test_clear_resets_count(gl):
    ctx, _ = gl
    batch = SpriteBatch(BUNNY, capacity=10, ctx=ctx, view_size=(64, 64))
    batch.spawn(10)
    batch.clear()
    assert batch.count == 0
    batch.spawn(10)  # não deve levantar


def test_views_write_through_to_columns(gl):
    ctx, _ = gl
    batch = SpriteBatch(BUNNY, capacity=10, ctx=ctx, view_size=(64, 64))
    g = batch.spawn(3)
    batch.pos[:3, 1] += 100.0
    assert g.y[0] == 100.0  # batch e grupo compartilham a mesma coluna


def test_draw_renders_pixels(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    batch = SpriteBatch(BUNNY, capacity=10, ctx=ctx, view_size=(64, 64))
    batch.spawn(1, x=32.0, y=32.0)
    batch.draw()
    raw = np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(64, 64, 4)
    assert raw[:, :, 0].max() > 200  # o coelho branco apareceu


def test_missing_texture_raises_actionable_error(gl):
    ctx, _ = gl
    with pytest.raises(FileNotFoundError, match="nao_existe.png"):
        SpriteBatch("nao_existe.png", capacity=10, ctx=ctx, view_size=(64, 64))


def test_no_window_and_no_ctx_raises_actionable_error():
    from fastobjects import _context

    _context.set_current(None)
    with pytest.raises(RuntimeError, match="fo.Window"):
        SpriteBatch(BUNNY, capacity=10)
