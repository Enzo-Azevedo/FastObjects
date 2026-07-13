"""Backend de shaping (HarfBuzz + FreeType): RTL, kerning, ligaturas.

Opcional: `pip install fastobjects[shaping]`. Sem os pacotes o Font cai no
layout simples da 0.6.1 (fallback silencioso — veja Font.shaped). O atlas
contém TODOS os glifos da fonte (ligaturas e formas contextuais produzem
glyph-IDs sem caractere correspondente); linha mista LTR+RTL usa a direção
dominante detectada pelo HarfBuzz (bidi completo é limite documentado).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from fastobjects.atlas import Atlas
from fastobjects.font import _ATLAS_MAX, Glyph


def available() -> bool:
    """True se uharfbuzz e freetype-py estão instalados."""
    try:
        import freetype  # noqa: F401
        import uharfbuzz  # noqa: F401
    except ImportError:
        return False
    return True


class ShapedBackend:
    """Rasteriza a fonte inteira por glyph-ID e shapeia linhas com HarfBuzz."""

    def __init__(self, source: str, size: int) -> None:
        import freetype
        import uharfbuzz as hb

        self._hb_mod = hb
        try:
            self._ft = freetype.Face(source)
        except freetype.ft_errors.FT_Exception as e:
            raise OSError(f"FreeType não abriu {source!r}: {e}") from e
        self._ft.set_pixel_sizes(0, size)
        self._ascender = self._ft.size.ascender / 64.0
        self.line_height = (self._ft.size.ascender - self._ft.size.descender) / 64.0

        self._hb = hb.Font(hb.Face(hb.Blob(Path(source).read_bytes())))
        self._hb.scale = (size * 64, size * 64)

        imgs: list[Image.Image] = []
        ids: list[int] = []
        meta: dict[int, tuple] = {}
        for gid in range(self._ft.num_glyphs):
            self._ft.load_glyph(gid, freetype.FT_LOAD_RENDER)
            g = self._ft.glyph
            bmp = g.bitmap
            w, h = bmp.width, bmp.rows
            meta[gid] = (
                (float(w), float(h)),
                float(g.advance.x) / 64.0,
                (float(g.bitmap_left), self._ascender - float(g.bitmap_top)),
            )
            if w > 0 and h > 0:
                cov = np.frombuffer(bytes(bmp.buffer), dtype="u1").reshape(
                    h, bmp.pitch
                )[:, :w]
                rgba = np.zeros((h, w, 4), dtype="u1")
                rgba[..., 0:3] = 255
                rgba[..., 3] = cov
                imgs.append(Image.fromarray(rgba))
                ids.append(gid)

        atlas = Atlas(imgs, max_size=_ATLAS_MAX, padding=1)
        self.atlas_pixels = atlas.pixels
        self.atlas_size = atlas.size
        self.glyphs: dict[int, Glyph] = {}
        for gid, (sz, adv, off) in meta.items():
            self.glyphs[gid] = Glyph(None, sz, adv, off)
        for i, gid in enumerate(ids):
            sz, adv, off = meta[gid]
            self.glyphs[gid] = Glyph(atlas.uvs[i].copy(), sz, adv, off)

    def char_index(self, ch: str) -> int:
        """Glyph-ID do caractere na cmap da fonte (0 = não coberto)."""
        return self._ft.get_char_index(ch)

    def shape_line(self, line: str) -> list[tuple[int, float, float, float]]:
        """Shapeia uma linha: [(gid, x_advance, x_offset, y_offset)] em px,
        na ordem visual (RTL já sai invertido, pronto para pen esquerda→direita).
        """
        hb = self._hb_mod
        buf = hb.Buffer()
        buf.add_str(line)
        buf.guess_segment_properties()
        hb.shape(self._hb, buf)
        return [
            (
                info.codepoint,
                pos.x_advance / 64.0,
                pos.x_offset / 64.0,
                pos.y_offset / 64.0,
            )
            for info, pos in zip(buf.glyph_infos, buf.glyph_positions)
        ]

    def layout(self, text: str):
        """Mesmo contrato do Font.layout: (centers, sizes, uvs, block)."""
        centers, sizes, uvs = [], [], []
        pen_y, max_w, n_lines = 0.0, 0.0, 0
        for line in text.split("\n"):
            n_lines += 1
            pen_x = 0.0
            for gid, adv, xoff, yoff in self.shape_line(line):
                g = self.glyphs.get(gid)
                if g is not None and g.uv is not None:
                    w, h = g.size
                    ox, oy = g.offset
                    centers.append(
                        (pen_x + xoff + ox + w / 2.0, pen_y - yoff + oy + h / 2.0)
                    )
                    sizes.append((w, h))
                    uvs.append(g.uv)
                pen_x += adv
            max_w = max(max_w, pen_x)
            pen_y += self.line_height
        n = len(centers)
        return (
            np.array(centers, dtype="f4").reshape(n, 2),
            np.array(sizes, dtype="f4").reshape(n, 2),
            np.array(uvs, dtype="f4").reshape(n, 4),
            (max_w, n_lines * self.line_height),
        )
