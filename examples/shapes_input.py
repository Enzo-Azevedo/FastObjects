"""Formas + input do FastObjects: círculo segue o mouse, setas movem o retângulo.

Rode da raiz do repositório:

    .venv\\Scripts\\python examples/shapes_input.py
    .venv\\Scripts\\python examples/shapes_input.py --frames 120   # auto-teste

Controles: mouse move o círculo; setas movem o retângulo; ESC sai.
"""

import argparse

import fastobjects as fo

WIDTH, HEIGHT = 800, 600
SPEED = 300.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=0, help="roda N frames e sai (auto-teste)")
    args = parser.parse_args()

    win = fo.Window(WIDTH, HEIGHT, "fastobjects shapes + input")
    shapes = fo.ShapeBatch(capacity=16)

    # decoração fixa: moldura de linhas
    shapes.lines(1, x1=20.0, y1=20.0, x2=WIDTH - 20.0, y2=20.0, width=2.0,
                 color=(0.3, 0.6, 0.9, 1.0))
    shapes.lines(1, x1=20.0, y1=HEIGHT - 20.0, x2=WIDTH - 20.0, y2=HEIGHT - 20.0,
                 width=2.0, color=(0.3, 0.6, 0.9, 1.0))

    cursor = shapes.circles(1, x=WIDTH / 2, y=HEIGHT / 2, radius=18.0,
                            color=(1.0, 0.7, 0.1, 0.9))
    player = shapes.rects(1, x=WIDTH / 2, y=HEIGHT / 2, w=48.0, h=48.0,
                          color=(0.2, 0.9, 0.4, 1.0))

    state = {"frames": 0}

    @win.frame
    def update(dt: float) -> None:
        # círculo segue o cursor (polling do mouse)
        cursor.x = win.mouse.x
        cursor.y = win.mouse.y

        # retângulo com as setas (polling do teclado)
        if win.keys[fo.KEY_RIGHT]:
            player.x += SPEED * dt
        if win.keys[fo.KEY_LEFT]:
            player.x -= SPEED * dt
        if win.keys[fo.KEY_DOWN]:
            player.y += SPEED * dt
        if win.keys[fo.KEY_UP]:
            player.y -= SPEED * dt

        win.clear(0.08, 0.08, 0.10)
        win.draw(shapes)

        state["frames"] += 1
        if win.keys[fo.KEY_ESCAPE] or (args.frames and state["frames"] >= args.frames):
            win.request_close()

    win.run()
    win.close()
    print(f"shapes ok: {state['frames']} frames")


if __name__ == "__main__":
    main()
