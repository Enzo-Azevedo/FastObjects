"""SpriteBatch: sprites como colunas de arrays NumPy, nunca objetos Python."""

from __future__ import annotations

from pathlib import Path

import moderngl
import numpy as np
from PIL import Image

from fastobjects import _context
from fastobjects._batchcore import BatchCore
from fastobjects.core.renderer import SpriteRenderer
from fastobjects.group import SpriteGroup


class SpriteBatch(BatchCore):
    """Lote de sprites com a mesma textura, desenhado em um draw call.

    O estado vive em colunas SoA (`pos`, `size`, `rot`, `color` — todas f4);
    as views escrevem direto nas colunas. Por frame, o draw sobe as posições
    sempre e as demais colunas só quando tocadas (ver BatchCore).

    Args:
        texture_path: caminho de uma imagem (qualquer formato PIL).
        capacity: número máximo de sprites do lote.
        ctx: contexto moderngl; se None, usa o da janela atual.
        view_size: (largura, altura) do alvo de render em pixels;
            se None, usa o tamanho da janela atual.
    """

    def __init__(
        self,
        texture_path: str,
        capacity: int,
        *,
        ctx: moderngl.Context | None = None,
        view_size: tuple[int, int] | None = None,
    ) -> None:
        super().__init__(capacity, "sprites")
        ctx, view_size = _context.resolve(ctx, view_size)
        path = Path(texture_path)
        if not path.is_file():
            raise FileNotFoundError(
                f"Textura não encontrada: {path.resolve()} — verifique o caminho "
                "(relativo ao diretório de execução) ou use um caminho absoluto."
            )
        img = Image.open(path).convert("RGBA")
        texture = ctx.texture(img.size, 4, data=img.tobytes())
        self.texture_size = img.size
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
    ) -> SpriteGroup:
        """Adiciona n sprites. Aceita escalares ou arrays de tamanho n.

        Returns:
            SpriteGroup das linhas recém-criadas (views escrevem no batch).

        Raises:
            ValueError: se n for negativo.
            CapacityError: se n não couber; a mensagem diz a capacity necessária.
        """
        s = self._alloc(n, "spawn")
        cols = self._cols
        cols["pos"][s, 0] = x
        cols["pos"][s, 1] = y
        cols["size"][s, 0] = self.texture_size[0] if w is None else w
        cols["size"][s, 1] = self.texture_size[1] if h is None else h
        cols["rot"][s] = rot
        cols["color"][s] = color
        return self._make_group(s)
