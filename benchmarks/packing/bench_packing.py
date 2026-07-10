"""Benchmark de velocidade de PACKING de atlas: FastObjects vs PyTexturePacker.

Comparação justa (Python vs Python): ambos carregam N imagens, empacotam num
atlas e montam a imagem final — em memória (sem escrita em disco). Também
reporta o end-to-end de cada um (o PyTexturePacker escreve arquivos no fluxo
`pack()`; o FastObjects entrega bytes na memória).

Rode: python benchmarks/packing/bench_packing.py [--n 800] [--size 64] [--runs 5]
"""

from __future__ import annotations

import argparse
import glob
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw

from fastobjects.atlas import Atlas

MAX = 4096  # tamanho máximo de atlas usado pelos DOIS (condição igual)
PAD = 2


def gen_images(folder: Path, n: int, size: int) -> list[str]:
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        ImageDraw.Draw(img).rectangle(
            [10, 10, size - 10, size - 10], fill=(i % 255, 100, 200, 255)
        )
        img.save(folder / f"sprite_{i:04d}.png")
    return sorted(glob.glob(str(folder / "*.png")))


def bench(fn, runs: int) -> tuple[float, float]:
    ts = []
    for _ in range(runs):
        t = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t)
    return min(ts) * 1000, sum(ts) / len(ts) * 1000


# ---- FastObjects: carregar + Atlas (bytes em memória) ----------------------
def fastobjects_core(paths):
    imgs = [Image.open(p).convert("RGBA") for p in paths]
    a = Atlas(imgs, max_size=MAX, padding=PAD)
    return a.pixels, a.uvs


# ---- PyTexturePacker: carregar + _pack + montar a imagem (em memória) ------
def ptp_core(paths):
    from PyTexturePacker import Utils
    from PyTexturePacker.MaxRectsPacker.MaxRectsPacker import MaxRectsPacker

    packer = MaxRectsPacker(
        max_width=MAX, max_height=MAX, enable_rotated=False,
        force_square=False, border_padding=PAD, shape_padding=PAD,
    )
    rects = Utils.load_images_from_paths(list(paths))
    atlas_list = packer._pack(rects)
    return [a.dump_image(0x00000000) for a in atlas_list]


# ---- end-to-end de cada um (fluxo real da lib) -----------------------------
def ptp_end_to_end(paths, outdir):
    from PyTexturePacker import Packer

    packer = Packer.create(
        max_width=MAX, max_height=MAX, enable_rotated=False,
        force_square=False, border_padding=PAD, shape_padding=PAD,
    )
    packer.pack(list(paths), "atlas%d", str(outdir))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=800)
    parser.add_argument("--size", type=int, default=64)
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        imgdir = Path(tmp) / "imgs"
        paths = gen_images(imgdir, args.n, args.size)
        print(f"N={args.n} imagens de {args.size}px, {args.runs} runs (min ms)\n")

        fo_mn, fo_me = bench(lambda: fastobjects_core(paths), args.runs)
        ptp_mn, ptp_me = bench(lambda: ptp_core(paths), args.runs)
        print("--- núcleo (carregar + empacotar + montar imagem, em memória) ---")
        print(f"FastObjects:      min={fo_mn:8.2f} ms  mean={fo_me:8.2f} ms")
        print(f"PyTexturePacker:  min={ptp_mn:8.2f} ms  mean={ptp_me:8.2f} ms")
        ratio = ptp_mn / fo_mn * 100
        faster = "mais rápido" if fo_mn < ptp_mn else "mais lento"
        print(f"=> FastObjects é {faster}: {ratio:.0f}% da velocidade do PyTexturePacker "
              f"(razão PTP/FO no tempo = {ptp_mn / fo_mn:.2f}x)\n")

        outdir = Path(tmp) / "out"
        outdir.mkdir()
        e2e_mn, e2e_me = bench(lambda: ptp_end_to_end(paths, outdir), args.runs)
        print("--- end-to-end (fluxo real de cada lib) ---")
        print(f"FastObjects (bytes em memória):     min={fo_mn:8.2f} ms")
        print(f"PyTexturePacker (pack() + escrita):  min={e2e_mn:8.2f} ms")


if __name__ == "__main__":
    main()
