import moderngl
import numpy as np
import pytest

pygame = pytest.importorskip("pygame")

from fastobjects.layer import SurfaceLayer  # noqa: E402


@pytest.fixture(scope="module")
def gl():
    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.BLEND)
    fbo = ctx.framebuffer(color_attachments=[ctx.texture((64, 64), 4)])
    fbo.use()
    yield ctx, fbo
    ctx.release()


def read_pixels(fbo) -> np.ndarray:
    raw = np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(64, 64, 4)
    return raw[::-1]


def test_surface_layer_composites_pygame_drawing(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    surf = pygame.Surface((64, 64), pygame.SRCALPHA)
    pygame.draw.rect(surf, (255, 0, 0, 255), pygame.Rect(10, 10, 20, 20))
    layer = SurfaceLayer(surf, ctx=ctx, view_size=(64, 64))
    layer.update()
    layer.draw()
    px = read_pixels(fbo)
    assert px[15, 15][0] > 200  # dentro do retângulo (pygame top-down == y-baixo)
    assert px[50, 50][0] < 10  # área transparente: fundo intacto


def test_surface_layer_update_reflects_new_drawing(gl):
    ctx, fbo = gl
    surf = pygame.Surface((64, 64), pygame.SRCALPHA)
    layer = SurfaceLayer(surf, ctx=ctx, view_size=(64, 64))
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    layer.update()
    layer.draw()
    assert read_pixels(fbo)[32, 32][1] < 10  # ainda vazio
    pygame.draw.circle(surf, (0, 255, 0, 255), (32, 32), 8)
    layer.update()
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    layer.draw()
    assert read_pixels(fbo)[32, 32][1] > 200  # círculo apareceu


def test_zero_size_surface_raises(gl):
    ctx, _ = gl
    surf = pygame.Surface((0, 0), pygame.SRCALPHA)
    with pytest.raises(ValueError, match="tamanho inválido"):
        SurfaceLayer(surf, ctx=ctx, view_size=(64, 64))


def test_surface_layer_size_change_raises(gl):
    ctx, _ = gl
    surf = pygame.Surface((32, 32), pygame.SRCALPHA)
    layer = SurfaceLayer(surf, ctx=ctx, view_size=(64, 64))
    layer._surface = pygame.Surface((16, 16), pygame.SRCALPHA)  # troca indevida
    with pytest.raises(ValueError, match="tamanho"):
        layer.update()
