"""Renderer instanciado: um VBO por atributo (SoA), um draw call por lote."""

from __future__ import annotations

import moderngl
import numpy as np

from fastobjects.core.shaders import SPRITE_FS, SPRITE_VS

# Layout SoA decidido por benchmark (Lab 2026-07-07, RESULTS.md): tudo f4;
# quantização de colunas frias foi medida e REJEITADA (conversão na CPU custa
# mais do que economiza de upload).
COLUMN_BYTES = {"pos": 8, "size": 8, "rot": 4, "color": 16, "kind": 4, "uv": 16}
COLUMN_FORMATS = {
    "pos": "2f/i",
    "size": "2f/i",
    "rot": "1f/i",
    "color": "4f/i",
    "kind": "1f/i",
    "uv": "4f/i",
}
COLUMN_ATTRS = {
    "pos": "in_pos",
    "size": "in_size",
    "rot": "in_rot",
    "color": "in_color",
    "kind": "in_kind",
    "uv": "in_uv",
}


class SpriteRenderer:
    """Desenha até `capacity` sprites com um único draw call instanciado.

    Um VBO por atributo: `pos` sobe em todo render; as demais colunas, apenas
    quando presentes em `dirty` — o chamador (BatchCore.draw) controla e limpa
    o conjunto.

    Args:
        ctx: contexto moderngl ativo.
        texture: textura compartilhada por todos os sprites do lote.
        capacity: número máximo de instâncias.
        view_size: (largura, altura) do alvo de render, em pixels.
    """

    COLUMNS = ("pos", "size", "rot", "color", "uv")

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
        self.uploads = 0  # total de buffer.write feitos (exposto para testes)
        self.prog = ctx.program(vertex_shader=SPRITE_VS, fragment_shader=SPRITE_FS)
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
            if name != "pos" and name not in dirty:
                continue  # coluna fria não tocada: a GPU já tem o valor
            self.buffers[name].write(cols[name][:count])
            self.uploads += 1

    def render(self, cols: dict[str, np.ndarray], count: int, dirty: set[str]) -> None:
        """Sobe `pos` (+ colunas sujas) e desenha `count` instâncias."""
        if count == 0:
            return
        self.texture.use(0)
        self._upload(cols, count, dirty)
        self.vao.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=count)
