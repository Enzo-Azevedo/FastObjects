"""Texto no FastObjects: título/instruções estáticos + contador de FPS dinâmico.

Rode da raiz do repositório:

    .venv\\Scripts\\python examples/text_hud.py
    .venv\\Scripts\\python examples/text_hud.py --frames 120   # auto-teste

ESC sai.
"""

import argparse
import time

import fastobjects as fo

W, H = 800, 600


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=0, help="roda N frames e sai")
    args = parser.parse_args()

    win = fo.Window(W, H, "fastobjects text HUD")
    font = fo.Font(size=28)

    # Texto estático: escrito uma vez.
    static = fo.TextBatch(font, capacity=500)
    static.write("FastObjects — texto via atlas de glifos", x=20.0, y=20.0)
    static.write("Acentos: ação, coração, à noite!", x=20.0, y=56.0,
                 color=(0.6, 0.9, 1.0, 1.0))
    static.write("centralizado", x=W / 2, y=H - 40, anchor="center",
                 color=(1.0, 0.8, 0.2, 1.0))

    # Texto dinâmico: reescrito por frame (clear + write).
    hud = fo.TextBatch(font, capacity=200)

    state = {"frames": 0, "fps": 0.0, "t0": time.perf_counter(), "acc": 0}

    @win.frame
    def update(dt: float) -> None:
        state["acc"] += 1
        now = time.perf_counter()
        if now - state["t0"] >= 0.25:
            state["fps"] = state["acc"] / (now - state["t0"])
            state["acc"] = 0
            state["t0"] = now

        hud.clear()
        hud.write(f"FPS: {state['fps']:.0f}", x=20.0, y=H - 100,
                  color=(0.5, 1.0, 0.5, 1.0))

        win.clear(0.08, 0.08, 0.10)
        win.draw(static, hud)
        state["frames"] += 1
        if win.keys[fo.KEY_ESCAPE] or (args.frames and state["frames"] >= args.frames):
            win.request_close()

    win.run()
    win.close()
    print(f"text ok: {state['frames']} frames")


if __name__ == "__main__":
    main()
