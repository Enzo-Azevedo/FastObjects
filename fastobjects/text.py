"""TextBatch: desenha texto como sprites de um atlas de glifos (um draw call)."""

from __future__ import annotations

import moderngl

from fastobjects import _context
from fastobjects._batchcore import BatchCore
from fastobjects.core.renderer import SpriteRenderer
from fastobjects.font import Font
from fastobjects.group import SpriteGroup


class TextBatch(BatchCore):
    """Lote de texto de uma fonte, desenhado em um draw call.

    Cada glifo é um quad texturizado do atlas de glifos da fonte. Vários
    `write` acumulam e saem em um único draw call; para texto que muda por
    frame (score/FPS), chame `clear()` e `write()` de novo.

    Args:
        font: a Font cujos glifos serão desenhados.
        capacity: número máximo de glifos (somando todos os writes vivos).
        ctx: contexto moderngl; se None, usa o da janela atual.
        view_size: (largura, altura) do alvo de render; se None, usa a janela.
    """

    def __init__(
        self,
        font: Font,
        capacity: int,
        *,
        ctx: moderngl.Context | None = None,
        view_size: tuple[int, int] | None = None,
    ) -> None:
        super().__init__(capacity, "glifos", uv=True)
        ctx, view_size = _context.resolve(ctx, view_size)
        self.font = font
        texture = ctx.texture(font.atlas_size, 4, data=font.atlas_pixels)
        self._renderer = SpriteRenderer(ctx, texture, capacity, view_size)

    def write(
        self,
        text: str,
        x: float,
        y: float,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
        anchor: str = "topleft",
    ) -> SpriteGroup:
        """Escreve `text` em (x, y). anchor: "topleft" (padrão) ou "center".

        Returns:
            SpriteGroup sobre os quads dos glifos (mova/recolora o texto todo).

        Raises:
            ValueError: se anchor for inválido.
            CapacityError: se os glifos não couberem no capacity restante.
        """
        if anchor not in ("topleft", "center"):
            raise ValueError(f"anchor={anchor!r} inválido: use 'topleft' ou 'center'.")
        centers, sizes, uvs, (bw, bh) = self.font.layout(text)
        n = centers.shape[0]
        dx, dy = (x, y) if anchor == "topleft" else (x - bw / 2.0, y - bh / 2.0)
        s = self._alloc(n, "write")
        cols = self._cols
        cols["pos"][s, 0] = centers[:, 0] + dx
        cols["pos"][s, 1] = centers[:, 1] + dy
        cols["size"][s] = sizes
        cols["rot"][s] = 0.0
        cols["color"][s] = color
        cols["uv"][s] = uvs
        return self._make_group(s)
