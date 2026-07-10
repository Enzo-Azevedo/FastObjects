# Text

FastObjects draws text as sprites from a **glyph atlas** — each character is a
textured quad, and a whole `TextBatch` draws in one call. Text is built on the
same atlas/renderer as sprites, so it's fast and batched.

## A font and a text batch

```python
import fastobjects as fo

win = fo.Window(800, 600)
font = fo.Font(size=28)              # built-in scalable font
labels = fo.TextBatch(font, capacity=500)

labels.write("Hello, FastObjects!", x=20, y=20)
labels.write("Acentos: ação!", x=20, y=60, color=(0.6, 0.9, 1.0, 1.0))
```

- `Font(size)` rasterizes a character set into a glyph atlas once. The default
  character set covers printable ASCII **and Latin-1** (accents like á, ç, ã, é
  work out of the box). Pass `chars="..."` for a custom set.
- `TextBatch(font, capacity)` — `capacity` is the maximum number of glyphs
  across all live `write`s.
- `write(text, x, y, color=(1,1,1,1), anchor="topleft")` returns a
  `SpriteGroup` over the glyph quads, so you can move or recolor the whole
  string: `label.pos += (0, 5)`, `label.color = (1, 0, 0, 1)`.

Newlines (`\n`) start a new line; `anchor="center"` centers the text block on
`(x, y)`.

## Dynamic text (score, FPS)

For text that changes every frame, `clear()` and `write()` again — no per-string
surface, no reallocation:

```python
hud = fo.TextBatch(font, capacity=200)

@win.frame
def update(dt):
    hud.clear()
    hud.write(f"Score: {score}", x=20, y=20)
    win.clear(0.1, 0.1, 0.1)
    win.draw(hud)
```

## Measuring

`font.measure(text)` returns the `(width, height)` of a string's block without
drawing — useful for positioning or centering yourself:

```python
w, h = font.measure("Game Over")
label.write("Game Over", x=(800 - w) / 2, y=(600 - h) / 2)
```

## A complete example

See [`examples/text_hud.py`](https://github.com/Enzo-Azevedo/FastObjects/blob/main/examples/text_hud.py)
(static labels + a live FPS counter).

!!! note "0.6.0 uses the built-in font"
    This release renders with Pillow's built-in scalable font. Loading your own
    `.ttf`/`.otf` files and text encoding/formatting options are planned for
    0.6.1. Characters outside the font's character set are skipped (they advance
    like a space).
