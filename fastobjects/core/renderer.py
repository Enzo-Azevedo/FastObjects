"""Renderer instanciado: um buffer de instâncias, um draw call por lote."""

from __future__ import annotations

import moderngl
import numpy as np

from fastobjects.core.shaders import SPRITE_FS, SPRITE_VS

FLOATS_PER_SPRITE = 9  # x, y, w, h, rot, r, g, b, a
STRIDE = FLOATS_PER_SPRITE * 4


class SpriteRenderer:
    """Desenha até `capacity` sprites com um único draw call instanciado.

    Args:
        ctx: contexto moderngl ativo.
        texture: textura compartilhada por todos os sprites do lote.
        capacity: número máximo de instâncias.
        view_size: (largura, altura) do alvo de render, em pixels.
    """

    def __init__(
        self,
        ctx: moderngl.Context,
        texture: moderngl.Texture,
        capacity: int,
        view_size: tuple[int, int],
    ) -> None:
        self.ctx = ctx
        self.texture = texture
        self.capacity = capacity
        self.prog = ctx.program(vertex_shader=SPRITE_VS, fragment_shader=SPRITE_FS)
        self.prog["u_view"].value = (2.0 / view_size[0], -2.0 / view_size[1])
        self.buffer = ctx.buffer(reserve=capacity * STRIDE)
        self.vao = ctx.vertex_array(
            self.prog,
            [(self.buffer, "2f 2f 1f 4f/i", "in_pos", "in_size", "in_rot", "in_color")],
        )

    def render(self, data: np.ndarray, count: int) -> None:
        """Sobe `data[:count]` e desenha `count` instâncias.

        Estratégia de upload: write total do trecho usado (hipótese H1 do
        RESEARCH.md; alternativas medidas no lab — ver benchmarks/RESULTS.md).
        """
        if count == 0:
            return
        self.texture.use(0)
        self.buffer.write(data[:count])
        self.vao.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=count)
