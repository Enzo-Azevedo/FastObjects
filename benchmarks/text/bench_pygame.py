"""Texto: pygame (Font.render por string + blit — uso idiomático)."""

import json
import sys
from pathlib import Path

import numpy as np
import pygame

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
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT), vsync=0)
    pygame.display.set_caption("text: pygame")
    font = pygame.font.SysFont(None, 16)

    def trial(n: int) -> tuple[float, float]:
        rng = np.random.default_rng(SEED)
        xs = rng.uniform(0, WIDTH - 100, n)
        ys = rng.uniform(0, HEIGHT - 16, n)
        # pré-renderiza as surfaces (o pygame re-rasteriza a string inteira)
        surfs = [font.render(f"Item {i:05d}", True, (230, 230, 230)) for i in range(n)]
        pos = [(int(xs[i]), int(ys[i])) for i in range(n)]
        timer = FrameTimer()
        for frame in range(WARMUP_FRAMES + MEASURE_FRAMES):
            pygame.event.pump()
            if frame >= WARMUP_FRAMES:
                timer.begin()
            screen.fill((25, 25, 30))
            screen.blits(list(zip(surfs, pos)), doreturn=False)
            pygame.display.flip()
            if frame >= WARMUP_FRAMES:
                timer.end()
        return timer.avg_ms, timer.p99_ms

    result = run_ramp("pygame-ce", trial)
    pygame.quit()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
