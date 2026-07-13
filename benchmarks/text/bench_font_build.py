"""Load-time: rasterizar o charset latin — fastobjects.Font(ttf) vs freetype-py puro.

Nota de justiça: o lado freetype-py SÓ rasteriza (sem montar atlas); o Font
rasteriza E empacota o atlas — o freetype-py puro faz menos trabalho.
"""

import time

import freetype

from fastobjects.font import _CHARSETS, Font

FONT = "C:/Windows/Fonts/arial.ttf"
SIZE = 16
N = 20


def timeit(fn) -> float:
    fn()  # warmup
    t0 = time.perf_counter()
    for _ in range(N):
        fn()
    return (time.perf_counter() - t0) / N * 1000.0


def build_fastobjects() -> None:
    Font(FONT, SIZE)


def build_freetype() -> None:
    face = freetype.Face(FONT)
    face.set_pixel_sizes(0, SIZE)
    for ch in _CHARSETS["latin"]:
        face.load_char(ch)
        bmp = face.glyph.bitmap
        bytes(bmp.buffer)


print(f"fastobjects Font(ttf) [rasteriza+atlas]: {timeit(build_fastobjects):.2f} ms")
print(f"freetype-py puro [só rasteriza]:        {timeit(build_freetype):.2f} ms")
