"""Font: rasteriza um charset num atlas de glifos (Pillow), sem OpenGL."""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
from PIL import Image, ImageFont

from fastobjects.atlas import Atlas

# ASCII imprimível (0x20-0x7E) + Latin-1 imprimível (0xA1-0xFF): cobre acentos.
_DEFAULT_CHARS = "".join(chr(c) for c in range(0x20, 0x7F)) + "".join(
    chr(c) for c in range(0xA1, 0x100)
)
_ATLAS_MAX = 8192  # seguro em qualquer GPU desktop GL 3.3 real


class Glyph(NamedTuple):
    uv: np.ndarray | None  # (4,) f4 (u0,v0,u1,v1) ou None se sem bitmap (espaço)
    size: tuple[float, float]  # (w, h) em px
    advance: float  # avanço do pen
    offset: tuple[float, float]  # (l, t) bearing do canto superior-esquerdo


class Font:
    """Atlas de glifos de uma fonte embutida do Pillow (escalável).

    Args:
        size: altura da fonte em px.
        chars: caracteres a incluir; None usa ASCII imprimível + Latin-1
            (acentos). Um caractere fora do conjunto é pulado no layout.

    Attributes:
        atlas_pixels: bytes RGBA (top-down) do atlas de glifos.
        atlas_size: (largura, altura) do atlas.
        line_height: altura de uma linha (ascent + descent), em px.
        size: a altura pedida.
        glyphs: dict char -> Glyph.
    """

    def __init__(self, size: int = 24, *, chars: str | None = None) -> None:
        chars = _DEFAULT_CHARS if chars is None else chars
        if not chars:
            raise ValueError("chars não pode ser vazio — passe ao menos um caractere.")
        font = ImageFont.load_default(size=size)
        self.size = size
        self.line_height = float(sum(font.getmetrics()))  # ascent + descent

        imgs: list[Image.Image] = []
        img_chars: list[str] = []
        meta: dict[str, tuple[tuple[float, float], float, tuple[float, float]]] = {}
        for ch in dict.fromkeys(chars):  # únicos, ordem estável
            mask = font.getmask(ch)
            w, h = mask.size
            adv = float(font.getlength(ch))
            left, top = font.getbbox(ch)[:2]
            meta[ch] = ((float(w), float(h)), adv, (float(left), float(top)))
            if w > 0 and h > 0:
                cov = np.array(mask, dtype="u1").reshape(h, w)
                rgba = np.zeros((h, w, 4), dtype="u1")
                rgba[..., 0:3] = 255
                rgba[..., 3] = cov
                imgs.append(Image.fromarray(rgba))  # (h,w,4) u8 => RGBA
                img_chars.append(ch)

        atlas = Atlas(imgs, max_size=_ATLAS_MAX, padding=1)
        self.atlas_pixels = atlas.pixels
        self.atlas_size = atlas.size

        self.glyphs: dict[str, Glyph] = {}
        for ch, (sz, adv, off) in meta.items():
            self.glyphs[ch] = Glyph(None, sz, adv, off)
        for i, ch in enumerate(img_chars):
            sz, adv, off = meta[ch]
            self.glyphs[ch] = Glyph(atlas.uvs[i].copy(), sz, adv, off)

    def layout(self, text: str):
        """Posiciona os glifos de `text` a partir de (0,0) topo-esquerda.

        Returns:
            (centers (n,2) f4, sizes (n,2) f4, uvs (n,4) f4, block (w,h)) —
            centros dos quads (sprites são center-based), tamanhos, UVs e o
            tamanho do bloco de texto. n = número de glifos com bitmap.
        """
        space = self.glyphs.get(" ")
        space_adv = space.advance if space else self.size * 0.5
        centers, sizes, uvs = [], [], []
        pen_x, pen_y = 0.0, 0.0
        max_w, n_lines = 0.0, 1
        for ch in text:
            if ch == "\n":
                max_w = max(max_w, pen_x)
                pen_x, pen_y = 0.0, pen_y + self.line_height
                n_lines += 1
                continue
            g = self.glyphs.get(ch)
            if g is None:
                pen_x += space_adv
                continue
            if g.uv is not None:
                w, h = g.size
                ox, oy = g.offset
                centers.append((pen_x + ox + w / 2.0, pen_y + oy + h / 2.0))
                sizes.append((w, h))
                uvs.append(g.uv)
            pen_x += g.advance
        max_w = max(max_w, pen_x)
        n = len(centers)
        return (
            np.array(centers, dtype="f4").reshape(n, 2),
            np.array(sizes, dtype="f4").reshape(n, 2),
            np.array(uvs, dtype="f4").reshape(n, 4),
            (max_w, n_lines * self.line_height),
        )

    def measure(self, text: str) -> tuple[float, float]:
        """Tamanho (largura, altura) do bloco de `text`, sem desenhar."""
        return self.layout(text)[3]
