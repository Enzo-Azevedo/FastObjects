import moderngl
import numpy as np
import pytest

from fastobjects.core.renderer import SpriteRenderer


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
    return raw[::-1]  # OpenGL lê de baixo para cima; invertemos para y-baixo


def white_texture(ctx) -> moderngl.Texture:
    return ctx.texture((4, 4), 4, data=b"\xff" * (4 * 4 * 4))


def make_sprite_data(x, y, w, h, rot, color) -> np.ndarray:
    data = np.zeros((1, 9), dtype="f4")
    data[0] = [x, y, w, h, rot, *color]
    return data


def test_renders_red_sprite_at_center(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    renderer = SpriteRenderer(ctx, white_texture(ctx), capacity=16, view_size=(64, 64))
    data = make_sprite_data(32, 32, 16, 16, 0.0, (1.0, 0.0, 0.0, 1.0))
    renderer.render(data, 1)
    px = read_pixels(fbo)
    center = px[32, 32]
    assert center[0] > 200 and center[1] < 50 and center[2] < 50  # vermelho
    corner = px[2, 2]
    assert corner[0] < 10 and corner[1] < 10  # fundo intacto


def test_render_zero_count_is_noop(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    renderer = SpriteRenderer(ctx, white_texture(ctx), capacity=16, view_size=(64, 64))
    renderer.render(np.zeros((16, 9), dtype="f4"), 0)
    px = read_pixels(fbo)
    assert px[:, :, 0].max() < 10  # nada desenhado


def test_sprite_y_axis_points_down(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    renderer = SpriteRenderer(ctx, white_texture(ctx), capacity=16, view_size=(64, 64))
    data = make_sprite_data(32, 8, 10, 10, 0.0, (0.0, 1.0, 0.0, 1.0))  # y=8: perto do TOPO
    renderer.render(data, 1)
    px = read_pixels(fbo)
    assert px[8, 32][1] > 200   # verde no topo
    assert px[56, 32][1] < 10   # nada embaixo
