"""SpriteBatch: sprites como linhas de um array NumPy, nunca objetos Python."""

from __future__ import annotations

import moderngl
import numpy as np
from PIL import Image

from fastobjects.core.renderer import FLOATS_PER_SPRITE, SpriteRenderer
from fastobjects.errors import CapacityError


class SpriteBatch:
    """Lote de sprites com a mesma textura, desenhado em um draw call.

    O estado vive em `data` (capacity, 9): x, y, w, h, rot, r, g, b, a.
    As views `pos`, `size`, `rot`, `color` escrevem direto em `data`.

    Args:
        ctx: contexto moderngl ativo.
        texture_path: caminho de uma imagem (qualquer formato PIL).
        capacity: número máximo de sprites do lote.
        view_size: (largura, altura) do alvo de render em pixels.
    """

    def __init__(
        self,
        ctx: moderngl.Context,
        texture_path: str,
        capacity: int,
        view_size: tuple[int, int],
    ) -> None:
        img = Image.open(texture_path).convert("RGBA")
        texture = ctx.texture(img.size, 4, data=img.tobytes())
        self.texture_size = img.size
        self.capacity = capacity
        self.count = 0
        self.data = np.zeros((capacity, FLOATS_PER_SPRITE), dtype="f4")
        self.pos = self.data[:, 0:2]
        self.size = self.data[:, 2:4]
        self.rot = self.data[:, 4]
        self.color = self.data[:, 5:9]
        self._renderer = SpriteRenderer(ctx, texture, capacity, view_size)

    def spawn(
        self,
        n: int,
        x: float | np.ndarray = 0.0,
        y: float | np.ndarray = 0.0,
        w: float | np.ndarray | None = None,
        h: float | np.ndarray | None = None,
        rot: float | np.ndarray = 0.0,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    ) -> slice:
        """Adiciona n sprites. Aceita escalares ou arrays de tamanho n.

        Returns:
            O slice das linhas recém-criadas em `data`/views.

        Raises:
            CapacityError: se n não couber; a mensagem diz a capacity necessária.
        """
        if self.count + n > self.capacity:
            raise CapacityError(
                f"spawn({n}) excede a capacidade: {self.count} usados de "
                f"{self.capacity}. Crie o batch com capacity={self.count + n} ou mais."
            )
        s = slice(self.count, self.count + n)
        self.pos[s, 0] = x
        self.pos[s, 1] = y
        self.size[s, 0] = self.texture_size[0] if w is None else w
        self.size[s, 1] = self.texture_size[1] if h is None else h
        self.rot[s] = rot
        self.color[s] = color
        self.count += n
        return s

    def clear(self) -> None:
        """Remove todos os sprites (O(1): só reseta o contador)."""
        self.count = 0

    def draw(self) -> None:
        """Sobe o estado atual e desenha o lote inteiro em um draw call."""
        self._renderer.render(self.data, self.count)
