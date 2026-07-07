# FastObjects

The fastest 2D object rendering library for Python.

FastObjects renders thousands of 2D sprites and shapes per frame with a
single OpenGL draw call per batch. State lives in flat NumPy arrays instead
of per-object Python instances, so you mutate positions with array slicing
and let the GPU do the rest.

## Installation

```bash
pip install fastobjects
```

## Quick start

```python
import fastobjects as fo

win = fo.Window(800, 600, title="FastObjects demo")

sprites = fo.SpriteBatch("player.png", capacity=1000)
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
  per-object overhead.
- `ShapeBatch` works the same way for rectangles, circles, and lines
  (`batch.rects(...)`, `batch.circles(...)`, `batch.lines(...)`), useful for
  debug overlays or non-textured geometry.
- `win.draw(*batches)` issues one draw call per batch, in the order given.

## Why it's fast

FastObjects is written in Python, but the hot path isn't: sprite/shape state
lives in flat NumPy arrays, and each `batch.draw()` uploads the whole array
and issues a **single OpenGL draw call** (via `moderngl`) for the entire
batch — no per-object Python loop, no per-object GPU call. The interpreter
overhead that usually kills naive Python renderers never touches the
per-sprite path.

## Benchmarks

Sprites sustained at 60 fps, measured on the same machine (AMD Radeon RX 580,
Python 3.13) against other Python rendering libraries — see
[`benchmarks/RESULTS.md`](benchmarks/RESULTS.md) for methodology and full
history:

| Framework | Sprites @ 60 fps |
|---|---|
| **fastobjects** | **218,809** |
| arcade | 5,692 |
| raylib | 5,692 |
| pyglet | 3,795 |
| pygame-ce | 1,687 |

Note: raylib and pygame-ce numbers above reflect a specific run in that
history file — check [`benchmarks/RESULTS.md`](benchmarks/RESULTS.md) for the full, dated series and
hardware details before quoting a number as "current".

## Development

Install with development dependencies:

```bash
pip install -e ".[dev,bench]"
```
