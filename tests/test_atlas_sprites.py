import moderngl
import numpy as np
import pytest
from PIL import Image

from fastobjects.batch import SpriteBatch


@pytest.fixture(scope="module")
def gl():
    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.BLEND)
    fbo = ctx.framebuffer(color_attachments=[ctx.texture((64, 64), 4)])
    fbo.use()
    yield ctx, fbo
    ctx.release()


def read(fbo):
    raw = np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(64, 64, 4)
    return raw[::-1]


def make_pngs(tmp_path):
    red = tmp_path / "red.png"
    green = tmp_path / "green.png"
    Image.new("RGBA", (16, 16), (255, 0, 0, 255)).save(red)
    Image.new("RGBA", (16, 16), (0, 255, 0, 255)).save(green)
    return str(red), str(green)


def test_each_image_renders_its_own_pixels(gl, tmp_path):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    red, green = make_pngs(tmp_path)
    batch = SpriteBatch([red, green], capacity=10, ctx=ctx, view_size=(64, 64))
    batch.spawn(1, x=16.0, y=32.0, image=0)  # vermelho à esquerda
    batch.spawn(1, x=48.0, y=32.0, image=1)  # verde à direita
    batch.draw()
    px = read(fbo)
    assert px[32, 16][0] > 200 and px[32, 16][1] < 60  # vermelho
    assert px[32, 48][1] > 200 and px[32, 48][0] < 60  # verde


def test_group_image_retextures(gl, tmp_path):
    ctx, fbo = gl
    red, green = make_pngs(tmp_path)
    batch = SpriteBatch([red, green], capacity=10, ctx=ctx, view_size=(64, 64))
    g = batch.spawn(1, x=32.0, y=32.0, image=0)
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    batch.draw()
    assert read(fbo)[32, 32][0] > 200  # vermelho
    g.image = 1
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    batch.draw()
    assert read(fbo)[32, 32][1] > 200  # agora verde


def test_vectorized_image_array(gl, tmp_path):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    red, green = make_pngs(tmp_path)
    batch = SpriteBatch([red, green], capacity=10, ctx=ctx, view_size=(64, 64))
    batch.spawn(
        2, x=np.array([16.0, 48.0], dtype="f4"), y=32.0, image=np.array([0, 1])
    )
    batch.draw()
    px = read(fbo)
    assert px[32, 16][0] > 200  # imagem 0 = vermelho
    assert px[32, 48][1] > 200  # imagem 1 = verde


def test_named_images(gl, tmp_path):
    ctx, _ = gl
    red, green = make_pngs(tmp_path)
    batch = SpriteBatch(
        {"vermelho": red, "verde": green}, capacity=10, ctx=ctx, view_size=(64, 64)
    )
    g = batch.spawn(1, x=32.0, y=32.0, image="verde")
    np.testing.assert_allclose(g.size[0], [16.0, 16.0])
    with pytest.raises(ValueError, match="azul"):
        batch.spawn(1, image="azul")


def test_default_size_is_selected_image_size(gl, tmp_path):
    ctx, _ = gl
    red, _green = make_pngs(tmp_path)
    Image.new("RGBA", (10, 40), (0, 0, 255, 255)).save(tmp_path / "tall.png")
    batch = SpriteBatch(
        [red, str(tmp_path / "tall.png")], capacity=10, ctx=ctx, view_size=(64, 64)
    )
    g = batch.spawn(1, image=1)
    np.testing.assert_allclose(g.size[0], [10.0, 40.0])


def test_image_index_out_of_range_raises(gl, tmp_path):
    ctx, _ = gl
    red, green = make_pngs(tmp_path)
    batch = SpriteBatch([red, green], capacity=10, ctx=ctx, view_size=(64, 64))
    with pytest.raises(ValueError, match="0..1"):
        batch.spawn(1, image=5)


def test_image_on_shapebatch_raises(gl):
    from fastobjects.shapes import ShapeBatch

    ctx, _ = gl
    batch = ShapeBatch(capacity=10, ctx=ctx, view_size=(64, 64))
    g = batch.rects(1)
    with pytest.raises(AttributeError, match="imagem"):
        g.image = 0
