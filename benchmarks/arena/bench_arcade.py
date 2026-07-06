"""Bunnymark: arcade (SpriteList na GPU, posições setadas por sprite)."""

import json
from pathlib import Path

import arcade
import numpy as np

from common import (
    DT,
    MEASURE_FRAMES,
    SEED,
    WARMUP_FRAMES,
    WIDTH,
    HEIGHT,
    FrameTimer,
    make_bunnies,
    run_ramp,
    step_bunnies,
)

ASSET = Path(__file__).parent / "assets" / "bunny.png"


def main() -> None:
    win = arcade.Window(WIDTH, HEIGHT, "bench: arcade", vsync=False)
    tex = arcade.load_texture(str(ASSET))

    def trial(n: int) -> tuple[float, float]:
        rng = np.random.default_rng(SEED)
        pos, vel = make_bunnies(n, rng)
        sprites = arcade.SpriteList(capacity=n)
        for i in range(n):
            s = arcade.Sprite(tex)
            s.position = (float(pos[i, 0]), float(pos[i, 1]))
            sprites.append(s)
        timer = FrameTimer()
        for frame in range(WARMUP_FRAMES + MEASURE_FRAMES):
            win.switch_to()
            win.dispatch_events()
            if frame >= WARMUP_FRAMES:
                timer.begin()
            step_bunnies(pos, vel, DT)
            xs = pos[:, 0].tolist()
            ys = pos[:, 1].tolist()
            for i, s in enumerate(sprites):
                s.position = (xs[i], ys[i])
            win.clear()
            sprites.draw()
            win.flip()
            if frame >= WARMUP_FRAMES:
                timer.end()
        sprites.clear()
        return timer.avg_ms, timer.p99_ms

    result = run_ramp("arcade", trial)
    win.close()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
