# Getting Started

## Install

```bash
pip install fastobjects
```

Requirements: Python ≥ 3.11 and a GPU/driver with OpenGL 3.3 core (any
desktop GPU from the last decade). Core dependencies are just `numpy`,
`moderngl`, `glfw`, and `pillow`.

For development (tests, linter, competitor benchmarks):

```bash
pip install "fastobjects[dev,bench]"
```

## Your first program

Save any image as `player.png` next to the script, then run:

```python
import numpy as np

import fastobjects as fo

win = fo.Window(800, 600, title="My first FastObjects program")

# One batch = one texture = one draw call.
sprites = fo.SpriteBatch("player.png", capacity=2000)

# Vectorized spawn: 1,000 sprites in one call, positions from arrays.
rng = np.random.default_rng()
group = sprites.spawn(
    1000,
    x=rng.uniform(0, 800, 1000),
    y=rng.uniform(0, 600, 1000),
)
velocity = rng.uniform(-100, 100, (1000, 2)).astype("f4")

@win.frame
def update(dt: float) -> None:
    # Physics on the group's NumPy views — no per-sprite loop.
    group.pos += velocity * dt

    win.clear(0.1, 0.1, 0.1)
    win.draw(sprites)

    if win.keys[fo.KEY_ESCAPE]:
        win.request_close()

win.run()
```

What just happened:

1. `fo.Window(...)` opened a native window with an OpenGL 3.3 core context
   and registered itself as the *current window* — batches created after it
   attach to it automatically.
2. `sprites.spawn(1000, x=..., y=...)` created 1,000 sprites **in one
   vectorized call** and returned a `SpriteGroup` — a lightweight handle
   whose properties are NumPy views into the batch.
3. `group.pos += velocity * dt` moved all 1,000 sprites with one array
   operation. This is the FastObjects idiom: update *groups*, never
   individual sprites in a Python loop.
4. `win.run()` drove the frame loop, calling your `@win.frame` function
   with the real `dt` each frame.

## Next steps

- Coordinates are **pixels with y pointing down** (origin at the top-left),
  like most 2D tools.
- Read [Sprites & Groups](guide/sprites.md) for despawn, colors, rotation,
  and the upload cost model.
- Already have a pygame project? See
  [Using inside pygame](guide/interop.md).
