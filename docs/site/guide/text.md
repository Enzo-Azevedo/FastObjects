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

## Custom fonts

`Font` takes the font first, pygame-style — a `.ttf`/`.otf` path or the name
of an installed system font. `None` (the default) uses Pillow's built-in font.

```python
hud = fo.Font("assets/PressStart2P.ttf", 16)
system = fo.Font("arial.ttf", 24)          # searched in the system font dirs
```

## Character sets

The atlas rasterizes one fixed set of characters, chosen at construction:

```python
fo.Font("arial.ttf", 24)                            # "latin" (default): ASCII + Latin-1
fo.Font("arial.ttf", 24, charset="cyrillic")        # Ѐ-џ only — no ASCII
fo.Font("arial.ttf", 24, charset=("latin", "greek", "cyrillic"))  # mixed text
fo.Font("arial.ttf", 24, chars="0123456789/:")      # full control (wins over charset)
```

Presets: `"ascii"`, `"latin"`, `"latin-ext"`, `"greek"`, `"cyrillic"`.
Presets are independent — combine them in a tuple for mixed text. A character
the *font file* doesn't cover renders as that font's tofu box; a character
outside the *atlas charset* is skipped (drawn as a space).

## A complete example

See [`examples/text_hud.py`](https://github.com/Enzo-Azevedo/FastObjects/blob/main/examples/text_hud.py)
(static labels + a live FPS counter).
