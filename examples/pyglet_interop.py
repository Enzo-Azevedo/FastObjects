"""FastObjects dentro de uma janela pyglet.

O pyglet é dono da janela, do loop e do input; o FastObjects renderiza os
objetos. Um `pyglet.text.Label` nativo desenha o HUD por cima.

Rode da raiz do repositório:

    .venv\\Scripts\\python examples/pyglet_interop.py
    .venv\\Scripts\\python examples/pyglet_interop.py --frames 120   # auto-teste

ESC sai. Requer pyglet (vem com `pip install fastobjects[bench]`).
"""

import argparse
import time
from pathlib import Path

import numpy as np
import pyglet

import fastobjects as fo

W, H = 900, 600
BUNNY = Path(__file__).resolve().parent.parent / "benchmarks" / "arena" / "assets" / "bunny.png"
GRAVITY = 980.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=0, help="roda N frames e sai (auto-teste)")
    parser.add_argument("--n", type=int, default=4000, help="quantidade de coelhos")
    args = parser.parse_args()

    win = pyglet.window.Window(W, H, "fastobjects + pyglet")
    keys = pyglet.window.key.KeyStateHandler()
    win.push_handlers(keys)

    ext = fo.attach(view_size=(W, H))
    batch = fo.SpriteBatch(str(BUNNY), capacity=max(args.n, 1))

    rng = np.random.default_rng(42)
    bunnies = batch.spawn(
        args.n,
        x=rng.uniform(0, W, args.n).astype("f4"),
        y=rng.uniform(0, H / 2, args.n).astype("f4"),
    )
    vel = np.empty((args.n, 2), dtype="f4")
    vel[:, 0] = rng.uniform(-250, 250, args.n)
    vel[:, 1] = rng.uniform(-100, 100, args.n)

    label = pyglet.text.Label(
        "FastObjects + pyglet — ESC para sair",
        x=10, y=H - 24, color=(255, 255, 255, 255),
    )

    frames = 0
    last = time.perf_counter()
    while not win.has_exit:
        win.switch_to()
        win.dispatch_events()
        now = time.perf_counter()
        dt = min(now - last, 1.0 / 30.0)
        last = now

        vel[:, 1] += GRAVITY * dt
        bunnies.pos += vel * dt
        out_x = (bunnies.x < 0) | (bunnies.x > W)
        vel[out_x, 0] *= -1.0
        hit_floor = bunnies.y > H
        vel[hit_floor, 1] *= -0.85
        bunnies.y = np.minimum(bunnies.y, H)

        ext.clear(0.08, 0.08, 0.10)
        batch.draw()       # objetos do FastObjects
        label.draw()       # HUD nativo do pyglet por cima
        win.flip()

        frames += 1
        if keys[pyglet.window.key.ESCAPE] or (args.frames and frames >= args.frames):
            break

    win.close()
    print(f"pyglet ok: {frames} frames, {args.n} sprites")


if __name__ == "__main__":
    main()
