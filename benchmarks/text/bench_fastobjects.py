"""Texto: fastobjects (TextBatch, N strings, um draw call)."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

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

from fastobjects import Font, TextBatch, Window  # noqa: E402

MAX_CAPACITY = 2_000_000  # glifos


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font", default=None)
    parser.add_argument("--name", default="fastobjects")
    args = parser.parse_args()

    win = Window(WIDTH, HEIGHT, f"text: {args.name}", vsync=False)
    font = Font(args.font, size=16)

    def trial(n: int) -> tuple[float, float]:
        strings = [f"Item {i:05d}" for i in range(n)]
        if n * 10 > MAX_CAPACITY:
            return float("inf"), float("inf")
        rng = np.random.default_rng(SEED)
        xs = rng.uniform(0, WIDTH - 100, n)
        ys = rng.uniform(0, HEIGHT - 16, n)
        text = TextBatch(font, capacity=n * 10, view_size=(WIDTH, HEIGHT))
        for i, sval in enumerate(strings):
            text.write(sval, float(xs[i]), float(ys[i]))
        timer = FrameTimer()
        for frame in range(WARMUP_FRAMES + MEASURE_FRAMES):
            win.poll()
            if frame >= WARMUP_FRAMES:
                timer.begin()
            win.clear(0.1, 0.1, 0.12)
            text.draw()
            win.swap()
            if frame >= WARMUP_FRAMES:
                timer.end()
        return timer.avg_ms, timer.p99_ms

    result = run_ramp(args.name, trial)
    win.close()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
