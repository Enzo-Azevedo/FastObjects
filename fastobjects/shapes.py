"""ShapeBatch: primitivas 2D instanciadas — forma resolvida no fragment shader."""

from __future__ import annotations

import moderngl
import numpy as np

from fastobjects import _context
from fastobjects._batchcore import BatchCore
from fastobjects.core.shaders import SHAPE_FS, SHAPE_VS
from fastobjects.group import SpriteGroup

SHAPE_FLOATS = 10  # x, y, w, h, rot, r, g, b, a, kind
SHAPE_STRIDE = SHAPE_FLOATS * 4
KIND_RECT = 0.0
KIND_CIRCLE = 1.0


class _ShapeRenderer:
    """Desenha até `capacity` formas com um único draw call instanciado.

    Args:
        ctx: contexto moderngl ativo.
        capacity: número máximo de instâncias.
        view_size: (largura, altura) do alvo de render, em pixels.
    """

    def __init__(
        self,
        ctx: moderngl.Context,
        capacity: int,
        view_size: tuple[int, int],
    ) -> None:
        self.ctx = ctx
        self.capacity = capacity
        self.prog = ctx.program(vertex_shader=SHAPE_VS, fragment_shader=SHAPE_FS)
        self.prog["u_view"].value = (2.0 / view_size[0], -2.0 / view_size[1])
        self.buffer = ctx.buffer(reserve=capacity * SHAPE_STRIDE)
        self.vao = ctx.vertex_array(
            self.prog,
            [
                (
                    self.buffer,
                    "2f 2f 1f 4f 1f/i",
                    "in_pos",
                    "in_size",
                    "in_rot",
                    "in_color",
                    "in_kind",
                )
            ],
        )

    def render(self, data: np.ndarray, count: int) -> None:
        """Sobe `data[:count]` e desenha `count` instâncias (estratégia A do lab)."""
        if count == 0:
            return
        self.buffer.write(data[:count])
        self.vao.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=count)


class ShapeBatch(BatchCore):
    """Lote de primitivas 2D (retângulo, círculo, linha) em um draw call.

    O estado vive em `data` (capacity, 10): x, y, w, h, rot, r, g, b, a, kind.
    Formas diferentes convivem no mesmo lote; os métodos retornam SpriteGroup
    com views que escrevem direto no array.

    Args:
        capacity: número máximo de formas do lote.
        ctx: contexto moderngl; se None, usa o da janela atual.
        view_size: (largura, altura) do alvo de render em pixels;
            se None, usa o tamanho da janela atual.
    """

    def __init__(
        self,
        capacity: int,
        *,
        ctx: moderngl.Context | None = None,
        view_size: tuple[int, int] | None = None,
    ) -> None:
        super().__init__(capacity, SHAPE_FLOATS, "formas")
        ctx, view_size = _context.resolve(ctx, view_size)
        self._renderer = _ShapeRenderer(ctx, capacity, view_size)

    def rects(
        self,
        n: int,
        x: float | np.ndarray = 0.0,
        y: float | np.ndarray = 0.0,
        w: float | np.ndarray = 10.0,
        h: float | np.ndarray = 10.0,
        rot: float | np.ndarray = 0.0,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    ) -> SpriteGroup:
        """Adiciona n retângulos. Aceita escalares ou arrays de tamanho n."""
        s = self._alloc(n, "rects")
        d = self.data
        d[s, 0] = x
        d[s, 1] = y
        d[s, 2] = w
        d[s, 3] = h
        d[s, 4] = rot
        d[s, 5:9] = color
        d[s, 9] = KIND_RECT
        return self._make_group(s)

    def circles(
        self,
        n: int,
        x: float | np.ndarray = 0.0,
        y: float | np.ndarray = 0.0,
        radius: float | np.ndarray = 5.0,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    ) -> SpriteGroup:
        """Adiciona n círculos; o layout guarda o bounding box (w = h = 2*radius)."""
        s = self._alloc(n, "circles")
        d = self.data
        diameter = np.multiply(radius, 2.0, dtype="f4")
        d[s, 0] = x
        d[s, 1] = y
        d[s, 2] = diameter
        d[s, 3] = diameter
        d[s, 4] = 0.0
        d[s, 5:9] = color
        d[s, 9] = KIND_CIRCLE
        return self._make_group(s)

    def lines(
        self,
        n: int,
        x1: float | np.ndarray,
        y1: float | np.ndarray,
        x2: float | np.ndarray,
        y2: float | np.ndarray,
        width: float | np.ndarray = 1.0,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    ) -> SpriteGroup:
        """Adiciona n linhas como retângulos rotacionados (conversão vetorizada).

        O shader não conhece "linha": endpoints viram centro, comprimento e
        rotação de um retângulo com altura `width`.
        """
        s = self._alloc(n, "lines")
        x1 = np.asarray(x1, dtype="f4")
        y1 = np.asarray(y1, dtype="f4")
        x2 = np.asarray(x2, dtype="f4")
        y2 = np.asarray(y2, dtype="f4")
        dx = x2 - x1
        dy = y2 - y1
        d = self.data
        d[s, 0] = (x1 + x2) * 0.5
        d[s, 1] = (y1 + y2) * 0.5
        d[s, 2] = np.hypot(dx, dy)
        d[s, 3] = width
        d[s, 4] = np.arctan2(dy, dx)
        d[s, 5:9] = color
        d[s, 9] = KIND_RECT
        return self._make_group(s)
