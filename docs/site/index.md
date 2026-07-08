# FastObjects

**The fastest 2D object rendering library for Python.** Sprites and shapes
live in flat NumPy arrays — never one Python object per sprite — and each
batch is drawn with a single instanced OpenGL draw call.

## The numbers

Sprites sustained at 60 fps in the bunnymark arena, same machine
(AMD Radeon RX 580, Python 3.13, 2026-07-07):

| Framework | Sprites @ 60 fps |
|---|---|
| **fastobjects** | **328,213** |
| arcade | 3,795 |
| raylib | 3,795 |
| pygame-ce | 2,530 |
| pyglet | 2,530 |

**86x** the closest competitor. Every number in this documentation comes from
a dated, reproducible entry in
[`benchmarks/RESULTS.md`](https://github.com/Enzo-Azevedo/FastObjects/blob/main/benchmarks/RESULTS.md) —
including the experiments that *lost*.

## Install

```bash
pip install fastobjects
```

## Where to go next

- [Getting Started](getting-started.md) — install and your first program.
- [Sprites & Groups](guide/sprites.md) — batches, vectorized spawn/despawn,
  and the cost model that makes it fast.
- [Shapes](guide/shapes.md) — rectangles, SDF circles, and lines.
- [Window & Input](guide/window-input.md) — the frame loop and polled input.
- [Using inside pygame](guide/interop.md) — pygame owns the window,
  FastObjects owns the objects.
- [Performance](performance.md) — the benchmarks and how to reproduce them.
- [API Reference](api.md) — every public symbol.
