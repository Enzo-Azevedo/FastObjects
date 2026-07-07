"""ShapeBatch: primitivas 2D instanciadas — forma resolvida no fragment shader."""

from __future__ import annotations

import moderngl
import numpy as np

from fastobjects import _context
from fastobjects._batchcore import BatchCore
from fastobjects.core.renderer import COLUMN_ATTRS, COLUMN_BYTES, COLUMN_FORMATS
from fastobjects.core.shaders import SHAPE_FS, SHAPE_VS
from fastobjects.group import SpriteGroup

KIND_RECT = 0.0
KIND_CIRCLE = 1.0


class _ShapeRenderer:
    """Desenha até `capacity` formas com um único draw call instanciado.

    Um VBO por atributo (SoA): `pos` sobe em todo render; as demais colunas,
    apenas quando presentes em `dirty`.

    Args:
        ctx: contexto moderngl ativo.
        capacity: número máximo de instâncias.
        view_size: (largura, altura) do alvo de render, em pixels.
    """

    COLUMNS = ("pos", "size", "rot", "color", "kind")

    def __init__(
        self,
        ctx: moderngl.Context,
        capacity: int,
        view_size: tuple[int, int],
    ) -> None:
        self.ctx = ctx
        self.capacity = capacity
        self.uploads = 0  # total de buffer.write feitos (exposto para testes)
        self.prog = ctx.program(vertex_shader=SHAPE_VS, fragment_shader=SHAPE_FS)
        self.prog["u_view"].value = (2.0 / view_size[0], -2.0 / view_size[1])
        self.buffers = {
            name: ctx.buffer(reserve=capacity * COLUMN_BYTES[name])
            for name in self.COLUMNS
        }
        self.vao = ctx.vertex_array(
            self.prog,
            [
                (self.buffers[name], COLUMN_FORMATS[name], COLUMN_ATTRS[name])
                for name in self.COLUMNS
            ],
        )

    def _upload(self, cols: dict[str, np.ndarray], count: int, dirty: set[str]) -> None:
        for name in self.COLUMNS:
            self.buffers[name].write(cols[name][:count])
            self.uploads += 1

    def render(self, cols: dict[str, np.ndarray], count: int, dirty: set[str]) -> None:
        """Sobe `pos` (+ colunas sujas) e desenha `count` instâncias."""
        if count == 0:
            return
        self._upload(cols, count, dirty)
        self.vao.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=count)


class ShapeBatch(BatchCore):
    """Lote de primitivas 2D (retângulo, círculo, linha) em um draw call.

    O estado vive em colunas SoA (`pos`, `size`, `rot`, `color`, `kind`).
    Formas diferentes convivem no mesmo lote; os métodos retornam SpriteGroup
    com views que escrevem direto nas colunas.

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
        super().__init__(capacity, "formas", kind=True)
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
        cols = self._cols
        cols["pos"][s, 0] = x
        cols["pos"][s, 1] = y
        cols["size"][s, 0] = w
        cols["size"][s, 1] = h
        cols["rot"][s] = rot
        cols["color"][s] = color
        cols["kind"][s] = KIND_RECT
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
        cols = self._cols
        diameter = np.multiply(radius, 2.0, dtype="f4")
        cols["pos"][s, 0] = x
        cols["pos"][s, 1] = y
        cols["size"][s, 0] = diameter
        cols["size"][s, 1] = diameter
        cols["rot"][s] = 0.0
        cols["color"][s] = color
        cols["kind"][s] = KIND_CIRCLE
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
        cols = self._cols
        cols["pos"][s, 0] = (x1 + x2) * 0.5
        cols["pos"][s, 1] = (y1 + y2) * 0.5
        cols["size"][s, 0] = np.hypot(dx, dy)
        cols["size"][s, 1] = width
        cols["rot"][s] = np.arctan2(dy, dx)
        cols["color"][s] = color
        cols["kind"][s] = KIND_RECT
        return self._make_group(s)
