# Sprites & Groups

## The batch

A `SpriteBatch` is a fixed-capacity pool of sprites that share one texture
and are drawn with **one instanced draw call**:

```python
import fastobjects as fo

win = fo.Window(800, 600)
batch = fo.SpriteBatch("player.png", capacity=10_000)
```

- `capacity` is the maximum number of live sprites; exceeding it raises
  `CapacityError` with the exact capacity you need instead.
- The texture is any image Pillow can open. One batch = one texture — if you
  need several images today, create one batch per image (a texture atlas is
  on the roadmap).
- `ctx`/`view_size` are taken from the current window; pass them explicitly
  only for offscreen rendering or tests.

## Spawning — always vectorized

`spawn(n, ...)` creates `n` sprites in one call. Every parameter accepts a
scalar (applied to all) or an array of length `n`:

```python
import numpy as np

rng = np.random.default_rng()
bunnies = batch.spawn(
    5000,
    x=rng.uniform(0, 800, 5000),
    y=100.0,                      # scalar: same for all
    rot=0.0,
    color=(1.0, 1.0, 1.0, 1.0),  # or an (n, 4) array
)
```

The return value is a `SpriteGroup` — one lightweight Python object for the
*whole group*, never one per sprite.

## Groups: views, not copies

A group's properties are NumPy **views** into the batch's storage. Writing
to them is writing to the sprites:

```python
bunnies.pos += velocity * dt          # move all, one array op
bunnies.color = (1.0, 0.2, 0.2, 1.0)  # tint all red
bunnies.rot += 0.5 * dt               # spin all
bunnies[100:200].y = 0.0              # sub-slice: rows 100..199
```

Available properties: `x`, `y`, `w`, `h`, `rot` (1D arrays), `pos` (n, 2),
`size` (n, 2), `color` (n, 4). `len(group)` gives the sprite count;
`group[a:b]` returns a sub-group over the same storage.

!!! note "How uploads work — you pay for change, not existence"
    Every sprite always has all properties, in CPU and GPU memory. What is
    optimized is the **per-frame upload**: positions upload every frame
    (they change in any real app); size, rotation, and color upload only in
    the frames you touch them. The tracking is automatic and conservative —
    *accessing* the property marks its column for upload, so a change can
    never silently not appear on screen.

    One rule: **don't store a property view across frames** and write to it
    later. Re-access it each frame (`group.color[...] = ...`) — the access
    is O(1) and is what keeps the tracking correct.

## Despawning

`despawn(group)` removes a group's sprites, compacts the batch with one
vectorized copy per column, and returns the capacity:

```python
a = batch.spawn(100)
b = batch.spawn(50)
batch.despawn(a)
len(b)          # still 50 — b's handle was relocated automatically
batch.spawn(80)  # a's capacity is available again
```

Surviving handles keep working. The removed group — and any sub-group that
overlaps it — becomes invalid: touching it raises a `RuntimeError` telling
you to spawn again. `batch.clear()` removes everything and invalidates all
handles.

## Multiple images (atlas)

A batch can hold **more than one image** and still draw everything in one call.
Pass a list (selected by index) or a dict (selected by name); FastObjects packs
them into a single texture atlas at creation:

```python
batch = fo.SpriteBatch(["hero.png", "coin.png", "enemy.png"], capacity=10_000)

hero  = batch.spawn(1, x=400, y=300, image=0)
coins = batch.spawn(50, x=xs, y=ys, image=1)        # all coins
mixed = batch.spawn(100, x=xs, y=ys, image=np.arange(100) % 3)  # vectorized

named = fo.SpriteBatch({"hero": "hero.png", "coin": "coin.png"}, capacity=100)
named.spawn(1, image="hero")
```

`spawn(..., image=i)` accepts a scalar or a length-`n` array of indices/names.
When `w`/`h` are left as `None`, each sprite defaults to **its own image's**
pixel size.

**Spritesheet animation** — reassign `group.image` to re-texture a group in
place (still one draw call, `image` is a cold column that only re-uploads when
you change it):

```python
frames = fo.SpriteBatch([f"walk{i}.png" for i in range(8)], capacity=100)
player = frames.spawn(1, x=400, y=300)

@win.frame
def update(dt):
    player.image = (tick // 6) % 8   # advance the animation
    ...
```

The atlas is **static**: built once from the images you pass. All images must
fit in one texture (`GL_MAX_TEXTURE_SIZE`, typically ≥ 8192); if not, you get an
actionable `AtlasOverflowError`. Runtime add/remove is not supported yet. See
[`examples/atlas_animation.py`](https://github.com/Enzo-Azevedo/FastObjects/blob/main/examples/atlas_animation.py).

## A complete example

```python
import numpy as np

import fastobjects as fo

win = fo.Window(800, 600, title="sprites guide")
batch = fo.SpriteBatch("player.png", capacity=5000)

rng = np.random.default_rng(7)
n = 2000
group = batch.spawn(n, x=rng.uniform(0, 800, n), y=rng.uniform(0, 300, n))
vel = rng.uniform(-120, 120, (n, 2)).astype("f4")

@win.frame
def update(dt: float) -> None:
    vel[:, 1] += 980.0 * dt          # gravity
    group.pos += vel * dt
    floor = group.y > 600
    vel[floor, 1] *= -0.85           # bounce
    group.y = np.minimum(group.y, 600)

    win.clear(0.08, 0.08, 0.10)
    win.draw(batch)
    if win.keys[fo.KEY_ESCAPE]:
        win.request_close()

win.run()
```
