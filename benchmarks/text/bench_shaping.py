"""Custo do shaping no layout: shaped vs simples vs Pillow+Raqm (publicado).

O draw não muda com shaping (mesmos quads/atlas) — o custo novo é todo no
layout/write. Pillow+Raqm é o código publicado equivalente para árabe correto
(rasteriza a string inteira por CPU a cada mudança); indisponível quando a
wheel do Pillow vem sem Raqm (caso do Windows).
"""

import time

from PIL import Image, ImageDraw, ImageFont, features

import fastobjects.shaping as shaping
from fastobjects.font import Font

FONT = "C:/Windows/Fonts/arial.ttf"
SIZE = 16
N = 2000
TEXTS = [f"سلام عليكم {i:04d}" for i in range(N)]


def rate(fn) -> float:
    fn()  # warmup
    t0 = time.perf_counter()
    fn()
    return N / (time.perf_counter() - t0)


f_shaped = Font(FONT, SIZE)
assert f_shaped.shaped, "extra shaping ausente"
print(
    f"layout shaped (HarfBuzz):  "
    f"{rate(lambda: [f_shaped.layout(t) for t in TEXTS]):,.0f} strings/s"
)

_orig = shaping.available
shaping.available = lambda: False
f_simple = Font(FONT, SIZE)
shaping.available = _orig
print(
    f"layout simples (0.6.1):    "
    f"{rate(lambda: [f_simple.layout(t) for t in TEXTS]):,.0f} strings/s"
    "  (árabe INCORRETO)"
)

if features.check("raqm"):
    pil = ImageFont.truetype(FONT, SIZE)

    def pil_render():
        for t in TEXTS:
            img = Image.new("L", (200, 24), 0)
            ImageDraw.Draw(img).text((0, 0), t, font=pil, fill=255)

    print(f"Pillow+Raqm (raster CPU):  {rate(pil_render):,.0f} strings/s")
else:
    print("Pillow sem Raqm — referência indisponível nesta máquina")
