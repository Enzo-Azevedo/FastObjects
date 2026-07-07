import moderngl
import numpy as np
import pytest

from fastobjects.batch import SpriteBatch
from fastobjects.shapes import ShapeBatch

BUNNY = "benchmarks/arena/assets/bunny.png"


@pytest.fixture(scope="module")
def gl():
    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.BLEND)
    fbo = ctx.framebuffer(color_attachments=[ctx.texture((64, 64), 4)])
    fbo.use()
    yield ctx, fbo
    ctx.release()


def make_batch(ctx, capacity=100):
    return SpriteBatch(BUNNY, capacity=capacity, ctx=ctx, view_size=(64, 64))


def test_first_draw_uploads_everything(gl):
    ctx, _ = gl
    batch = make_batch(ctx)
    batch.spawn(10)
    batch.draw()
    assert batch._renderer.uploads == 4  # pos + size + rot + color


def test_untouched_frame_uploads_only_pos(gl):
    ctx, _ = gl
    batch = make_batch(ctx)
    g = batch.spawn(10)
    batch.draw()
    base = batch._renderer.uploads
    g.pos += 1.0  # posição não é rastreada: sobe sempre
    batch.draw()
    assert batch._renderer.uploads == base + 1  # só pos


def test_touching_color_reuploads_color_and_shows_on_screen(gl):
    ctx, fbo = gl
    batch = ShapeBatch(capacity=4, ctx=ctx, view_size=(64, 64))
    g = batch.rects(1, x=32.0, y=32.0, w=20.0, h=20.0, color=(1.0, 1.0, 1.0, 1.0))
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    batch.draw()
    base = batch._renderer.uploads
    g.color = (0.0, 1.0, 0.0, 1.0)
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    batch.draw()
    assert batch._renderer.uploads == base + 2  # pos + color
    raw = np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(64, 64, 4)[::-1]
    assert raw[32, 32][1] > 200  # a cor NOVA chegou à GPU
    assert raw[32, 32][0] < 10


def test_reading_marks_dirty_conservatively(gl):
    ctx, _ = gl
    batch = make_batch(ctx)
    g = batch.spawn(5)
    batch.draw()
    base = batch._renderer.uploads
    _ = g.rot  # só leitura: marca mesmo assim (conservador, nunca bug visual)
    batch.draw()
    assert batch._renderer.uploads == base + 2  # pos + rot


def test_spawn_despawn_clear_mark_all(gl):
    ctx, _ = gl
    batch = make_batch(ctx)
    a = batch.spawn(5)
    batch.draw()
    base = batch._renderer.uploads

    batch.spawn(5)  # spawn marca tudo
    batch.draw()
    assert batch._renderer.uploads == base + 4
    base = batch._renderer.uploads

    batch.despawn(a)  # despawn desloca dados por baixo: marca tudo
    batch.draw()
    assert batch._renderer.uploads == base + 4
    base = batch._renderer.uploads

    batch.clear()  # clear marca tudo (com count 0 o draw não sobe nada)
    batch.spawn(3)
    batch.draw()
    assert batch._renderer.uploads == base + 4


def test_batch_level_properties_mark_dirty(gl):
    ctx, _ = gl
    batch = make_batch(ctx)
    batch.spawn(5)
    batch.draw()
    base = batch._renderer.uploads
    batch.color[:1] = (1.0, 0.0, 0.0, 1.0)
    batch.draw()
    assert batch._renderer.uploads == base + 2  # pos + color


def test_shapebatch_uploads_five_columns_then_only_pos(gl):
    ctx, _ = gl
    batch = ShapeBatch(capacity=4, ctx=ctx, view_size=(64, 64))
    batch.rects(2)
    batch.draw()
    assert batch._renderer.uploads == 5  # pos + size + rot + color + kind
    batch.draw()
    assert batch._renderer.uploads == 6  # só pos
