# FastObjects

The fastest 2D object rendering library for Python.

[**Documentation**](https://enzo-azevedo.github.io/FastObjects/) · [Documentação em português](https://enzo-azevedo.github.io/FastObjects/pt/)

Sprites sustained at 60 fps in the bunnymark arena, measured on the same
machine (AMD Radeon RX 580, Python 3.13, 2026-07-07) against other Python
rendering libraries:

| Framework | Sprites @ 60 fps |
|---|---|
| **fastobjects** | **328,213** |
| arcade | 3,795 |
| raylib | 3,795 |
| pygame-ce | 2,530 |
| pyglet | 2,530 |

That is **86x** the closest competitor. Numbers vary between runs by one ramp
step (±1.5x); see [`benchmarks/RESULTS.md`](https://github.com/Enzo-Azevedo/FastObjects/blob/main/benchmarks/RESULTS.md) for the
full dated series, methodology, and hardware details before quoting a number
as "current".

## Installation

```bash
pip install fastobjects
```

Requires Python ≥ 3.11 and OpenGL 3.3 core.

## Quick start

```python
import fastobjects as fo

win = fo.Window(800, 600, title="FastObjects demo")

sprites = fo.SpriteBatch("player.png", capacity=1000)  # any image file
group = sprites.spawn(1, x=400, y=300)

@win.frame
def update(dt: float) -> None:
    if win.keys[fo.KEY_RIGHT]:
        group.pos[:, 0] += 200 * dt

    win.clear(0.1, 0.1, 0.1)
    win.draw(sprites)

    if win.keys[fo.KEY_ESCAPE]:
        win.request_close()

win.run()
```

- `Window` opens a native GLFW window with an OpenGL 3.3 core context and
  drives the frame loop (`run()` calls your `@win.frame` callback every
  frame with `dt`). `win.keys[fo.KEY_X]` and `win.mouse` expose polled input
  state.
- `SpriteBatch` holds up to `capacity` textured sprites; `spawn()` returns a
  `SpriteGroup` whose `.pos`, `.size`, `.rot`, and `.color` are NumPy views
  into the batch — writing to them updates the sprites directly, no
  per-object overhead. `batch.despawn(group)` removes a group and frees its
  capacity; the other groups' handles stay valid.
- `ShapeBatch` works the same way for rectangles, circles, and lines
  (`batch.rects(...)`, `batch.circles(...)`, `batch.lines(...)`), useful for
  debug overlays or non-textured geometry.
- `win.draw(*batches)` issues one draw call per batch, in the order given.

## Why it's fast

Three decisions, each validated by benchmark (every experiment — winners and
losers — is recorded in [`benchmarks/RESULTS.md`](https://github.com/Enzo-Azevedo/FastObjects/blob/main/benchmarks/RESULTS.md)):

1. **No Python objects per sprite.** State lives in flat NumPy columns
   (structure-of-arrays); updates are vectorized array math, never a
   per-object loop.
2. **One instanced draw call per batch.** The quad is generated in the
   vertex shader; per-instance attributes stream from one VBO per column.
3. **You pay for change, not existence.** Positions upload every frame;
   size, rotation, and color upload only in the frames you touch them
   (automatic, conservative dirty tracking). A typical frame uploads
   8 bytes per sprite instead of 40.

The result: at 100,000 moving objects, FastObjects sustains **384 fps** —
above the 353 fps of a minimal hand-written `moderngl` renderer used as the
technique's reference ceiling (which pays extra CPU copies per frame that
FastObjects avoids).

## Use it inside pygame

pygame owns the window, events, input, and sound; FastObjects owns object
insertion, update, removal, and rendering. Classic pygame drawing
(`pygame.draw`, `pygame.font`) composites on top via `SurfaceLayer`:

```python
import pygame
import fastobjects as fo

pygame.init()
pygame.display.set_mode((1280, 720), pygame.OPENGL | pygame.DOUBLEBUF)
ext = fo.attach(view_size=(1280, 720))

batch = fo.SpriteBatch("player.png", capacity=10_000)
group = batch.spawn(1000, x=640, y=360)

hud_surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
hud = fo.SurfaceLayer(hud_surface)

while True:
    for event in pygame.event.get():
        ...
    ext.clear(0.1, 0.1, 0.1)
    batch.draw()
    hud.update()
    hud.draw()
    pygame.display.flip()
```
## Examples

- [`examples/pygame_interop.py`](https://github.com/Enzo-Azevedo/FastObjects/blob/main/examples/pygame_interop.py) for the
complete, runnable version (click to spawn, D to despawn, pygame-font HUD).

- [`examples/bunnymark.py`](https://github.com/Enzo-Azevedo/FastObjects/blob/main/examples/bunnymark.py) — 100k bouncing bunnies,
  native window, FPS counter.
- [`examples/shapes_input.py`](https://github.com/Enzo-Azevedo/FastObjects/blob/main/examples/shapes_input.py) — shapes + polled
  keyboard/mouse input.

## Development

Install with development dependencies:

```bash
pip install -e ".[dev,bench]"
```

Run the test suite (98 tests, pixel-verified against an offscreen OpenGL
context) with `pytest`, and the benchmark arena with
`python benchmarks/arena/run_all.py`.
