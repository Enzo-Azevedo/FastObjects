"""Lab: qual estratégia de upload de buffer é mais rápida em N alto?

Estratégias:
  A) write total do trecho usado (implementação atual)
  B) orphan() antes do write (evita stall de sincronização GPU)
  C) write duplo-buffer (alterna entre 2 buffers, um por frame)

Contexto standalone + FBO: mede só upload+draw, sem ruído de janela/vsync.
"""

from __future__ import annotations

import time

import moderngl
import numpy as np

N = 200_000
FRAMES = 300
SIZE = (1280, 720)
FLOATS = 9
STRIDE = FLOATS * 4


def make_gl():
    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.BLEND)
    fbo = ctx.framebuffer(color_attachments=[ctx.texture(SIZE, 4)])
    fbo.use()
    return ctx, fbo


def build(ctx, n):
    from fastobjects.core.renderer import SpriteRenderer

    tex = ctx.texture((4, 4), 4, data=b"\xff" * 64)
    renderer = SpriteRenderer(ctx, tex, capacity=n, view_size=SIZE)
    rng = np.random.default_rng(42)
    data = np.zeros((n, FLOATS), dtype="f4")
    data[:, 0] = rng.uniform(0, SIZE[0], n)
    data[:, 1] = rng.uniform(0, SIZE[1], n)
    data[:, 2:4] = 26.0
    data[:, 5:9] = 1.0
    return renderer, data


def measure(name, frame_fn):
    t0 = time.perf_counter_ns()
    for _ in range(FRAMES):
        frame_fn()
    ms = (time.perf_counter_ns() - t0) / 1e6 / FRAMES
    print(f"{name}: {ms:.3f} ms/frame")
    return ms


def main() -> None:
    ctx, fbo = make_gl()
    renderer, data = build(ctx, N)

    def strategy_a():
        data[:, 0] += 0.01  # simula atualização
        renderer.buffer.write(data)
        renderer.texture.use(0)
        renderer.vao.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=N)
        ctx.finish()

    def strategy_b():
        data[:, 0] += 0.01
        renderer.buffer.orphan()
        renderer.buffer.write(data)
        renderer.texture.use(0)
        renderer.vao.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=N)
        ctx.finish()

    # C: double-buffer
    buf2 = ctx.buffer(reserve=N * STRIDE)
    vao2 = ctx.vertex_array(
        renderer.prog,
        [(buf2, "2f 2f 1f 4f/i", "in_pos", "in_size", "in_rot", "in_color")],
    )
    flip = {"i": 0}

    def strategy_c():
        data[:, 0] += 0.01
        flip["i"] ^= 1
        buf, vao = (renderer.buffer, renderer.vao) if flip["i"] else (buf2, vao2)
        buf.write(data)
        renderer.texture.use(0)
        vao.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=N)
        ctx.finish()

    print(f"N={N}, {FRAMES} frames, GPU={ctx.info['GL_RENDERER']}")
    results = {
        "A write": measure("A write total", strategy_a),
        "B orphan+write": measure("B orphan+write", strategy_b),
        "C double-buffer": measure("C double-buffer", strategy_c),
    }
    winner = min(results, key=results.get)
    print(f"vencedora: {winner}")


if __name__ == "__main__":
    main()
