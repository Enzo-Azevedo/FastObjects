"""Multi-imagem: pyglet (Batch + Sprite, M imagens cicladas)."""

import json
import sys
from pathlib import Path

import numpy as np
import pyglet

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
    win = pyglet.window.Window(WIDTH, HEIGHT, "multi: pyglet", vsync=False)
    imgs = [pyglet.image.load(p) for p in IMAGES]

    def trial(n: int) -> tuple[float, float]:
        rng = np.random.default_rng(SEED)
        pos, vel = make_bunnies(n, rng)
        batch = pyglet.graphics.Batch()
        sprites = [
            pyglet.sprite.Sprite(imgs[i % len(imgs)], batch=batch) for i in range(n)
        ]
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
