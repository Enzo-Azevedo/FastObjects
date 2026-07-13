# Performance

## The bunnymark arena

Every listed library runs the *same* bunnymark — identical physics, timer,
and ramp protocol — in its own process, so rendering is the only variable.
Each uses its documented fast path. Sprites sustained at 60 fps
(AMD Radeon RX 580, Python 3.13, 2026-07-07):

| Framework | Sprites @ 60 fps | avg ms | p99 ms |
|---|---|---|---|
| **fastobjects** | **328,213** | 12.5 | 22.2 |
| arcade | 3,795 | 10.3 | 19.4 |
| raylib | 3,795 | 10.1 | 19.6 |
| pygame-ce | 2,530 | 11.6 | 20.8 |
| pyglet | 2,530 | 10.3 | 17.2 |

## Against the technique's ceiling

A minimal, hand-written `moderngl` renderer (raw instancing, no library, no
rotation, no blend) is the theoretical ceiling for this technique. In a
scalability sweep (800×600, 6×6 rects), FastObjects reaches — and passes —
that ceiling, because it writes contiguous arrays directly while the raw
version pays `astype`/`tobytes` copies per frame:

| Objects | moderngl (raw) | fastobjects | % of ceiling |
|---|---|---|---|
| 1,000 | 1,084 fps | 1,293 fps | 119% |
| 10,000 | 1,025 fps | 1,286 fps | 125% |
| 100,000 | 353 fps | 384 fps | 109% |

## Atlas packing speed

Building a texture atlas is a load-time step. Against
[PyTexturePacker](https://pypi.org/project/PyTexturePacker/) (a pure-Python
MaxRects packer), FastObjects's shelf packing produces an **identically-sized
atlas** while being far faster on same-size images (spritesheets): 30× at 400
images, 77× at 800 — the MaxRects free-rectangle list degenerates on uniform
grids. On mixed-size art the two tie, and FastObjects scales linearly. Full
numbers in
[`benchmarks/RESULTS.md`](https://github.com/Enzo-Azevedo/FastObjects/blob/main/benchmarks/RESULTS.md).
(patlas was dropped from the comparison: it has no wheels past Python 3.9 and
its sdist doesn't build.)

## Text throughput

Text is glyph-atlas sprites in one draw call. Drawing many short strings,
FastObjects sustains **145,873 strings @ 60 fps** — 3.4× pyglet (which also
uses a glyph atlas, but per-label vertex lists) and 38× pygame (a new surface
per string).

Against the canonical freetype-py + PyOpenGL renderer (one GL texture and one
draw call per glyph — the learnopengl.com tutorial technique), with the same
`.ttf` on both sides, FastObjects sustains the same 145,873 strings while the
per-glyph renderer cannot hold 60 fps at even 500 strings (~276 ms/frame):
all text here is a single instanced draw call. Loading a `.ttf` costs the
same as the built-in font at runtime; building the glyph atlas is a one-time
~120 ms load step (see `benchmarks/RESULTS.md` for the load-time breakdown).

## Reproduce it

```bash
# The full arena (5 libraries, saves a dated section to RESULTS.md)
python benchmarks/arena/run_all.py --save --label "my-run"

# The scalability sweep vs the raw-moderngl ceiling
python benchmarks/benchmark_2d.py --libs moderngl fastobjects
```

!!! warning "Run benchmarks in the foreground"
    Windows throttles OpenGL presentation for windows owned by background
    processes (~10 fps), which silently ruins GL benchmark numbers. pygame's
    software path is unaffected, so the skew is easy to miss. Always run
    these in the foreground.

## The philosophy: no decision without a benchmark

FastObjects takes no performance decision by opinion — every candidate
technique must win on measured numbers, and the results (winners *and*
losers) are recorded with date and hardware in
[`benchmarks/RESULTS.md`](https://github.com/Enzo-Azevedo/FastObjects/blob/main/benchmarks/RESULTS.md).
Examples from that log:

- **Buffer upload strategy** — plain `write` vs `orphan` vs double-buffer:
  no reproducible winner, so the simplest (plain `write`) was kept.
- **SoA vs AoS + quantization** — structure-of-arrays with one VBO per
  column beat interleaved arrays 4x on a typical frame; quantizing cold
  columns to u8/f16 *lost* (the CPU conversion cost more than the upload it
  saved) and was rejected.

## Practical tips

- **One batch per texture.** Sprites in a batch share a texture and a draw
  call; group your art accordingly.
- **Vectorize.** Update whole groups with array math (`group.pos += v * dt`),
  never a Python loop over sprites.
- **Prefer `despawn` to clear-and-respawn.** `despawn` frees capacity with
  one vectorized compaction and keeps other handles valid.
- **Touch cold columns only when they change.** Positions upload every
  frame anyway; re-assigning color/size/rotation every frame when they are
  static wastes uploads (still correct, just slower).
