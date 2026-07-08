# Window & Input

## The window

```python
import fastobjects as fo

win = fo.Window(1280, 720, title="my game", vsync=False, visible=True)
```

`Window` opens a native GLFW window with an OpenGL 3.3 core context. Creating
it registers it as the *current window*: batches created afterwards attach to
it automatically. `vsync` is off by default (benchmarks demand it); pass
`vsync=True` to cap at the monitor's refresh rate. `visible=False` gives an
offscreen-style window, used by the test suite.

Coordinates everywhere are **pixels, y pointing down**, origin at the
top-left.

## The frame loop

```python
@win.frame
def update(dt: float) -> None:
    ...                       # your per-frame logic
    win.clear(0.1, 0.1, 0.1)  # background color
    win.draw(batch_a, batch_b)  # one draw call per batch, in order

win.run()
```

- `@win.frame` registers the update function (registering again replaces it).
- `win.run()` loops until the window closes: poll events → measure real
  `dt` (seconds) → call your function → swap buffers.
- `win.request_close()` ends the loop from inside the update — the usual
  exit path (`if win.keys[fo.KEY_ESCAPE]: win.request_close()`).
- Prefer manual control? `poll()`, `clear()`, `swap()`, and `should_close`
  are public — the benchmark arena uses exactly that loop.
- Using a window after `close()` raises a clear `RuntimeError` (instead of
  crashing the interpreter).

## Polled input

Input is polled state, read inside the frame function — no callbacks to
wire:

```python
@win.frame
def update(dt: float) -> None:
    if win.keys[fo.KEY_RIGHT]:          # held down right now?
        player.x += 200 * dt
    if win.mouse.left:                   # left button held?
        cursor.x = win.mouse.x           # position in pixels, y down
        cursor.y = win.mouse.y
```

- `win.keys[keycode]` — `True` while the key is held. Keycodes are the glfw
  constants re-exported as `fo.KEY_*` (e.g. `fo.KEY_SPACE`, `fo.KEY_W`,
  `fo.KEY_ESCAPE`).
- `win.mouse` — `.x`, `.y` (pixels), `.left`, `.right`, `.middle` (bools).

## A complete example

This is [`examples/shapes_input.py`](https://github.com/Enzo-Azevedo/FastObjects/blob/main/examples/shapes_input.py)
in miniature:

```python
import fastobjects as fo

win = fo.Window(800, 600, title="window & input")
shapes = fo.ShapeBatch(capacity=8)
cursor = shapes.circles(1, x=400.0, y=300.0, radius=16.0,
                        color=(1.0, 0.7, 0.1, 0.9))
player = shapes.rects(1, x=400.0, y=300.0, w=48.0, h=48.0,
                      color=(0.2, 0.9, 0.4, 1.0))

@win.frame
def update(dt: float) -> None:
    cursor.x = win.mouse.x
    cursor.y = win.mouse.y
    if win.keys[fo.KEY_RIGHT]:
        player.x += 300 * dt
    if win.keys[fo.KEY_LEFT]:
        player.x -= 300 * dt

    win.clear(0.08, 0.08, 0.10)
    win.draw(shapes)
    if win.keys[fo.KEY_ESCAPE]:
        win.request_close()

win.run()
```
