"""Multi-imagem: arcade (SpriteList, N sprites de M texturas — atlas interno)."""

import json
import sys
from pathlib import Path

import arcade
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "arena"))

from common import (  # noqa: E402
    DT,
    HEIGHT,
    MEASURE_FRAMES,
    SEED,
    WARMUP_FRAMES,
    WIDTH,
    FrameTimer,
    make_bunnies,
    run_ramp,
    step_bunnies,
)

ASSETS = Path(__file__).parent / "assets"
IMAGES = [str(ASSETS / f"img{i}.png") for i in range(8)]


def main() -> None:
    win = arcade.Window(WIDTH, HEIGHT, "multi: arcade", vsync=False)
    texes = [arcade.load_texture(p) for p in IMAGES]

    def trial(n: int) -> tuple[float, float]:
        rng = np.random.default_rng(SEED)
        pos, vel = make_bunnies(n, rng)
        sprites = arcade.SpriteList(capacity=n)
        for i in range(n):
            s = arcade.Sprite(texes[i % len(texes)])
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
