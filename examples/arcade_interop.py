"""FastObjects dentro de uma janela arcade.

O arcade é dono da janela, do loop e do input; o FastObjects renderiza os
objetos. Texto nativo do arcade (`arcade.draw_text`) desenha o HUD.

Rode da raiz do repositório:

    .venv\\Scripts\\python examples/arcade_interop.py
    .venv\\Scripts\\python examples/arcade_interop.py --frames 120   # auto-teste

ESC sai. Requer arcade (vem com `pip install fastobjects[bench]`).
"""

import argparse
from pathlib import Path

import arcade
import numpy as np

import fastobjects as fo

W, H = 900, 600
BUNNY = Path(__file__).resolve().parent.parent / "benchmarks" / "arena" / "assets" / "bunny.png"
GRAVITY = 980.0


class Demo(arcade.Window):
    def __init__(self, n: int, max_frames: int) -> None:
        super().__init__(W, H, "fastobjects + arcade")
        self.max_frames = max_frames
        self.frames = 0
        self.ext = fo.attach(view_size=(W, H))
        self.batch = fo.SpriteBatch(str(BUNNY), capacity=max(n, 1))
        rng = np.random.default_rng(42)
        self.bunnies = self.batch.spawn(
            n,
            x=rng.uniform(0, W, n).astype("f4"),
            y=rng.uniform(0, H / 2, n).astype("f4"),
        )
        self.vel = np.empty((n, 2), dtype="f4")
        self.vel[:, 0] = rng.uniform(-250, 250, n)
        self.vel[:, 1] = rng.uniform(-100, 100, n)
        self.hud = arcade.Text(
            "FastObjects + arcade — ESC para sair", 10, H - 24,
            arcade.color.WHITE, 16,
        )

    def on_update(self, dt: float) -> None:
        dt = min(dt, 1.0 / 30.0)
        self.vel[:, 1] += GRAVITY * dt
        self.bunnies.pos += self.vel * dt
        out_x = (self.bunnies.x < 0) | (self.bunnies.x > W)
        self.vel[out_x, 0] *= -1.0
        hit_floor = self.bunnies.y > H
        self.vel[hit_floor, 1] *= -0.85
        self.bunnies.y = np.minimum(self.bunnies.y, H)
        self.frames += 1
        if self.max_frames and self.frames >= self.max_frames:
            self.close()

    def on_draw(self) -> None:
        self.clear()
        self.batch.draw()  # objetos do FastObjects
        self.hud.draw()    # HUD nativo do arcade por cima

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        if symbol == arcade.key.ESCAPE:
            self.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=0, help="roda N frames e sai (auto-teste)")
    parser.add_argument("--n", type=int, default=4000, help="quantidade de coelhos")
    args = parser.parse_args()

    demo = Demo(args.n, args.frames)
    arcade.run()
    frames = demo.frames
    print(f"arcade ok: {frames} frames, {args.n} sprites")


if __name__ == "__main__":
    main()
