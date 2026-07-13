"""Edge cases (regra permanente): capacity zero, despawn em massa, view_size."""

import random

import moderngl
import numpy as np
import pytest

from fastobjects.errors import CapacityError
from fastobjects.font import Font
from fastobjects.shapes import ShapeBatch
from fastobjects.text import TextBatch


@pytest.fixture(scope="module")
def gl():
    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.BLEND)
    yield ctx
    ctx.release()


def fbo_of(ctx, w, h):
    fbo = ctx.framebuffer(color_attachments=[ctx.texture((w, h), 4)])
    fbo.use()
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    return fbo


def read(fbo, w, h):
    return np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(h, w, 4)[::-1]


def test_capacity_zero_raises_actionable(gl):
    with pytest.raises(ValueError, match="capacity"):
        ShapeBatch(0, ctx=gl, view_size=(128, 64))
    with pytest.raises(ValueError, match="capacity"):
        TextBatch(Font(size=16), 0, ctx=gl, view_size=(128, 64))


def test_spawn_zero_objects_gives_empty_valid_group(gl):
    batch = ShapeBatch(10, ctx=gl, view_size=(128, 64))
    g = batch.rects(0)
    assert len(g) == 0 and batch.count == 0
    batch.draw()  # desenhar vazio não quebra


def test_write_empty_string_gives_empty_valid_group(gl):
    batch = TextBatch(Font(size=16), 10, ctx=gl, view_size=(128, 64))
    g = batch.write("", 0.0, 0.0)
    assert len(g) == 0 and batch.count == 0
    batch.draw()


def test_exact_fit_then_capacity_error(gl):
    batch = ShapeBatch(5, ctx=gl, view_size=(128, 64))
    batch.rects(5)  # lote cheio exato funciona
    assert batch.count == 5
    with pytest.raises(CapacityError, match="capacity"):
        batch.rects(1)


def test_mass_despawn_random_order(gl):
    batch = ShapeBatch(500, ctx=gl, view_size=(128, 64))
    groups = [batch.rects(10, x=float(i)) for i in range(50)]
    rng = random.Random(42)
    rng.shuffle(groups)
    for i, g in enumerate(groups):
        batch.despawn(g)
        for other in groups[i + 1 :]:  # sobreviventes seguem válidos
            assert len(other) == 10
            assert other.pos.shape == (10, 2)
        batch.draw()
    assert batch.count == 0


def test_despawn_twice_raises(gl):
    batch = ShapeBatch(10, ctx=gl, view_size=(128, 64))
    g = batch.rects(3)
    batch.despawn(g)
    with pytest.raises(RuntimeError):
        batch.despawn(g)


def test_view_size_anchors_topleft_after_resize(gl):
    """Contrato do resize: view_size novo => px continuam ancorados no topo-esq."""
    for w, h in ((128, 64), (256, 128)):
        fbo = fbo_of(gl, w, h)
        batch = ShapeBatch(10, ctx=gl, view_size=(w, h))
        batch.rects(1, x=10.0, y=10.0, w=6.0, h=6.0)
        batch.draw()
        px = read(fbo, w, h)
        ys, xs = np.where(px[:, :, 0] > 200)
        assert abs(xs.mean() - 10) < 3 and abs(ys.mean() - 10) < 3
        fbo.release()
