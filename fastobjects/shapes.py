"""ShapeBatch: primitivas 2D instanciadas — forma resolvida no fragment shader."""

from __future__ import annotations

import moderngl
import numpy as np

from fastobjects.core.shaders import SHAPE_FS, SHAPE_VS

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
