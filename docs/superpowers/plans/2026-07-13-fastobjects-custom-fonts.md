# Fontes Customizadas + Charsets Unicode (0.6.1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `fo.Font` aceita fontes `.ttf`/`.otf` (assinatura estilo pygame) e charsets Unicode via presets nomeados, vencendo freetype-py + PyOpenGL em throughput.

**Architecture:** Só a origem da fonte e a seleção de caracteres mudam em `font.py`; o pipeline getmask → atlas → layout → TextBatch fica intacto. Benchmark novo implementa a técnica canônica do learnopengl (textura + draw call por glifo) como baseline a ser vencida.

**Tech Stack:** Pillow (`ImageFont.truetype`), numpy; benchmark: freetype-py + PyOpenGL + glfw (só no extra `[bench]`).

## Global Constraints

- Deps de runtime continuam **só** moderngl, glfw, numpy, pillow (`pyproject.toml` `dependencies` inalterado; freetype-py/PyOpenGL só em `[project.optional-dependencies] bench`).
- Python ≥ 3.11; OpenGL 3.3 core.
- Commits **sem** trailer `Co-Authored-By` (regra do projeto).
- Arquivos sempre via ferramentas Write/Edit (nunca `Set-Content -Encoding utf8` — BOM quebra pyproject/py).
- Benchmarks GL rodam em **foreground** (Windows limita GL de janelas em background a ~10fps).
- Gate da fase: fastobjects-ttf > freetype-gl em strings @ 60fps; senão, parar e repensar.
- Branch de trabalho: `custom-fonts` a partir de `main`.

---

### Task 1: Presets de charset

**Files:**
- Modify: `fastobjects/font.py` (linhas 12-15: `_DEFAULT_CHARS` → `_CHARSETS` + `_resolve_charset`; assinatura do `__init__`)
- Test: `tests/test_font.py`

**Interfaces:**
- Produces: `Font(source=None, size=24, *, chars=None, charset="latin")` — `charset: str | tuple[str, ...]`; `_CHARSETS: dict[str, str]` (usado pelo bench da Task 3). Nesta task `source` ainda não é usado (Task 2); apenas entra na assinatura já na forma final, ignorado se None.

- [ ] **Step 1: Testes falhando** — adicionar a `tests/test_font.py`:

```python
def test_charset_preset_is_independent():
    f = Font(charset="cyrillic")
    assert "Д" in f.glyphs
    assert "A" not in f.glyphs  # presets não incluem ASCII implicitamente


def test_charset_combination():
    f = Font(charset=("latin", "greek"))
    assert "A" in f.glyphs and "é" in f.glyphs and "Ω" in f.glyphs


def test_charset_invalid_name_raises():
    with pytest.raises(ValueError, match="charset"):
        Font(charset="klingon")


def test_chars_overrides_charset():
    f = Font(chars="AB", charset="cyrillic")
    assert "A" in f.glyphs and "Д" not in f.glyphs
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_font.py -v`
Expected: os 4 novos FALHAM (`TypeError: unexpected keyword argument 'charset'`); os 8 antigos passam.

- [ ] **Step 3: Implementação** — em `fastobjects/font.py`, substituir `_DEFAULT_CHARS` por:

```python
_ASCII = "".join(chr(c) for c in range(0x20, 0x7F))
_CHARSETS: dict[str, str] = {
    "ascii": _ASCII,
    # ASCII + Latin-1 imprimível: o padrão (cobre acentos do português)
    "latin": _ASCII + "".join(chr(c) for c in range(0xA1, 0x100)),
    # latin + Latin Extended-A (Ā-ſ: polonês, tcheco, turco...)
    "latin-ext": _ASCII
    + "".join(chr(c) for c in range(0xA1, 0x180)),
    # grego moderno imprimível (pula code points reservados)
    "greek": "".join(
        chr(c) for c in range(0x386, 0x3CF) if c not in (0x38B, 0x38D, 0x3A2)
    ),
    # cirílico Ѐ-џ + Ґґ (ucraniano)
    "cyrillic": "".join(chr(c) for c in range(0x400, 0x460)) + "Ґґ",
}


def _resolve_charset(charset: str | tuple[str, ...]) -> str:
    names = (charset,) if isinstance(charset, str) else tuple(charset)
    parts: list[str] = []
    for name in names:
        if name not in _CHARSETS:
            raise ValueError(
                f"charset desconhecido: {name!r} — válidos: {sorted(_CHARSETS)}"
            )
        parts.append(_CHARSETS[name])
    return "".join(parts)
```

E o começo do `__init__` vira (docstring atualizada junto — `charset` documentado como presets independentes, combináveis por tupla, vencido por `chars`):

```python
    def __init__(
        self,
        source: str | None = None,
        size: int = 24,
        *,
        chars: str | None = None,
        charset: str | tuple[str, ...] = "latin",
    ) -> None:
        if chars is None:
            chars = _resolve_charset(charset)
        if not chars:
            raise ValueError("chars não pode ser vazio — passe ao menos um caractere.")
        font = ImageFont.load_default(size=size)  # source usado na Task 2
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv\Scripts\python -m pytest tests/test_font.py tests/test_text.py -v`
Expected: 12 + 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add fastobjects/font.py tests/test_font.py
git commit -m "feat: charset presets (ascii/latin/latin-ext/greek/cyrillic) na Font"
```

---

### Task 2: Fonte `.ttf`/`.otf` via `source`

**Files:**
- Modify: `fastobjects/font.py` (o `font = ImageFont.load_default(...)` da Task 1)
- Test: `tests/test_font.py`, `tests/test_text.py`

**Interfaces:**
- Consumes: assinatura `Font(source, size, *, chars, charset)` da Task 1.
- Produces: `Font("caminho.ttf", 24)` funcional; atributo `Font.source: str | None`. `Font(None, 16)` ≡ fonte embutida (usado pelo bench na Task 3).

- [ ] **Step 1: Testes falhando** — em `tests/test_font.py`, adicionar no topo `from pathlib import Path` e:

```python
_ARIAL = Path("C:/Windows/Fonts/arial.ttf")
needs_arial = pytest.mark.skipif(not _ARIAL.exists(), reason="arial.ttf ausente")


@needs_arial
def test_ttf_font_builds_and_lays_out():
    f = Font(str(_ARIAL), 24)
    assert f.source == str(_ARIAL)
    assert f.glyphs["A"].uv is not None
    centers, _, _, block = f.layout("Olá")
    assert centers.shape[0] == 3 and block[0] > 0


@needs_arial
def test_ttf_covers_wide_charsets():
    f = Font(str(_ARIAL), 24, charset=("latin", "cyrillic"))
    assert f.glyphs["Д"].uv is not None


def test_missing_font_raises_actionable():
    with pytest.raises(ValueError, match="fonte"):
        Font("nao-existe-esta-fonte.ttf", 24)


def test_default_source_is_none():
    assert Font(size=16).source is None
```

E em `tests/test_text.py` (já importa `Font`, `TextBatch`, `pytest`, `np`; adicionar `from pathlib import Path`):

```python
@pytest.mark.skipif(
    not Path("C:/Windows/Fonts/arial.ttf").exists(), reason="arial.ttf ausente"
)
def test_ttf_text_draws(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    font = Font("C:/Windows/Fonts/arial.ttf", 32)
    txt = TextBatch(font, capacity=100, ctx=ctx, view_size=(128, 64))
    txt.write("I", x=20.0, y=10.0)
    txt.draw()
    px = read(fbo)
    assert px[:, :, :3].max() > 200
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_font.py tests/test_text.py -v`
Expected: novos FALHAM (`AttributeError: source` / `TypeError` positional); antigos passam.

- [ ] **Step 3: Implementação** — em `font.py`, trocar a linha `font = ImageFont.load_default(size=size)  # source usado na Task 2` por:

```python
        if source is None:
            font = ImageFont.load_default(size=size)
        else:
            try:
                font = ImageFont.truetype(str(source), size=size)
            except OSError as e:
                raise ValueError(
                    f"fonte não encontrada: {source!r}. Passe um caminho .ttf/.otf "
                    "completo ou o nome de uma fonte instalada (ex.: 'arial.ttf')."
                ) from e
        self.source = None if source is None else str(source)
```

Atualizar a docstring da classe: `source` (None = embutida do Pillow; caminho ou nome de fonte do sistema), assinatura pygame-like, nota do tofu para caractere sem cobertura na fonte.

- [ ] **Step 4: Suíte inteira**

Run: `.venv\Scripts\python -m pytest -q`
Expected: 136 passed (131 + 5 novos). `ruff check .` limpo.

- [ ] **Step 5: Commit**

```bash
git add fastobjects/font.py tests/test_font.py tests/test_text.py
git commit -m "feat: Font aceita .ttf/.otf - Font(source, size) estilo pygame"
```

---

### Task 3: Benchmark vs freetype-py + PyOpenGL (gate)

**Files:**
- Create: `benchmarks/text/bench_freetype_gl.py`, `benchmarks/text/bench_font_build.py`
- Modify: `benchmarks/text/bench_fastobjects.py` (argparse `--font/--name`), `benchmarks/text/run_all.py` (lista `BENCHES` com args), `pyproject.toml` (extra `bench` += `freetype-py`, `PyOpenGL`), `benchmarks/RESULTS.md` (via `--save` + seção load-time)

**Interfaces:**
- Consumes: `Font(source, size)` (Task 2), `_CHARSETS` (Task 1), `common.py` da arena (`WIDTH=1280, HEIGHT=720, SEED, WARMUP_FRAMES=30, MEASURE_FRAMES=120, FrameTimer, run_ramp(name, trial)`).
- Produces: números datados em `RESULTS.md`; decisão do gate.

- [ ] **Step 1: Instalar deps de bench**

Run: `.venv\Scripts\pip install freetype-py PyOpenGL`
E em `pyproject.toml`, adicionar `"freetype-py"`, `"PyOpenGL"` à lista do extra `bench`.

- [ ] **Step 2: `bench_fastobjects.py` ganha `--font/--name`** — adicionar `import argparse` e no `main()`:

```python
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font", default=None)
    parser.add_argument("--name", default="fastobjects")
    args = parser.parse_args()

    win = Window(WIDTH, HEIGHT, f"text: {args.name}", vsync=False)
    font = Font(args.font, size=16)
```

e no final `result = run_ramp(args.name, trial)`.

- [ ] **Step 3: `bench_freetype_gl.py`** — técnica canônica (learnopengl "Text Rendering"): uma textura GL_RED por glifo, um quad atualizado por `glBufferSubData` e um draw call **por caractere**:

```python
"""Texto: freetype-py + PyOpenGL (canônico: textura e draw call por glifo)."""

import json
import sys
from pathlib import Path

import freetype
import glfw
import numpy as np
from OpenGL import GL

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "arena"))

from common import (  # noqa: E402
    HEIGHT,
    MEASURE_FRAMES,
    SEED,
    WARMUP_FRAMES,
    WIDTH,
    FrameTimer,
    run_ramp,
)

FONT = "C:/Windows/Fonts/arial.ttf"
SIZE = 16

VS = """#version 330 core
layout (location = 0) in vec4 vertex;  // xy=pos px, zw=uv
out vec2 uv;
uniform vec2 screen;
void main() {
    gl_Position = vec4(vertex.x / screen.x * 2.0 - 1.0,
                       1.0 - vertex.y / screen.y * 2.0, 0.0, 1.0);
    uv = vertex.zw;
}
"""
FS = """#version 330 core
in vec2 uv;
out vec4 color;
uniform sampler2D glyph;
uniform vec3 text_color;
void main() { color = vec4(text_color, texture(glyph, uv).r); }
"""


def compile_program() -> int:
    def shader(src: str, kind) -> int:
        s = GL.glCreateShader(kind)
        GL.glShaderSource(s, src)
        GL.glCompileShader(s)
        if not GL.glGetShaderiv(s, GL.GL_COMPILE_STATUS):
            raise RuntimeError(GL.glGetShaderInfoLog(s).decode())
        return s

    prog = GL.glCreateProgram()
    GL.glAttachShader(prog, shader(VS, GL.GL_VERTEX_SHADER))
    GL.glAttachShader(prog, shader(FS, GL.GL_FRAGMENT_SHADER))
    GL.glLinkProgram(prog)
    if not GL.glGetProgramiv(prog, GL.GL_LINK_STATUS):
        raise RuntimeError(GL.glGetProgramInfoLog(prog).decode())
    return prog


def load_glyphs(chars: str) -> dict:
    """Uma textura GL_RED por glifo — exatamente como no tutorial."""
    face = freetype.Face(FONT)
    face.set_pixel_sizes(0, SIZE)
    GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
    glyphs = {}
    for ch in chars:
        face.load_char(ch)
        g = face.glyph
        w, h = g.bitmap.width, g.bitmap.rows
        tex = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D, 0, GL.GL_RED, w, h, 0,
            GL.GL_RED, GL.GL_UNSIGNED_BYTE,
            bytes(g.bitmap.buffer) if w and h else None,
        )
        for p in (GL.GL_TEXTURE_WRAP_S, GL.GL_TEXTURE_WRAP_T):
            GL.glTexParameteri(GL.GL_TEXTURE_2D, p, GL.GL_CLAMP_TO_EDGE)
        for p in (GL.GL_TEXTURE_MIN_FILTER, GL.GL_TEXTURE_MAG_FILTER):
            GL.glTexParameteri(GL.GL_TEXTURE_2D, p, GL.GL_LINEAR)
        glyphs[ch] = (tex, w, h, g.bitmap_left, g.bitmap_top, g.advance.x >> 6)
    return glyphs


def main() -> None:
    if not glfw.init():
        sys.exit("glfw.init falhou")
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    win = glfw.create_window(WIDTH, HEIGHT, "text: freetype-gl", None, None)
    glfw.make_context_current(win)
    glfw.swap_interval(0)

    prog = compile_program()
    GL.glUseProgram(prog)
    GL.glUniform2f(GL.glGetUniformLocation(prog, "screen"), WIDTH, HEIGHT)
    GL.glUniform3f(GL.glGetUniformLocation(prog, "text_color"), 0.9, 0.9, 0.9)
    GL.glEnable(GL.GL_BLEND)
    GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)

    vao = GL.glGenVertexArrays(1)
    GL.glBindVertexArray(vao)
    vbo = GL.glGenBuffers(1)
    GL.glBindBuffer(GL.GL_ARRAY_BUFFER, vbo)
    GL.glBufferData(GL.GL_ARRAY_BUFFER, 6 * 4 * 4, None, GL.GL_DYNAMIC_DRAW)
    GL.glEnableVertexAttribArray(0)
    GL.glVertexAttribPointer(0, 4, GL.GL_FLOAT, GL.GL_FALSE, 0, None)

    glyphs = load_glyphs("Item 0123456789")

    def draw_string(s: str, x: float, y: float) -> None:
        for ch in s:
            tex, w, h, left, top, adv = glyphs[ch]
            if w and h:
                x0, y0 = x + left, y - top
                quad = np.array(
                    [
                        [x0, y0 + h, 0.0, 1.0],
                        [x0 + w, y0, 1.0, 0.0],
                        [x0, y0, 0.0, 0.0],
                        [x0, y0 + h, 0.0, 1.0],
                        [x0 + w, y0 + h, 1.0, 1.0],
                        [x0 + w, y0, 1.0, 0.0],
                    ],
                    dtype="f4",
                )
                GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
                GL.glBufferSubData(GL.GL_ARRAY_BUFFER, 0, quad.nbytes, quad)
                GL.glDrawArrays(GL.GL_TRIANGLES, 0, 6)
            x += adv

    def trial(n: int) -> tuple[float, float]:
        rng = np.random.default_rng(SEED)
        xs = rng.uniform(0, WIDTH - 100, n)
        ys = rng.uniform(16, HEIGHT, n)
        strings = [f"Item {i:05d}" for i in range(n)]
        timer = FrameTimer()
        for frame in range(WARMUP_FRAMES + MEASURE_FRAMES):
            glfw.poll_events()
            if frame >= WARMUP_FRAMES:
                timer.begin()
            GL.glClearColor(0.1, 0.1, 0.12, 1.0)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT)
            for i in range(n):
                draw_string(strings[i], xs[i], ys[i])
            glfw.swap_buffers(win)
            if frame >= WARMUP_FRAMES:
                timer.end()
        return timer.avg_ms, timer.p99_ms

    result = run_ramp("freetype-gl", trial)
    glfw.terminate()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: `run_all.py` roda variantes com args** — trocar `BENCHES` e o loop:

```python
ARIAL = "C:/Windows/Fonts/arial.ttf"
BENCHES: list[list[str]] = [
    ["bench_fastobjects.py"],
    ["bench_fastobjects.py", "--font", ARIAL, "--name", "fastobjects-ttf"],
    ["bench_pygame.py"],
    ["bench_pyglet.py"],
    ["bench_freetype_gl.py"],
]
```

e no loop: `print(f"== rodando {' '.join(bench)} ==", flush=True)` e
`[sys.executable, str(HERE / bench[0]), *bench[1:]]`.

- [ ] **Step 5: `bench_font_build.py`** (load-time, sem GL):

```python
"""Load-time: rasterizar o charset latin — fastobjects.Font(ttf) vs freetype-py puro.

Nota de justiça: o lado freetype-py SÓ rasteriza (sem montar atlas); o Font
rasteriza E empacota o atlas — o freetype-py puro faz menos trabalho.
"""

import time

import freetype

from fastobjects.font import _CHARSETS, Font

FONT = "C:/Windows/Fonts/arial.ttf"
SIZE = 16
N = 20


def timeit(fn) -> float:
    fn()  # warmup
    t0 = time.perf_counter()
    for _ in range(N):
        fn()
    return (time.perf_counter() - t0) / N * 1000.0


def build_fastobjects() -> None:
    Font(FONT, SIZE)


def build_freetype() -> None:
    face = freetype.Face(FONT)
    face.set_pixel_sizes(0, SIZE)
    for ch in _CHARSETS["latin"]:
        face.load_char(ch)
        bmp = face.glyph.bitmap
        bytes(bmp.buffer)


print(f"fastobjects Font(ttf) [rasteriza+atlas]: {timeit(build_fastobjects):.2f} ms")
print(f"freetype-py puro [só rasteriza]:        {timeit(build_freetype):.2f} ms")
```

- [ ] **Step 6: Rodar (FOREGROUND) e salvar**

Run: `.venv\Scripts\python benchmarks/text/run_all.py --save` (foreground!) e depois `.venv\Scripts\python benchmarks/text/bench_font_build.py`.
Expected: tabela com 5 linhas; **gate**: `fastobjects-ttf` > `freetype-gl` em Strings @ 60fps. Anexar o resultado do load-time como parágrafo na mesma seção datada de `RESULTS.md` (via Edit). Se o gate falhar: PARAR, investigar, repensar (regra do usuário).

- [ ] **Step 7: Commit**

```bash
git add benchmarks/text/ pyproject.toml benchmarks/RESULTS.md
git commit -m "bench: texto vs freetype-py+PyOpenGL (draw call por glifo) + load-time"
```

---

### Task 4: Docs bilíngues

**Files:**
- Modify: `docs/site/guide/text.md`, `docs/site/guide/text.pt.md` (seção "Custom fonts"/"Fontes customizadas"), `docs/site/api.md`, `docs/site/api.pt.md` (assinatura de `Font`), `docs/site/performance.md`, `docs/site/performance.pt.md` (resultado freetype-gl)

**Interfaces:**
- Consumes: números reais da Task 3 (substituir os `<N>` abaixo pelos medidos).

- [ ] **Step 1: Guia** — adicionar ao fim de `docs/site/guide/text.md` (e tradução equivalente em `text.pt.md`):

````markdown
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
````

- [ ] **Step 2: API** — em `docs/site/api.md`/`.pt.md`, atualizar a entrada de `Font` para a assinatura `Font(source=None, size=24, *, chars=None, charset="latin")` com uma linha por parâmetro (source: caminho/nome ou None; charset: preset ou tupla; chars: vence charset) e o atributo `source`.

- [ ] **Step 3: Performance** — em `docs/site/performance.md`/`.pt.md`, adicionar à seção "Text throughput" um parágrafo: contra o renderizador canônico freetype-py + PyOpenGL (uma textura e um draw call por glifo, técnica do tutorial learnopengl), FastObjects com a mesma `.ttf` sustenta `<N>` strings @ 60fps vs `<N>` — `<N>x` — porque todo o texto é um único draw call instanciado; números completos em `RESULTS.md`.

- [ ] **Step 4: Build das docs**

Run: `.venv\Scripts\python -m mkdocs build --strict`
Expected: build limpo, sem warnings de link.

- [ ] **Step 5: Commit**

```bash
git add docs/site/ 
git commit -m "docs: fontes customizadas e charsets (EN/PT) + numeros freetype-gl"
```

---

### Task 5: Release 0.6.1

**Files:**
- Modify: `pyproject.toml` (`version = "0.6.1"`), `fastobjects/__init__.py` (`__version__`), `tests/test_smoke.py`

**Interfaces:**
- Consumes: tudo acima mergeado; workflow `publish.yml` (tag `v*` → PyPI), REST API com token de `git credential fill` (sem gh CLI, nunca imprimir o token).

- [ ] **Step 1: Bump** — `0.6.0` → `0.6.1` nos 3 arquivos; `.venv\Scripts\python -m pytest -q` → 136 passed; `ruff check .` limpo.

- [ ] **Step 2: Commit + merge + push**

```bash
git add pyproject.toml fastobjects/__init__.py tests/test_smoke.py
git commit -m "chore: bump to 0.6.1 - custom fonts + unicode charsets"
git checkout main
git merge --ff-only custom-fonts
git branch -d custom-fonts
git push origin main
```

- [ ] **Step 3: Tag + release**

```bash
git tag v0.6.1
git push origin v0.6.1
```

Escrever notas no scratchpad (fontes `.ttf`/`.otf` estilo pygame, presets de charset, números do gate freetype-gl, contagem de testes, prerelease=True) e criar a release com o script REST do scratchpad adaptado (`create_release_v061.py`, mesmo padrão do v0.6.0).

- [ ] **Step 4: Verificar pipeline** — checar runs do Actions (autenticado, sem polling agressivo): `Publish Python Package` (v0.6.1) e `Docs` até `success` (re-executar jobs falhos se OIDC 503); confirmar `https://pypi.org/pypi/fastobjects/0.6.1/json` → 200 e a página do guia de texto atualizada.
