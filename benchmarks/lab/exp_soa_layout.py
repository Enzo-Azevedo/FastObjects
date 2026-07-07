"""Lab: quanto custa o upload por layout? AoS total vs SoA vs SoA quantizado.

Cenário 1 (frame típico): só posições mudam por frame.
Cenário 2 (pior caso): todas as colunas mudam todo frame.
Estratégias:
  A) AoS atual: 1 buffer interleaved de 36 B/inst, write total por frame.
  B) SoA f4: pos (8 B) write por frame; frias só quando mudam.
  C) SoA quantizado: pos f4; frias em u8-norm/f16 (cor 4 B, size 4 B, rot 2 B).
  B-orphan) B com orphan() no buffer de pos antes do write.

Contexto standalone + FBO; ctx.finish() por frame; N=100k; 300 frames; 5 runs.
"""

from __future__ import annotations

import time

import moderngl
import numpy as np

N = 100_000
FRAMES = 300
RUNS = 5
SIZE = (800, 600)

VS = """
#version 330
uniform vec2 u_view;
in vec2 in_pos;
in vec2 in_size;
in float in_rot;
in vec4 in_color;
out vec4 v_color;
const vec2 CORNERS[4] = vec2[4](
    vec2(-0.5, -0.5), vec2(0.5, -0.5), vec2(-0.5, 0.5), vec2(0.5, 0.5)
);
void main() {
    vec2 corner = CORNERS[gl_VertexID] * in_size;
    float c = cos(in_rot);
    float s = sin(in_rot);
    vec2 world = in_pos + vec2(corner.x * c - corner.y * s,
                               corner.x * s + corner.y * c);
    gl_Position = vec4(world * u_view + vec2(-1.0, 1.0), 0.0, 1.0);
    v_color = in_color;
}
"""
FS = """
#version 330
in vec4 v_color;
out vec4 f_color;
void main() { f_color = v_color; }
"""


def make_ctx():
    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.BLEND)
    fbo = ctx.framebuffer(color_attachments=[ctx.texture(SIZE, 4)])
    fbo.use()
    return ctx


def make_data(rng):
    pos = np.empty((N, 2), dtype="f4")
    pos[:, 0] = rng.uniform(0, SIZE[0], N)
    pos[:, 1] = rng.uniform(0, SIZE[1], N)
    size = np.full((N, 2), 6.0, dtype="f4")
    rot = np.zeros(N, dtype="f4")
    color = rng.uniform(0.2, 1.0, (N, 4)).astype("f4")
    color[:, 3] = 1.0
    return pos, size, rot, color


def measure(name, frame_fn, ctx):
    best = []
    for _ in range(RUNS):
        t0 = time.perf_counter_ns()
        for _ in range(FRAMES):
            frame_fn()
            ctx.finish()
        best.append((time.perf_counter_ns() - t0) / 1e6 / FRAMES)
    ms = min(best)  # melhor de 5: isola o custo intrínseco do ruído do SO
    runs = ", ".join(f"{b:.3f}" for b in best)
    print(f"{name}: {ms:.3f} ms/frame (runs: {runs})")
    return ms


def main() -> None:
    ctx = make_ctx()
    rng = np.random.default_rng(42)
    pos, size, rot, color = make_data(rng)
    prog = ctx.program(vertex_shader=VS, fragment_shader=FS)
    prog["u_view"].value = (2.0 / SIZE[0], -2.0 / SIZE[1])

    # --- A: AoS interleaved (layout atual do ShapeBatch sem kind) ---
    aos = np.zeros((N, 9), dtype="f4")
    aos[:, 0:2] = pos
    aos[:, 2:4] = size
    aos[:, 4] = rot
    aos[:, 5:9] = color
    buf_a = ctx.buffer(reserve=N * 36)
    vao_a = ctx.vertex_array(
        prog, [(buf_a, "2f 2f 1f 4f/i", "in_pos", "in_size", "in_rot", "in_color")]
    )

    def frame_a_tipico():
        aos[:, 0] += 0.01
        buf_a.write(aos)
        vao_a.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=N)

    # --- B: SoA f4 ---
    b_pos = ctx.buffer(reserve=N * 8)
    b_size = ctx.buffer(size.tobytes())
    b_rot = ctx.buffer(rot.tobytes())
    b_color = ctx.buffer(color.tobytes())
    vao_b = ctx.vertex_array(prog, [
        (b_pos, "2f/i", "in_pos"),
        (b_size, "2f/i", "in_size"),
        (b_rot, "1f/i", "in_rot"),
        (b_color, "4f/i", "in_color"),
    ])

    def frame_b_tipico():
        pos[:, 0] += 0.01
        b_pos.write(pos)
        vao_b.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=N)

    def frame_b_orphan():
        pos[:, 0] += 0.01
        b_pos.orphan()
        b_pos.write(pos)
        vao_b.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=N)

    def frame_b_pior():
        pos[:, 0] += 0.01
        b_pos.write(pos)
        b_size.write(size)
        b_rot.write(rot)
        b_color.write(color)
        vao_b.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=N)

    # --- C: SoA quantizado (frias em f2/u8-norm) ---
    c_pos = ctx.buffer(reserve=N * 8)
    c_size = ctx.buffer(size.astype("f2").tobytes())
    c_rot = ctx.buffer(rot.astype("f2").tobytes())
    c_color = ctx.buffer((color * 255.0 + 0.5).astype("u1").tobytes())
    vao_c = ctx.vertex_array(prog, [
        (c_pos, "2f/i", "in_pos"),
        (c_size, "2f2/i", "in_size"),
        (c_rot, "1f2/i", "in_rot"),
        (c_color, "4f1/i", "in_color"),
    ])

    def frame_c_tipico():
        pos[:, 0] += 0.01
        c_pos.write(pos)
        vao_c.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=N)

    def frame_c_pior():
        pos[:, 0] += 0.01
        c_pos.write(pos)
        c_size.write(size.astype("f2"))
        c_rot.write(rot.astype("f2"))
        c_color.write((color * 255.0 + 0.5).astype("u1"))
        vao_c.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=N)

    print(f"N={N}, {FRAMES} frames, {RUNS} runs, GPU={ctx.info['GL_RENDERER']}")
    print("--- Cenário 1: frame típico (só posições mudam) ---")
    measure("A  AoS write total (36B/inst)", frame_a_tipico, ctx)
    measure("B  SoA f4, só pos (8B/inst)", frame_b_tipico, ctx)
    measure("B' SoA f4, pos com orphan", frame_b_orphan, ctx)
    measure("C  SoA quant, só pos (8B/inst)", frame_c_tipico, ctx)
    print("--- Cenário 2: pior caso (todas as colunas mudam) ---")
    measure("A  AoS write total (36B/inst)", frame_a_tipico, ctx)
    measure("B  SoA f4 tudo (36B/inst)", frame_b_pior, ctx)
    measure("C  SoA quant tudo (18B/inst)", frame_c_pior, ctx)


if __name__ == "__main__":
    main()
