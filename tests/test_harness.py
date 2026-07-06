import numpy as np
import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "benchmarks" / "arena"))

from common import (  # noqa: E402
    HEIGHT,
    WIDTH,
    FrameTimer,
    RampController,
    make_bunnies,
    run_ramp,
    step_bunnies,
)


def test_make_bunnies_shapes_and_determinism():
    rng1 = np.random.default_rng(42)
    rng2 = np.random.default_rng(42)
    pos1, vel1 = make_bunnies(100, rng1)
    pos2, vel2 = make_bunnies(100, rng2)
    assert pos1.shape == (100, 2) and vel1.shape == (100, 2)
    assert pos1.dtype == np.float32 and vel1.dtype == np.float32
    np.testing.assert_array_equal(pos1, pos2)
    assert (pos1[:, 0] >= 0).all() and (pos1[:, 0] <= WIDTH).all()


def test_step_bunnies_bounces_off_floor():
    pos = np.array([[100.0, HEIGHT - 0.5]], dtype=np.float32)
    vel = np.array([[0.0, 300.0]], dtype=np.float32)
    step_bunnies(pos, vel, 1.0 / 60.0)
    assert pos[0, 1] == HEIGHT  # preso no chão
    assert vel[0, 1] < 0  # velocidade invertida (quicou)


def test_step_bunnies_bounces_off_walls():
    pos = np.array([[WIDTH - 0.1, 300.0]], dtype=np.float32)
    vel = np.array([[500.0, 0.0]], dtype=np.float32)
    step_bunnies(pos, vel, 1.0 / 60.0)
    assert pos[0, 0] == WIDTH
    assert vel[0, 0] < 0


def test_frame_timer_stats():
    t = FrameTimer()
    for _ in range(10):
        t.begin()
        t.end()
    assert t.avg_ms >= 0.0
    assert t.p99_ms >= t.avg_ms * 0.0  # p99 definido e não-negativo
    assert len(t.samples_ms) == 10


def test_ramp_controller_grows_then_stops():
    r = RampController(start=100, growth=2.0, target_ms=16.7, p99_limit_ms=25.0)
    assert r.current == 100
    assert r.record(10.0, 12.0) == 200  # passou -> cresce
    assert r.record(12.0, 14.0) == 400
    assert r.record(20.0, 30.0) is None  # falhou -> para
    assert r.best == 200


def test_ramp_controller_fails_first_trial():
    r = RampController(start=100, growth=2.0)
    assert r.record(50.0, 60.0) is None
    assert r.best == 0


def test_ramp_controller_respects_max_trials():
    r = RampController(start=1, growth=1.0001, max_trials=3)
    r.record(1.0, 1.0)
    r.record(1.0, 1.0)
    assert r.record(1.0, 1.0) is None  # 3o trial é o último


def test_run_ramp_returns_report():
    calls = []

    def fake_trial(n):
        calls.append(n)
        return (10.0, 12.0) if n <= 1000 else (30.0, 40.0)

    result = run_ramp("fake", fake_trial)
    assert result["framework"] == "fake"
    assert result["sprites_at_60fps"] == calls[-2]  # último que passou
    assert len(result["trials"]) == len(calls)
