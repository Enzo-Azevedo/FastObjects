"""Animação de spritesheet com FastObjects: um atlas de K frames, group.image.

Gera K frames coloridos num diretório temporário, cria um `SpriteBatch` com
todos, e anima um grupo trocando `group.image` a cada poucos frames — tudo em
um único draw call.

Rode da raiz do repositório:

    .venv\\Scripts\\python examples/atlas_animation.py
    .venv\\Scripts\\python examples/atlas_animation.py --frames 120   # auto-teste

ESC sai.
"""

import argparse
import colorsys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import fastobjects as fo

W, H = 800, 600
K = 8          # frames do "spritesheet"
HELD = 6       # frames de tela por frame de animação


def make_frames(folder: Path) -> list[str]:
    paths = []
    for i in range(K):
        rgb = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(i / K, 0.7, 1.0))
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse((4, 4, 59, 59), fill=(*rgb, 255))
        d.pieslice((4, 4, 59, 59), start=0, end=360 * i / K, fill=(255, 255, 255, 255))
        p = folder / f"frame{i}.png"
        img.save(p)
        paths.append(str(p))
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=0, help="roda N frames e sai")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        win = fo.Window(W, H, "fastobjects atlas animation")
        frames = make_frames(Path(tmp))
        batch = fo.SpriteBatch(frames, capacity=64)

        rng = np.random.default_rng(1)
        n = 24
        group = batch.spawn(
            n,
            x=rng.uniform(80, W - 80, n).astype("f4"),
            y=rng.uniform(80, H - 80, n).astype("f4"),
            w=64.0, h=64.0,
        )

        state = {"count": 0}

        @win.frame
        def update(dt: float) -> None:
            group.image = (state["count"] // HELD) % K  # anima o spritesheet
            win.clear(0.08, 0.08, 0.10)
            win.draw(batch)
            state["count"] += 1
            if win.keys[fo.KEY_ESCAPE] or (args.frames and state["count"] >= args.frames):
                win.request_close()

        win.run()
        win.close()
        print(f"atlas animation ok: {state['count']} frames")


if __name__ == "__main__":
    main()
