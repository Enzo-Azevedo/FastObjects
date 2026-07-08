# API Reference

Everything importable from `fastobjects` (imported as `fo`). Coordinates are
pixels, y pointing down.

## `Window`

```python
Window(width, height, title="fastobjects", vsync=False, visible=True)
```

Native GLFW window with an OpenGL 3.3 core context. Registers itself as the
current window on creation. Raises `RuntimeError` if GLFW or the GL context
cannot be created.

| Member | Description |
|---|---|
| `frame(fn)` | Decorator; registers `fn(dt: float)` as the per-frame update. Registering again replaces it. |
| `run()` | Runs the loop until close: poll → `dt` → update → swap. Raises `RuntimeError` if no frame is registered. |
| `draw(*batches)` | Calls `.draw()` on each drawable in order. |
| `clear(r, g, b)` | Clears the framebuffer (values 0–1). |
| `request_close()` | Ends `run()` from inside the update. |
| `should_close` | `bool` property — window close requested. |
| `poll()` / `swap()` | Manual event poll / buffer swap (for hand-written loops). |
| `close()` | Destroys the window; deregisters it if current. |
| `keys` | `Keyboard`: `keys[fo.KEY_X] -> bool`. |
| `mouse` | `Mouse`: `.x`, `.y`, `.left`, `.right`, `.middle`. |
| `ctx`, `width`, `height` | moderngl context and size. |

Using `run`/`swap`/`request_close`/`should_close` after `close()` raises
`RuntimeError`.

## `SpriteBatch`

```python
SpriteBatch(texture_path, capacity, *, ctx=None, view_size=None)
```

Fixed-capacity pool of textured sprites drawn in one instanced call.
`ctx`/`view_size` default to the current window. Raises `ValueError` if
`capacity <= 0`, `FileNotFoundError` (with the resolved path) if the texture
is missing.

| Member | Description |
|---|---|
| `spawn(n, x=0, y=0, w=None, h=None, rot=0, color=(1,1,1,1))` | Creates `n` sprites, returns a `SpriteGroup`. Each arg is a scalar or length-`n` array; `w`/`h` default to the texture size. Raises `ValueError` (n<0) or `CapacityError`. |
| `despawn(group)` | Removes the group, compacts storage, frees capacity, relocates surviving handles. Raises `ValueError` (foreign batch) / `RuntimeError` (already removed). |
| `clear()` | Removes all sprites; invalidates all handles. |
| `draw()` | Uploads changed columns + positions, one instanced draw call. |
| `count` | Live sprite count. |
| `pos`, `size`, `rot`, `color` | Batch-wide NumPy views (capacity rows). Accessing the cold ones marks them for upload. |

## `ShapeBatch`

```python
ShapeBatch(capacity, *, ctx=None, view_size=None)
```

Like `SpriteBatch` but for untextured primitives; mixed shapes share one
draw call. Same `despawn`/`clear`/`draw`/`count`/`pos`/`size`/`rot`/`color`.

| Factory | Description |
|---|---|
| `rects(n, x=0, y=0, w=10, h=10, rot=0, color=(1,1,1,1))` | Rectangles (position = center). Returns `SpriteGroup`. |
| `circles(n, x=0, y=0, radius=5, color=(1,1,1,1))` | SDF circles; stores `w=h=2*radius`. Returns `SpriteGroup`. |
| `lines(n, x1, y1, x2, y2, width=1, color=(1,1,1,1))` | Lines as rotated rects. Returns `SpriteGroup`. |

All args are scalars or length-`n` arrays; same `ValueError`/`CapacityError`
guards.

## `SpriteGroup`

A handle over a contiguous slice of a batch — one object per group, never
per sprite. Returned by `spawn`/`rects`/`circles`/`lines`. Properties are
NumPy views into the batch.

| Member | Description |
|---|---|
| `x`, `y`, `w`, `h`, `rot` | 1D views (length = group size). |
| `pos` (n,2), `size` (n,2), `color` (n,4) | Block views. |
| `slice` | Absolute slice in the batch. |
| `len(group)` | Sprite count. |
| `group[a:b]` | Sub-group over the same storage (step must be 1). |

Reading or writing size/rot/color marks that column for upload (conservative
— never a silent no-show). After `despawn`/`clear`, any access raises
`RuntimeError`. Do not store a property view across frames; re-access it.

## `SurfaceLayer`

```python
SurfaceLayer(surface, *, ctx=None, view_size=None)
```

Composites a `pygame.Surface` (classic CPU drawing) as a textured quad.
Fixed size at creation; raises `ValueError` for a zero-size surface.

| Member | Description |
|---|---|
| `update()` | Uploads the surface to the GPU (one upload). Raises `ImportError` if pygame is missing, `ValueError` if the surface changed size. |
| `draw()` | Composites it (one draw call). |

## `attach` / `ExternalWindow`

```python
attach(view_size) -> ExternalWindow
```

Connects FastObjects to the host's current OpenGL context and registers an
`ExternalWindow` as current. Call once per host window. Raises `RuntimeError`
if there is no active GL context.

`ExternalWindow` exposes only `.ctx`, `.width`, `.height`, `.clear(r, g, b)`,
and `.close()` — the host owns the loop, input, and buffer swap.

## Constants & errors

- `fo.KEY_*` — glfw key codes (`KEY_SPACE`, `KEY_ESCAPE`, `KEY_A`, arrows,
  etc.).
- `fo.MOUSE_BUTTON_*` — glfw mouse button codes.
- `CapacityError` — raised when a spawn exceeds a batch's capacity; the
  message states the capacity you need.
