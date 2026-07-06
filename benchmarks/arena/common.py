"""Harness compartilhado da arena: física, timer e controlador de ramp.

Todos os benches usam exatamente esta física e este protocolo de medição,
para que a única variável entre eles seja a renderização.
"""

from __future__ import annotations

import time
from typing import Callable

import numpy as np

WIDTH = 1280
HEIGHT = 720
SEED = 42
DT = 1.0 / 60.0
TARGET_MS = 1000.0 / 60.0
P99_LIMIT_MS = 25.0
WARMUP_FRAMES = 30
MEASURE_FRAMES = 120
GRAVITY = 980.0


def make_bunnies(n: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Cria n coelhos com posição/velocidade determinísticas (dado o rng)."""
    pos = np.empty((n, 2), dtype=np.float32)
    pos[:, 0] = rng.uniform(0, WIDTH, n)
    pos[:, 1] = rng.uniform(0, HEIGHT / 2, n)
    vel = np.empty((n, 2), dtype=np.float32)
    vel[:, 0] = rng.uniform(-250, 250, n)
    vel[:, 1] = rng.uniform(-100, 100, n)
    return pos, vel


def step_bunnies(pos: np.ndarray, vel: np.ndarray, dt: float) -> None:
    """Um passo de física bunnymark clássica, in-place e vetorizado."""
    vel[:, 1] += GRAVITY * dt
    pos += vel * dt

    out_x = (pos[:, 0] < 0) | (pos[:, 0] > WIDTH)
    vel[out_x, 0] *= -1.0
    np.clip(pos[:, 0], 0, WIDTH, out=pos[:, 0])

    hit_floor = pos[:, 1] > HEIGHT
    vel[hit_floor, 1] *= -0.85
    pos[hit_floor, 1] = HEIGHT

    hit_top = pos[:, 1] < 0
    vel[hit_top, 1] *= -1.0
    pos[hit_top, 1] = 0.0


class FrameTimer:
    """Mede a duração de frames em ms via perf_counter_ns."""

    def __init__(self) -> None:
        self.samples_ms: list[float] = []
        self._t0 = 0

    def begin(self) -> None:
        self._t0 = time.perf_counter_ns()

    def end(self) -> None:
        self.samples_ms.append((time.perf_counter_ns() - self._t0) / 1e6)

    @property
    def avg_ms(self) -> float:
        return float(np.mean(self.samples_ms)) if self.samples_ms else 0.0

    @property
    def p99_ms(self) -> float:
        return float(np.percentile(self.samples_ms, 99)) if self.samples_ms else 0.0


class RampController:
    """Aumenta N até o frame time estourar o alvo; guarda o melhor N aprovado."""

    def __init__(
        self,
        start: int = 500,
        growth: float = 1.5,
        target_ms: float = TARGET_MS,
        p99_limit_ms: float = P99_LIMIT_MS,
        max_trials: int = 40,
    ) -> None:
        self.current = start
        self.growth = growth
        self.target_ms = target_ms
        self.p99_limit_ms = p99_limit_ms
        self.max_trials = max_trials
        self.best = 0
        self._trials = 0

    def record(self, avg_ms: float, p99_ms: float) -> int | None:
        """Registra o resultado do trial em `current`. Retorna o próximo N ou None."""
        self._trials += 1
        passed = avg_ms <= self.target_ms and p99_ms <= self.p99_limit_ms
        if not passed:
            return None
        self.best = self.current
        if self._trials >= self.max_trials:
            return None
        self.current = max(self.current + 1, int(self.current * self.growth))
        return self.current


def run_ramp(framework: str, trial_fn: Callable[[int], tuple[float, float]]) -> dict:
    """Executa o protocolo completo: trial_fn(n) -> (avg_ms, p99_ms) por trial."""
    ramp = RampController()
    trials: list[dict] = []
    n: int | None = ramp.current
    while n is not None:
        avg, p99 = trial_fn(n)
        trials.append({"n": n, "avg_ms": round(avg, 3), "p99_ms": round(p99, 3)})
        n = ramp.record(avg, p99)
    return {"framework": framework, "sprites_at_60fps": ramp.best, "trials": trials}
