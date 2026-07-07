import moderngl
import numpy as np
import pytest

from fastobjects.batch import SpriteBatch
from fastobjects.group import SpriteGroup

BUNNY = "benchmarks/arena/assets/bunny.png"


@pytest.fixture(scope="module")
def ctx():
    ctx = moderngl.create_standalone_context()
    yield ctx
    ctx.release()


def make_batch(ctx, capacity=100):
    return SpriteBatch(BUNNY, capacity=capacity, ctx=ctx, view_size=(64, 64))


def test_spawn_returns_group(ctx):
    batch = make_batch(ctx)
    g = batch.spawn(10)
    assert isinstance(g, SpriteGroup)
    assert g.slice == slice(0, 10)
    assert len(g) == 10


def test_group_views_write_to_batch_data(ctx):
    batch = make_batch(ctx)
    g = batch.spawn(10, x=1.0, y=2.0)
    g.y += 100.0  # in-place na view: zero cópia
    assert batch.data[0, 1] == 102.0


def test_group_assignment_broadcasts(ctx):
    batch = make_batch(ctx)
    g = batch.spawn(5)
    g.x = 7.0
    np.testing.assert_allclose(batch.data[:5, 0], 7.0)
    g.color = (0.0, 1.0, 0.0, 1.0)
    np.testing.assert_allclose(batch.data[:5, 5:9], [[0.0, 1.0, 0.0, 1.0]] * 5)


def test_scalar_columns_and_size(ctx):
    batch = make_batch(ctx)
    g = batch.spawn(4)
    g.rot = 0.5
    np.testing.assert_allclose(batch.data[:4, 4], 0.5)
    g.w = 10.0
    g.h = 20.0
    np.testing.assert_allclose(batch.data[:4, 2], 10.0)
    np.testing.assert_allclose(batch.data[:4, 3], 20.0)
    np.testing.assert_allclose(g.size, [[10.0, 20.0]] * 4)
    np.testing.assert_allclose(g.pos[:, 0], g.x)


def test_subslice_offsets_into_batch(ctx):
    batch = make_batch(ctx)
    g = batch.spawn(20)
    sub = g[5:10]
    assert isinstance(sub, SpriteGroup)
    assert len(sub) == 5
    assert sub.slice == slice(5, 10)
    sub.x = 9.0
    np.testing.assert_allclose(batch.data[5:10, 0], 9.0)
    assert batch.data[4, 0] == 0.0  # vizinho intacto


def test_subslice_of_second_group_is_absolute(ctx):
    batch = make_batch(ctx)
    batch.spawn(10)
    b = batch.spawn(10)
    sub = b[2:4]
    assert sub.slice == slice(12, 14)


def test_two_groups_do_not_overlap(ctx):
    batch = make_batch(ctx)
    a = batch.spawn(10, x=1.0)
    b = batch.spawn(10, x=2.0)
    assert a.slice == slice(0, 10)
    assert b.slice == slice(10, 20)
    b.x = 5.0
    np.testing.assert_allclose(a.x, 1.0)


def test_getitem_requires_slice_without_step(ctx):
    batch = make_batch(ctx)
    g = batch.spawn(3)
    with pytest.raises(TypeError, match="slices"):
        g[0]
    with pytest.raises(ValueError, match="step"):
        g[::2]


def test_clear_invalidates_groups(ctx):
    batch = make_batch(ctx)
    g = batch.spawn(5)
    batch.clear()
    with pytest.raises(RuntimeError, match="removido"):
        g.x
    with pytest.raises(RuntimeError, match="removido"):
        g.x = 1.0
    with pytest.raises(RuntimeError, match="removido"):
        len(g)
    with pytest.raises(RuntimeError, match="removido"):
        g[0:1]


def test_shapebatch_clear_invalidates_groups(ctx):
    from fastobjects.shapes import ShapeBatch

    batch = ShapeBatch(capacity=10, ctx=ctx, view_size=(64, 64))
    g = batch.rects(3)
    batch.clear()
    with pytest.raises(RuntimeError, match="removido"):
        g.color


def test_subgroup_is_registered_and_invalidated_by_clear(ctx):
    batch = make_batch(ctx)
    g = batch.spawn(10)
    sub = g[2:5]
    batch.clear()
    with pytest.raises(RuntimeError, match="removido"):
        sub.y


def test_new_groups_after_clear_work(ctx):
    batch = make_batch(ctx)
    batch.spawn(5)
    batch.clear()
    fresh = batch.spawn(3, x=9.0)
    np.testing.assert_allclose(fresh.x, 9.0)
