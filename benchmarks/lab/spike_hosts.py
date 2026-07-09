"""Spike: quais hosts (pyglet/arcade/raylib) funcionam com fo.attach?

Cada host roda em subprocesso próprio (isolamento de contexto GL). Para cada
um: cria a janela do host com OpenGL, fo.attach, desenha um retângulo vermelho
no centro, lê o pixel central e classifica:
  verde     = attach cru basta (pixel vermelho sem intervenção)
  amarelo   = só funciona salvando/restaurando estado GL em volta do draw
  vermelho  = attach falha ou o estado do host corrompe o render

Rode: python benchmarks/lab/spike_hosts.py   (orquestra os 3 subprocessos)
"""

from __future__ import annotations

import subprocess
import sys

W, H = 320, 240
CX, CY = W // 2, H // 2
HOSTS = ["pyglet", "arcade", "raylib"]


def _draw_and_read(ext):
    """Desenha um retângulo vermelho no centro e lê o pixel central (RGB 0-255)."""
    import numpy as np

    import fastobjects as fo

    batch = fo.ShapeBatch(capacity=4, view_size=(W, H))
    batch.rects(1, x=float(CX), y=float(CY), w=60.0, h=60.0, color=(1.0, 0.0, 0.0, 1.0))
    ext.clear(0.0, 0.0, 0.1)
    batch.draw()
    # ctx.screen: framebuffer padrão do host. Lê 1px no centro (origem GL: baixo).
    raw = ext.ctx.screen.read(viewport=(CX, H - CY, 1, 1), components=3)
    return np.frombuffer(raw, dtype="u1")


def _classify(px) -> str:
    r, g, b = int(px[0]), int(px[1]), int(px[2])
    return "verde" if (r > 200 and g < 60 and b < 60) else "?"


def _try_isolated(ext) -> str:
    """Salva/restaura blend+program+VAO+textura ativa em volta do draw; reclassifica."""
    from OpenGL import GL

    blend = GL.glIsEnabled(GL.GL_BLEND)
    prog = GL.glGetIntegerv(GL.GL_CURRENT_PROGRAM)
    vao = GL.glGetIntegerv(GL.GL_VERTEX_ARRAY_BINDING)
    tex = GL.glGetIntegerv(GL.GL_TEXTURE_BINDING_2D)
    try:
        px = _draw_and_read(ext)
    finally:
        (GL.glEnable if blend else GL.glDisable)(GL.GL_BLEND)
        GL.glUseProgram(prog)
        GL.glBindVertexArray(vao)
        GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
    return "amarelo" if _classify(px) == "verde" else "vermelho"


def probe_pyglet() -> None:
    import pyglet

    import fastobjects as fo

    win = pyglet.window.Window(W, H, "spike pyglet", visible=True)
    win.switch_to()
    ext = fo.attach(view_size=(W, H))
    px = _draw_and_read(ext)
    res = _classify(px)
    if res != "verde":
        res = _try_isolated(ext)
    print(f"pyglet {res}: pixel={tuple(int(v) for v in px)}")
    win.close()


def _try_arcade_own_ctx(win) -> str:
    """Rota alternativa do arcade: usar win.ctx diretamente, sem fo.attach."""
    try:
        import numpy as np

        import fastobjects as fo

        batch = fo.ShapeBatch(capacity=4, ctx=win.ctx, view_size=(W, H))
        batch.rects(1, x=float(CX), y=float(CY), w=60.0, h=60.0,
                    color=(0.0, 1.0, 0.0, 1.0))
        win.ctx.screen.use()
        win.ctx.screen.clear(0.0, 0.0, 0.1)
        batch.draw()
        raw = win.ctx.screen.read(viewport=(CX, H - CY, 1, 1), components=3)
        px = np.frombuffer(raw, dtype="u1")
        return "verde" if (int(px[1]) > 200 and int(px[0]) < 60) else "vermelho"
    except Exception as e:  # noqa: BLE001
        return f"vermelho ({type(e).__name__}: {e})"


def probe_arcade() -> None:
    import arcade

    import fastobjects as fo

    win = arcade.Window(W, H, "spike arcade")
    win.switch_to()
    try:
        ext = fo.attach(view_size=(W, H))
        px = _draw_and_read(ext)
        res = _classify(px)
        if res != "verde":
            res = _try_isolated(ext)
    except Exception as e:  # noqa: BLE001
        res = f"vermelho ({type(e).__name__}: {e})"
        px = (0, 0, 0)
    alt = _try_arcade_own_ctx(win)
    print(f"arcade {res} (attach) / {alt} (ctx proprio): pixel={tuple(int(v) for v in px)}")
    win.close()


def probe_raylib() -> None:
    import pyray as rl

    import fastobjects as fo

    rl.set_config_flags(0)
    rl.init_window(W, H, "spike raylib")
    try:
        ext = fo.attach(view_size=(W, H))
    except Exception as e:  # noqa: BLE001
        print(f"raylib vermelho: attach falhou ({type(e).__name__}: {e})")
        rl.close_window()
        return
    rl.begin_drawing()
    rl.clear_background(rl.Color(0, 0, 25, 255))
    try:
        px = _draw_and_read(ext)
        res = _classify(px)
        if res != "verde":
            res = _try_isolated(ext)
    except Exception as e:  # noqa: BLE001
        res = f"vermelho (draw/read falhou: {type(e).__name__}: {e})"
        px = (0, 0, 0)
    rl.end_drawing()
    print(f"raylib {res}: pixel={tuple(int(v) for v in px)}")
    rl.close_window()


PROBES = {"pyglet": probe_pyglet, "arcade": probe_arcade, "raylib": probe_raylib}


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "--host":
        PROBES[sys.argv[2]]()
        return
    for host in HOSTS:
        print(f"== {host} ==", flush=True)
        try:
            proc = subprocess.run(
                [sys.executable, __file__, "--host", host],
                capture_output=True, text=True, timeout=120,
            )
            out = (proc.stdout + proc.stderr).strip()
            print(out if out else f"(sem saida, returncode={proc.returncode})")
        except subprocess.TimeoutExpired:
            print(f"{host}: TIMEOUT")


if __name__ == "__main__":
    main()
