"""Bunnymark: pyglet (Batch + Sprite, posições setadas por sprite)."""

import json
from pathlib import Path

import numpy as np
import pyglet

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
    win = pyglet.window.Window(WIDTH, HEIGHT, "bench: pyglet", vsync=False)
    img = pyglet.image.load(str(ASSET))

    def trial(n: int) -> tuple[float, float]:
        rng = np.random.default_rng(SEED)
        pos, vel = make_bunnies(n, rng)
        batch = pyglet.graphics.Batch()
        sprites = [pyglet.sprite.Sprite(img, batch=batch) for _ in range(n)]
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
                s.position = (xs[i], ys[i], 0)
            win.clear()
            batch.draw()
            win.flip()
            if frame >= WARMUP_FRAMES:
                timer.end()
        for s in sprites:
            s.delete()
        return timer.avg_ms, timer.p99_ms

    result = run_ramp("pyglet", trial)
    win.close()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
