"""Multi-imagem: fastobjects (atlas, N sprites de M imagens, 1 draw call)."""

import json
import sys
from pathlib import Path

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

from fastobjects import SpriteBatch, Window  # noqa: E402

ASSETS = Path(__file__).parent / "assets"
IMAGES = [str(ASSETS / f"img{i}.png") for i in range(8)]
MAX_CAPACITY = 2_000_000


def main() -> None:
    win = Window(WIDTH, HEIGHT, "multi: fastobjects", vsync=False)
    batch = SpriteBatch(IMAGES, capacity=MAX_CAPACITY)

    def trial(n: int) -> tuple[float, float]:
        if n > MAX_CAPACITY:
            return float("inf"), float("inf")
        rng = np.random.default_rng(SEED)
        pos, vel = make_bunnies(n, rng)
        batch.clear()
        batch.spawn(n, x=pos[:, 0], y=pos[:, 1], image=np.arange(n) % len(IMAGES))
        live_pos = batch.pos[:n]
        timer = FrameTimer()
        for frame in range(WARMUP_FRAMES + MEASURE_FRAMES):
            win.poll()
            if frame >= WARMUP_FRAMES:
                timer.begin()
            step_bunnies(live_pos, vel, DT)
            win.clear(0.12, 0.12, 0.12)
            batch.draw()
            win.swap()
            if frame >= WARMUP_FRAMES:
                timer.end()
        return timer.avg_ms, timer.p99_ms

    result = run_ramp("fastobjects", trial)
    win.close()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
