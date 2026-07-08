# Shapes

`ShapeBatch` renders untextured primitives — rectangles, circles, and
lines — with the same model as sprites: NumPy state, groups, and **one
instanced draw call for the whole batch**, mixed shapes included.

```python
import fastobjects as fo

win = fo.Window(800, 600)
shapes = fo.ShapeBatch(capacity=1000)

bars = shapes.rects(3, x=[100.0, 200.0, 300.0], y=500.0, w=40.0, h=120.0,
                    color=(0.2, 0.8, 0.3, 1.0))
dots = shapes.circles(50, x=..., y=..., radius=6.0)
grid = shapes.lines(2, x1=[0.0, 400.0], y1=[300.0, 0.0],
                    x2=[800.0, 400.0], y2=[300.0, 600.0], width=1.0)
```

All three factories are vectorized like `spawn` (scalars or length-`n`
arrays) and return the same `SpriteGroup` type — `bars.rot += 0.1` and
`shapes.despawn(dots)` work exactly as with sprites.

## The three primitives

**Rectangles** — `rects(n, x, y, w, h, rot=0.0, color=...)`. Position is
the center; `rot` is in radians.

**Circles** — `circles(n, x, y, radius, color=...)`. Rendered as a signed
distance field in the fragment shader with ~1px anti-aliased edges — crisp
at any size, no polygon segments. Internally the bounding box stores the
diameter, so `group.size` reads/writes `2 * radius`.

**Lines** — `lines(n, x1, y1, x2, y2, width=1.0, color=...)`. Lines are API
sugar: the endpoints are converted (vectorized) into a rotated rectangle
with the given width. Moving a line afterwards means moving its center
(`group.pos`) or recreating it.

## Mixing shapes

Different primitives share the same batch and the same draw call:

```python
shapes.rects(1, x=400.0, y=100.0, w=200.0, h=20.0, color=(0.9, 0.2, 0.2, 1.0))
shapes.circles(1, x=400.0, y=300.0, radius=50.0, color=(0.2, 0.5, 0.9, 0.8))
shapes.draw()   # one draw call for both
```

Alpha blending matches the sprites (straight alpha).

## A complete example

```python
import fastobjects as fo

win = fo.Window(800, 600, title="shapes guide")
shapes = fo.ShapeBatch(capacity=64)

spinner = shapes.rects(1, x=400.0, y=300.0, w=160.0, h=24.0,
                       color=(1.0, 0.6, 0.1, 1.0))
shapes.circles(1, x=400.0, y=300.0, radius=8.0, color=(1.0, 1.0, 1.0, 1.0))

@win.frame
def update(dt: float) -> None:
    spinner.rot += 1.5 * dt
    win.clear(0.08, 0.08, 0.10)
    win.draw(shapes)
    if win.keys[fo.KEY_ESCAPE]:
        win.request_close()

win.run()
```
