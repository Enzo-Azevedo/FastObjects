"""Bunnymark: fastobjects (estado NumPy, 1 upload, 1 draw call instanciado)."""

import json
from pathlib import Path

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
from fastobjects import SpriteBatch, Window

ASSET = Path(__file__).parent / "assets" / "bunny.png"
MAX_CAPACITY = 2_000_000


def main() -> None:
    win = Window(WIDTH, HEIGHT, "bench: fastobjects", vsync=False)
    batch = SpriteBatch(win.ctx, str(ASSET), capacity=MAX_CAPACITY, view_size=(WIDTH, HEIGHT))

    def trial(n: int) -> tuple[float, float]:
        if n > MAX_CAPACITY:
            # Teto de capacity do batch, não um limite de performance: encerra
            # o ramp como trial falho em vez de deixar spawn() levantar
            # CapacityError e derrubar o subprocesso.
            return float("inf"), float("inf")
        rng = np.random.default_rng(SEED)
        pos, vel = make_bunnies(n, rng)
        batch.clear()
        batch.spawn(n, x=pos[:, 0], y=pos[:, 1])
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
