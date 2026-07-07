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


def test_despawn_compacts_and_frees_capacity(gl):
    ctx, _ = gl
    batch = make_batch(ctx, capacity=10)
    a = batch.spawn(6, x=1.0)
    batch.spawn(4, x=2.0)
    batch.despawn(a)
    assert batch.count == 4
    np.testing.assert_allclose(batch.pos[:4, 0], 2.0)  # sobrevivente compactado
    batch.spawn(6)  # capacity devolvida: não levanta


def test_despawn_preserves_neighbor_data_exactly(gl):
    ctx, _ = gl
    batch = make_batch(ctx)
    a = batch.spawn(3, x=np.array([1.0, 2.0, 3.0], dtype=np.float32))
    middle = batch.spawn(2, x=99.0)
    c = batch.spawn(3, x=np.array([7.0, 8.0, 9.0], dtype=np.float32))
    before_a = {name: arr[0:3].copy() for name, arr in batch._cols.items()}
    batch.despawn(middle)
    for name, arr in batch._cols.items():  # antes: intacto, coluna a coluna
        np.testing.assert_array_equal(arr[0:3], before_a[name])
    np.testing.assert_allclose(c.x, [7.0, 8.0, 9.0])  # depois: realocado, dados ok
    np.testing.assert_allclose(a.x, [1.0, 2.0, 3.0])


def test_despawn_shifts_later_groups(gl):
    ctx, _ = gl
    batch = make_batch(ctx)
    a = batch.spawn(5)
    b = batch.spawn(5, x=42.0)
    batch.despawn(a)
    assert b.slice == slice(0, 5)
    np.testing.assert_allclose(b.x, 42.0)


def test_despawn_subgroup_shrinks_parent(gl):
    ctx, _ = gl
    batch = make_batch(ctx)
    g = batch.spawn(10, x=np.arange(10, dtype=np.float32))
    sub = g[4:7]
    batch.despawn(sub)
    assert len(g) == 7
    np.testing.assert_allclose(g.x, [0, 1, 2, 3, 7, 8, 9])
    with pytest.raises(RuntimeError, match="removido"):
        sub.x


def test_despawn_invalidates_group_and_contained(gl):
    ctx, _ = gl
    batch = make_batch(ctx)
    g = batch.spawn(10)
    inner = g[2:5]
    batch.despawn(g)
    with pytest.raises(RuntimeError, match="removido"):
        g.x
    with pytest.raises(RuntimeError, match="removido"):
        inner.x


def test_despawn_twice_raises(gl):
    ctx, _ = gl
    batch = make_batch(ctx)
    g = batch.spawn(5)
    batch.despawn(g)
    with pytest.raises(RuntimeError, match="removido"):
        batch.despawn(g)


def test_despawn_foreign_group_raises(gl):
    ctx, _ = gl
    b1 = make_batch(ctx)
    b2 = make_batch(ctx)
    g = b1.spawn(3)
    with pytest.raises(ValueError, match="outro batch"):
        b2.despawn(g)


def test_despawn_empty_group_is_noop_but_invalidates(gl):
    ctx, _ = gl
    batch = make_batch(ctx)
    g = batch.spawn(0)
    other = batch.spawn(5, x=3.0)
    batch.despawn(g)
    assert batch.count == 5
    np.testing.assert_allclose(other.x, 3.0)
    with pytest.raises(RuntimeError, match="removido"):
        len(g)


def test_despawn_after_despawn_chain(gl):
    ctx, _ = gl
    batch = make_batch(ctx)
    a = batch.spawn(3, x=1.0)
    b = batch.spawn(3, x=2.0)
    c = batch.spawn(3, x=3.0)
    batch.despawn(b)
    batch.despawn(a)
    assert batch.count == 3
    assert c.slice == slice(0, 3)
    np.testing.assert_allclose(c.x, 3.0)


def test_despawn_invalidates_partially_overlapping_siblings(gl):
    ctx, _ = gl
    batch = make_batch(ctx)
    g = batch.spawn(10, x=np.arange(10, dtype=np.float32))
    a = g[3:6]
    b = g[4:7]  # irmão parcialmente sobreposto a `a`
    left = g[0:2]  # antes do trecho: continua válido
    batch.despawn(a)
    with pytest.raises(RuntimeError, match="removido"):
        b.x
    np.testing.assert_allclose(left.x, [0.0, 1.0])
    assert len(g) == 7  # pai encolheu normalmente


def test_shapebatch_despawn_works_the_same(gl):
    ctx, _ = gl
    batch = ShapeBatch(capacity=10, ctx=ctx, view_size=(64, 64))
    a = batch.rects(4, x=1.0)
    b = batch.circles(3, x=2.0)
    batch.despawn(a)
    assert batch.count == 3
    assert b.slice == slice(0, 3)
    np.testing.assert_allclose(b.x, 2.0)


def test_despawn_pixel_only_remaining_group_visible(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    batch = ShapeBatch(capacity=10, ctx=ctx, view_size=(64, 64))
    left = batch.rects(1, x=16.0, y=32.0, w=10.0, h=10.0, color=(1.0, 0.0, 0.0, 1.0))
    batch.rects(1, x=48.0, y=32.0, w=10.0, h=10.0, color=(0.0, 1.0, 0.0, 1.0))
    batch.despawn(left)
    batch.draw()
    raw = np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(64, 64, 4)[::-1]
    assert raw[32, 16][0] < 10  # vermelho removido não aparece
    assert raw[32, 48][1] > 200  # verde continua
