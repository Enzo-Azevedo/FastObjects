"""Bunnymark nativo do FastObjects: N coelhos quicando em um draw call.

Rode da raiz do repositório:

    .venv\\Scripts\\python examples/bunnymark.py                 # 100.000 coelhos
    .venv\\Scripts\\python examples/bunnymark.py --n 300000      # mais coelhos
    .venv\\Scripts\\python examples/bunnymark.py --frames 120    # auto-teste

O FPS é impresso no terminal uma vez por segundo. ESC sai.
"""

import argparse
import time
from pathlib import Path

import numpy as np

import fastobjects as fo

WIDTH, HEIGHT = 1280, 720
BUNNY = Path(__file__).resolve().parent.parent / "benchmarks" / "arena" / "assets" / "bunny.png"
GRAVITY = 980.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=100_000, help="quantidade de coelhos")
    parser.add_argument("--frames", type=int, default=0, help="roda N frames e sai (auto-teste)")
    args = parser.parse_args()

    win = fo.Window(WIDTH, HEIGHT, f"fastobjects bunnymark - {args.n:,} coelhos")
    batch = fo.SpriteBatch(str(BUNNY), capacity=args.n)

    rng = np.random.default_rng(42)
    bunnies = batch.spawn(
        args.n,
        x=rng.uniform(0, WIDTH, args.n).astype("f4"),
        y=rng.uniform(0, HEIGHT / 2, args.n).astype("f4"),
    )
    vel = np.empty((args.n, 2), dtype="f4")
    vel[:, 0] = rng.uniform(-250, 250, args.n)
    vel[:, 1] = rng.uniform(-100, 100, args.n)

    state = {"frames": 0, "fps_frames": 0, "fps_t0": time.perf_counter()}

    @win.frame
    def update(dt: float) -> None:
        dt = min(dt, 1.0 / 30.0)

        # física vetorizada direto nas views do grupo (zero cópia)
        vel[:, 1] += GRAVITY * dt
        bunnies.pos += vel * dt
        out_x = (bunnies.x < 0) | (bunnies.x > WIDTH)
        vel[out_x, 0] *= -1.0
        hit_floor = bunnies.y > HEIGHT
        vel[hit_floor, 1] *= -0.85
        bunnies.y = np.minimum(bunnies.y, HEIGHT)

        win.clear(0.08, 0.08, 0.10)
        win.draw(batch)

        state["frames"] += 1
        state["fps_frames"] += 1
        now = time.perf_counter()
        if now - state["fps_t0"] >= 1.0:
            print(f"{state['fps_frames'] / (now - state['fps_t0']):.0f} fps", flush=True)
            state["fps_frames"] = 0
            state["fps_t0"] = now

        if win.keys[fo.KEY_ESCAPE] or (args.frames and state["frames"] >= args.frames):
            win.request_close()

    t0 = time.perf_counter()
    win.run()
    elapsed = time.perf_counter() - t0
    win.close()
    print(f"bunnymark ok: {state['frames']} frames, {args.n} sprites, "
          f"{state['frames'] / elapsed:.0f} fps média")


if __name__ == "__main__":
    main()
