"""Empacotamento de imagens num texture atlas (shelf packing, sem GL)."""

from __future__ import annotations

import numpy as np
from PIL import Image

from fastobjects.errors import AtlasOverflowError


def _next_pow2(n: int) -> int:
    p = 1
    while p < n:
        p *= 2
    return p


class Atlas:
    """Empacota imagens numa única textura RGBA e produz as UVs de cada uma.

    Shelf packing (imagens ordenadas por altura desc, colocadas em prateleiras),
    com `padding` px de borda extrudada entre as sub-imagens para evitar bleeding
    sob filtragem linear. A textura é montada top-down (coerente com o renderer
    y-para-baixo).

    Args:
        images: imagens PIL (serão convertidas para RGBA).
        max_size: dimensão máxima da textura (GL_MAX_TEXTURE_SIZE).
        padding: px de borda extrudada em volta de cada imagem.

    Attributes:
        size: (largura, altura) da textura empacotada.
        pixels: bytes RGBA (top-down) para ctx.texture(size, 4, data=pixels).
        uvs: (n, 4) float32 — (u0, v0, u1, v1) por imagem de entrada.
        sizes: (n, 2) float32 — (w, h) em pixels por imagem.

    Raises:
        AtlasOverflowError: se as imagens não couberem em max_size.
    """

    def __init__(
        self, images: list[Image.Image], *, max_size: int, padding: int = 1
    ) -> None:
        rgba = [im.convert("RGBA") for im in images]
        self.sizes = np.array([im.size for im in rgba], dtype="f4")
        cells = [(im.size[0] + 2 * padding, im.size[1] + 2 * padding) for im in rgba]

        order = sorted(range(len(cells)), key=lambda i: cells[i][1], reverse=True)
        widest = max(cw for cw, _ in cells)
        total = sum(cw * ch for cw, ch in cells)
        atlas_w = min(max_size, _next_pow2(max(widest, int(total**0.5) + 1)))

        placements = [(0, 0)] * len(cells)
        x = y = shelf_h = 0
        for i in order:
            cw, ch = cells[i]
            if x + cw > atlas_w:
                x = 0
                y += shelf_h
                shelf_h = 0
            placements[i] = (x, y)
            x += cw
            shelf_h = max(shelf_h, ch)
        atlas_h = _next_pow2(y + shelf_h)

        if atlas_w > max_size or atlas_h > max_size:
            biggest = max(rgba, key=lambda im: im.size[0] * im.size[1]).size
            raise AtlasOverflowError(
                f"As imagens não cabem num atlas de {max_size}x{max_size} — a "
                f"maior é {biggest[0]}x{biggest[1]}. Reduza as imagens ou divida "
                "em vários batches (um SpriteBatch por atlas)."
            )

        atlas = np.zeros((atlas_h, atlas_w, 4), dtype="u1")
        uvs = np.zeros((len(cells), 4), dtype="f4")
        for i, im in enumerate(rgba):
            cx, cy = placements[i]
            w, h = im.size
            block = np.pad(
                np.asarray(im, dtype="u1"),
                ((padding, padding), (padding, padding), (0, 0)),
                mode="edge",
            )
            bh, bw = block.shape[:2]
            atlas[cy : cy + bh, cx : cx + bw] = block
            x0, y0 = cx + padding, cy + padding
            uvs[i] = [
                x0 / atlas_w,
                y0 / atlas_h,
                (x0 + w) / atlas_w,
                (y0 + h) / atlas_h,
            ]

        self.size = (atlas_w, atlas_h)
        self.pixels = atlas.tobytes()
        self.uvs = uvs
