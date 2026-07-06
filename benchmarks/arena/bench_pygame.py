"""Bunnymark: pygame-ce (Surface.blits, o caminho mais rápido documentado)."""

import json
from pathlib import Path

import numpy as np
import pygame

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
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT), vsync=0)
    pygame.display.set_caption("bench: pygame-ce")
    bunny = pygame.image.load(str(ASSET)).convert_alpha()

    def trial(n: int) -> tuple[float, float]:
        rng = np.random.default_rng(SEED)
        pos, vel = make_bunnies(n, rng)
        timer = FrameTimer()
        for frame in range(WARMUP_FRAMES + MEASURE_FRAMES):
            pygame.event.pump()
            if frame >= WARMUP_FRAMES:
                timer.begin()
            step_bunnies(pos, vel, DT)
            screen.fill((30, 30, 30))
            screen.blits([(bunny, p) for p in pos.tolist()], doreturn=False)
            pygame.display.flip()
            if frame >= WARMUP_FRAMES:
                timer.end()
        return timer.avg_ms, timer.p99_ms

    result = run_ramp("pygame-ce", trial)
    pygame.quit()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
