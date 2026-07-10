"""Texto: pyglet (N Labels num Batch — atlas de glifos batched)."""

import json
import sys
from pathlib import Path

import numpy as np
import pyglet

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "arena"))

from common import (  # noqa: E402
    HEIGHT,
    MEASURE_FRAMES,
    SEED,
    WARMUP_FRAMES,
    WIDTH,
    FrameTimer,
    run_ramp,
)


def main() -> None:
    win = pyglet.window.Window(WIDTH, HEIGHT, "text: pyglet", vsync=False)

    def trial(n: int) -> tuple[float, float]:
        rng = np.random.default_rng(SEED)
        xs = rng.uniform(0, WIDTH - 100, n)
        ys = rng.uniform(0, HEIGHT - 16, n)
        batch = pyglet.graphics.Batch()
        labels = [
            pyglet.text.Label(
                f"Item {i:05d}", font_size=10,
                x=float(xs[i]), y=float(ys[i]), batch=batch,
            )
            for i in range(n)
        ]
        timer = FrameTimer()
        for frame in range(WARMUP_FRAMES + MEASURE_FRAMES):
            win.switch_to()
            win.dispatch_events()
            if frame >= WARMUP_FRAMES:
                timer.begin()
            win.clear()
            batch.draw()
            win.flip()
            if frame >= WARMUP_FRAMES:
                timer.end()
        for label in labels:
            label.delete()
        return timer.avg_ms, timer.p99_ms

    result = run_ramp("pyglet", trial)
    win.close()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
