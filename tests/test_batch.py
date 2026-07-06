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
    batch = SpriteBatch(ctx, BUNNY, capacity=100, view_size=(64, 64))
    s = batch.spawn(10, x=5.0, y=7.0)
    assert batch.count == 10
    assert s == slice(0, 10)
    np.testing.assert_allclose(batch.pos[s][:, 0], 5.0)
    np.testing.assert_allclose(batch.pos[s][:, 1], 7.0)
    assert batch.size[0, 0] == 26.0  # largura da textura bunny.png
    assert batch.size[0, 1] == 37.0


def test_spawn_vectorized(gl):
    ctx, _ = gl
    batch = SpriteBatch(ctx, BUNNY, capacity=100, view_size=(64, 64))
    xs = np.arange(20, dtype=np.float32)
    batch.spawn(20, x=xs, y=0.0)
    np.testing.assert_array_equal(batch.pos[:20, 0], xs)


def test_spawn_appends_after_existing(gl):
    ctx, _ = gl
    batch = SpriteBatch(ctx, BUNNY, capacity=100, view_size=(64, 64))
    batch.spawn(10)
    s2 = batch.spawn(5, x=99.0)
    assert s2 == slice(10, 15)
    assert batch.count == 15


def test_spawn_over_capacity_raises_actionable_error(gl):
    ctx, _ = gl
    batch = SpriteBatch(ctx, BUNNY, capacity=10, view_size=(64, 64))
    batch.spawn(8)
    with pytest.raises(CapacityError, match="capacity=13"):
        batch.spawn(5)


def test_clear_resets_count(gl):
    ctx, _ = gl
    batch = SpriteBatch(ctx, BUNNY, capacity=10, view_size=(64, 64))
    batch.spawn(10)
    batch.clear()
    assert batch.count == 0
    batch.spawn(10)  # não deve levantar


def test_views_write_through_to_data(gl):
    ctx, _ = gl
    batch = SpriteBatch(ctx, BUNNY, capacity=10, view_size=(64, 64))
    batch.spawn(3)
    batch.pos[:3, 1] += 100.0
    assert batch.data[0, 1] == 100.0  # view escreve no array base


def test_draw_renders_pixels(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    batch = SpriteBatch(ctx, BUNNY, capacity=10, view_size=(64, 64))
    batch.spawn(1, x=32.0, y=32.0)
    batch.draw()
    raw = np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(64, 64, 4)
    assert raw[:, :, 0].max() > 200  # o coelho branco apareceu
