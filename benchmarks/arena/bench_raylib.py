"""Bunnymark: raylib (pyray, draw_texture por coelho — batching interno em C)."""

import json
from pathlib import Path

import numpy as np
import pyray as rl

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
    rl.set_config_flags(0)  # sem VSYNC_HINT: vsync off
    rl.init_window(WIDTH, HEIGHT, "bench: raylib")
    tex = rl.load_texture(str(ASSET))
    bg = rl.Color(30, 30, 30, 255)
    white = rl.WHITE

    def trial(n: int) -> tuple[float, float]:
        rng = np.random.default_rng(SEED)
        pos, vel = make_bunnies(n, rng)
        timer = FrameTimer()
        for frame in range(WARMUP_FRAMES + MEASURE_FRAMES):
            if frame >= WARMUP_FRAMES:
                timer.begin()
            step_bunnies(pos, vel, DT)
            coords = pos.astype(np.int32).tolist()
            rl.begin_drawing()
            rl.clear_background(bg)
            draw = rl.draw_texture
            for x, y in coords:
                draw(tex, x, y, white)
            rl.end_drawing()
            if frame >= WARMUP_FRAMES:
                timer.end()
        return timer.avg_ms, timer.p99_ms

    result = run_ramp("raylib", trial)
    rl.unload_texture(tex)
    rl.close_window()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
