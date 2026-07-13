"""Texto: freetype-py + PyOpenGL (canônico: textura e draw call por glifo).

Implementa a técnica publicada de referência (learnopengl.com "Text
Rendering"): FreeType rasteriza cada glifo numa textura GL_RED própria; cada
caractere desenhado é um glBufferSubData do quad + glBindTexture +
glDrawArrays. Sem otimizações além do tutorial.
"""

import json
import sys
from pathlib import Path

import freetype
import glfw
import numpy as np
from OpenGL import GL

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

FONT = "C:/Windows/Fonts/arial.ttf"
SIZE = 16

VS = """#version 330 core
layout (location = 0) in vec4 vertex;  // xy=pos px, zw=uv
out vec2 uv;
uniform vec2 screen;
void main() {
    gl_Position = vec4(vertex.x / screen.x * 2.0 - 1.0,
                       1.0 - vertex.y / screen.y * 2.0, 0.0, 1.0);
    uv = vertex.zw;
}
"""
FS = """#version 330 core
in vec2 uv;
out vec4 color;
uniform sampler2D glyph;
uniform vec3 text_color;
void main() { color = vec4(text_color, texture(glyph, uv).r); }
"""


def compile_program() -> int:
    def shader(src: str, kind) -> int:
        s = GL.glCreateShader(kind)
        GL.glShaderSource(s, src)
        GL.glCompileShader(s)
        if not GL.glGetShaderiv(s, GL.GL_COMPILE_STATUS):
            raise RuntimeError(GL.glGetShaderInfoLog(s).decode())
        return s

    prog = GL.glCreateProgram()
    GL.glAttachShader(prog, shader(VS, GL.GL_VERTEX_SHADER))
    GL.glAttachShader(prog, shader(FS, GL.GL_FRAGMENT_SHADER))
    GL.glLinkProgram(prog)
    if not GL.glGetProgramiv(prog, GL.GL_LINK_STATUS):
        raise RuntimeError(GL.glGetProgramInfoLog(prog).decode())
    return prog


def load_glyphs(chars: str) -> dict:
    """Uma textura GL_RED por glifo — exatamente como no tutorial."""
    face = freetype.Face(FONT)
    face.set_pixel_sizes(0, SIZE)
    GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
    glyphs = {}
    for ch in chars:
        face.load_char(ch)
        g = face.glyph
        w, h = g.bitmap.width, g.bitmap.rows
        tex = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D, 0, GL.GL_RED, w, h, 0,
            GL.GL_RED, GL.GL_UNSIGNED_BYTE,
            bytes(g.bitmap.buffer) if w and h else None,
        )
        for p in (GL.GL_TEXTURE_WRAP_S, GL.GL_TEXTURE_WRAP_T):
            GL.glTexParameteri(GL.GL_TEXTURE_2D, p, GL.GL_CLAMP_TO_EDGE)
        for p in (GL.GL_TEXTURE_MIN_FILTER, GL.GL_TEXTURE_MAG_FILTER):
            GL.glTexParameteri(GL.GL_TEXTURE_2D, p, GL.GL_LINEAR)
        glyphs[ch] = (tex, w, h, g.bitmap_left, g.bitmap_top, g.advance.x >> 6)
    return glyphs


def main() -> None:
    if not glfw.init():
        sys.exit("glfw.init falhou")
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    win = glfw.create_window(WIDTH, HEIGHT, "text: freetype-gl", None, None)
    glfw.make_context_current(win)
    glfw.swap_interval(0)

    prog = compile_program()
    GL.glUseProgram(prog)
    GL.glUniform2f(GL.glGetUniformLocation(prog, "screen"), WIDTH, HEIGHT)
    GL.glUniform3f(GL.glGetUniformLocation(prog, "text_color"), 0.9, 0.9, 0.9)
    GL.glEnable(GL.GL_BLEND)
    GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)

    vao = GL.glGenVertexArrays(1)
    GL.glBindVertexArray(vao)
    vbo = GL.glGenBuffers(1)
    GL.glBindBuffer(GL.GL_ARRAY_BUFFER, vbo)
    GL.glBufferData(GL.GL_ARRAY_BUFFER, 6 * 4 * 4, None, GL.GL_DYNAMIC_DRAW)
    GL.glEnableVertexAttribArray(0)
    GL.glVertexAttribPointer(0, 4, GL.GL_FLOAT, GL.GL_FALSE, 0, None)

    glyphs = load_glyphs("Item 0123456789")

    def draw_string(s: str, x: float, y: float) -> None:
        for ch in s:
            tex, w, h, left, top, adv = glyphs[ch]
            if w and h:
                x0, y0 = x + left, y - top
                quad = np.array(
                    [
                        [x0, y0 + h, 0.0, 1.0],
                        [x0 + w, y0, 1.0, 0.0],
                        [x0, y0, 0.0, 0.0],
                        [x0, y0 + h, 0.0, 1.0],
                        [x0 + w, y0 + h, 1.0, 1.0],
                        [x0 + w, y0, 1.0, 0.0],
                    ],
                    dtype="f4",
                )
                GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
                GL.glBufferSubData(GL.GL_ARRAY_BUFFER, 0, quad.nbytes, quad)
                GL.glDrawArrays(GL.GL_TRIANGLES, 0, 6)
            x += adv

    def trial(n: int) -> tuple[float, float]:
        rng = np.random.default_rng(SEED)
        xs = rng.uniform(0, WIDTH - 100, n)
        ys = rng.uniform(16, HEIGHT, n)
        strings = [f"Item {i:05d}" for i in range(n)]
        timer = FrameTimer()
        for frame in range(WARMUP_FRAMES + MEASURE_FRAMES):
            glfw.poll_events()
            if frame >= WARMUP_FRAMES:
                timer.begin()
            GL.glClearColor(0.1, 0.1, 0.12, 1.0)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT)
            for i in range(n):
                draw_string(strings[i], xs[i], ys[i])
            glfw.swap_buffers(win)
            if frame >= WARMUP_FRAMES:
                timer.end()
        return timer.avg_ms, timer.p99_ms

    result = run_ramp("freetype-gl", trial)
    glfw.terminate()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
