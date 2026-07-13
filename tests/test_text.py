from pathlib import Path

import moderngl
import numpy as np
import pytest

from fastobjects.font import Font
from fastobjects.text import TextBatch


@pytest.fixture(scope="module")
def gl():
    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.BLEND)
    fbo = ctx.framebuffer(color_attachments=[ctx.texture((128, 64), 4)])
    fbo.use()
    yield ctx, fbo
    ctx.release()


def read(fbo):
    raw = np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(64, 128, 4)
    return raw[::-1]


def test_write_paints_glyph_pixels(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    font = Font(size=32)
    txt = TextBatch(font, capacity=100, ctx=ctx, view_size=(128, 64))
    txt.write("I", x=20.0, y=10.0, color=(1.0, 1.0, 1.0, 1.0))
    txt.draw()
    px = read(fbo)
    assert px[:, :, :3].max() > 200  # o glifo apareceu
    assert px[:, 100:, :3].max() < 20  # nada à direita (texto está à esquerda)


def test_write_color(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    font = Font(size=32)
    txt = TextBatch(font, capacity=100, ctx=ctx, view_size=(128, 64))
    txt.write("H", x=20.0, y=10.0, color=(1.0, 0.0, 0.0, 1.0))
    txt.draw()
    px = read(fbo)
    lit = px[px[:, :, :3].sum(axis=2) > 200]
    assert lit[:, 0].mean() > 150 and lit[:, 1].mean() < 80  # vermelho


def test_newline_goes_down(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    font = Font(size=20)
    txt = TextBatch(font, capacity=100, ctx=ctx, view_size=(128, 64))
    txt.write("A\nA", x=10.0, y=2.0)
    txt.draw()
    px = read(fbo)
    rows = np.where(px[:, :, :3].max(axis=(1, 2)) > 150)[0]
    assert rows.max() - rows.min() > 20  # duas linhas separadas em y


def test_anchor_center(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    font = Font(size=24)
    txt = TextBatch(font, capacity=100, ctx=ctx, view_size=(128, 64))
    txt.write("Hi", x=64.0, y=32.0, anchor="center")
    txt.draw()
    px = read(fbo)
    cols = np.where(px[:, :, :3].max(axis=(0, 2)) > 150)[0]
    assert abs((cols.min() + cols.max()) / 2 - 64) < 20  # centrado em x=64


def test_spaces_and_unknown_do_not_crash(gl):
    ctx, _ = gl
    font = Font(size=20, chars="AB")
    txt = TextBatch(font, capacity=100, ctx=ctx, view_size=(128, 64))
    g = txt.write("A ?B", x=0.0, y=0.0)  # espaço + '?' fora do charset
    assert len(g) == 2  # só A e B


def test_write_returns_movable_group(gl):
    ctx, _ = gl
    font = Font(size=20)
    txt = TextBatch(font, capacity=100, ctx=ctx, view_size=(128, 64))
    g = txt.write("Hi", x=10.0, y=10.0)
    y0 = g.y.copy()
    g.pos += (0.0, 5.0)
    np.testing.assert_allclose(g.y, y0 + 5.0)


def test_invalid_anchor_raises(gl):
    ctx, _ = gl
    font = Font(size=20)
    txt = TextBatch(font, capacity=100, ctx=ctx, view_size=(128, 64))
    with pytest.raises(ValueError, match="anchor"):
        txt.write("x", 0.0, 0.0, anchor="middle")


@pytest.mark.skipif(
    not Path("C:/Windows/Fonts/arial.ttf").exists(), reason="arial.ttf ausente"
)
def test_ttf_text_draws(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    font = Font("C:/Windows/Fonts/arial.ttf", 32)
    txt = TextBatch(font, capacity=100, ctx=ctx, view_size=(128, 64))
    txt.write("I", x=20.0, y=10.0)
    txt.draw()
    px = read(fbo)
    assert px[:, :, :3].max() > 200


@pytest.mark.skipif(
    not Path("C:/Windows/Fonts/arial.ttf").exists(), reason="arial.ttf ausente"
)
def test_arabic_text_draws_pixels(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    font = Font("C:/Windows/Fonts/arial.ttf", 24)
    txt = TextBatch(font, capacity=100, ctx=ctx, view_size=(128, 64))
    txt.write("سلام", x=10.0, y=10.0)
    txt.draw()
    px = read(fbo)
    assert px[:, :, :3].max() > 200  # árabe renderiza (shaped ou fallback)


def test_exports():
    import fastobjects as fo

    assert fo.Font is not None and fo.TextBatch is not None
