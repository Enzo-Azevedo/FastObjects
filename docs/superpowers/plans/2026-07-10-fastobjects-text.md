# FastObjects Renderização de Texto (0.6.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (execução INLINE, a pedido do usuário). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Texto nativo via atlas de glifos (fonte embutida do Pillow), reusando atlas/SoA/renderer/shader — um draw call por TextBatch — mais pesquisa comparativa e benchmark. Aditivo. Sai como 0.6.0 (também documenta o resultado de packing vs PyTexturePacker).

**Architecture:** `Font` (puro, sem GL) rasteriza um charset com `PIL.ImageFont.load_default(size)`, empacota os glifos com o `Atlas` e expõe UV+métricas+`layout()`. `TextBatch(font, capacity)` cria a textura GL do atlas de glifos e um `SpriteRenderer`; `write(text, x, y, color, anchor)` faz o layout e preenche as colunas SoA (um quad por glifo), retornando um `SpriteGroup`. Glifo branco × cor no shader (já existente). Spec: `docs/superpowers/specs/2026-07-10-fastobjects-text-design.md`.

**Tech Stack:** Pillow (rasterização — já dep do core; ImageFont/getmask/getbbox/getlength/getmetrics), numpy, moderngl. pygame/pyglet no `[bench]` para o benchmark.

## Global Constraints

- **Aditivo:** suíte atual (111) e uso existente inalterados; nenhuma dependência nova.
- **Font sem OpenGL** (rasterização+packing puros) — testável sem contexto.
- Nenhum loop Python por sprite no upload; o layout é por caractere (texto é baixo volume), mas o preenchimento das colunas é vetorizado.
- Mensagens de erro acionáveis; pixel tests não afrouxam asserts; benchmarks GL em FOREGROUND.
- Commits sem `Co-Authored-By`; suíte + ruff verdes antes de cada commit.
- Branch: `text`. Escrever arquivos com Write/Edit (não `Set-Content -Encoding utf8` — BOM).
- Métricas de referência (Pillow 11.3, `load_default(24)`): line_height = ascent+descent = 30; `getmask(ch).size`=(w,h) da cobertura; `getbbox(ch)[:2]`=(l,t) offset; espaço tem h=0 (sem quad, só avança).

---

### Task 1: `fastobjects/font.py` — Font (puro, sem GL) + testes unitários

**Files:**
- Create: `fastobjects/font.py`
- Test: `tests/test_font.py`

**Interfaces:**
- Produces (consumido pelo Task 2): `Font(size=24, *, chars=None)` com `.atlas_pixels: bytes`, `.atlas_size: (W,H)`, `.line_height: float`, `.size: int`, `.glyphs: dict`, e `layout(text) -> (centers (n,2) f4, sizes (n,2) f4, uvs (n,4) f4, block (w,h))` e `measure(text) -> (w,h)`. Rasteriza um charset (ASCII+Latin-1 default) via Pillow.

- [ ] **Step 1: Escrever os testes (falhando)** — `tests/test_font.py`:

```python
import numpy as np
import pytest

from fastobjects.font import Font


def test_default_charset_has_ascii_and_accents():
    f = Font(size=24)
    for ch in "Aig ç ã é 9 !":
        assert ch in f.glyphs
    assert f.line_height > 0
    assert f.atlas_size[0] > 0 and f.atlas_size[1] > 0
    assert len(f.atlas_pixels) == f.atlas_size[0] * f.atlas_size[1] * 4


def test_glyph_has_uv_size_advance_offset():
    f = Font(size=24)
    g = f.glyphs["A"]
    assert g.advance > 0
    assert g.uv is not None and len(g.uv) == 4  # 'A' tem quad
    assert g.size[0] > 0 and g.size[1] > 0
    assert f.glyphs[" "].uv is None  # espaço não tem quad
    assert f.glyphs[" "].advance > 0


def test_custom_charset_respected():
    f = Font(size=20, chars="0123456789")
    assert "5" in f.glyphs
    assert "A" not in f.glyphs


def test_empty_charset_raises():
    with pytest.raises(ValueError, match="chars"):
        Font(size=20, chars="")


def test_layout_positions_and_block():
    f = Font(size=24)
    centers, sizes, uvs, block = f.layout("AB")
    assert centers.shape[0] == sizes.shape[0] == uvs.shape[0] == 2  # dois quads
    assert centers[1, 0] > centers[0, 0]  # 'B' à direita de 'A'
    assert block[0] > 0 and block[1] >= f.line_height


def test_layout_newline_adds_a_line():
    f = Font(size=24)
    _, _, _, one = f.layout("Ab")
    _, _, _, two = f.layout("A\nb")
    assert two[1] > one[1]  # duas linhas => mais alto


def test_layout_skips_unknown_char():
    f = Font(size=24, chars="AB")
    centers, *_ = f.layout("A?B")  # '?' fora do charset é pulado
    assert centers.shape[0] == 2  # só A e B viram quad


def test_measure_matches_layout_block():
    f = Font(size=24)
    assert f.measure("Hello") == pytest.approx(f.layout("Hello")[3])
```

- [ ] **Step 2: Ver falhar** — `.venv\Scripts\python -m pytest tests/test_font.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implementar `fastobjects/font.py`**

```python
"""Font: rasteriza um charset num atlas de glifos (Pillow), sem OpenGL."""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
from PIL import Image, ImageFont

from fastobjects.atlas import Atlas

# ASCII imprimível (0x20-0x7E) + Latin-1 imprimível (0xA1-0xFF): cobre acentos.
_DEFAULT_CHARS = "".join(chr(c) for c in range(0x20, 0x7F)) + "".join(
    chr(c) for c in range(0xA1, 0x100)
)
_ATLAS_MAX = 8192  # seguro em qualquer GPU desktop GL 3.3 real


class Glyph(NamedTuple):
    uv: np.ndarray | None  # (4,) f4 (u0,v0,u1,v1) ou None se sem bitmap (espaço)
    size: tuple[float, float]  # (w, h) em px
    advance: float  # avanço do pen
    offset: tuple[float, float]  # (l, t) bearing do canto superior-esquerdo


class Font:
    """Atlas de glifos de uma fonte embutida do Pillow (escalável).

    Args:
        size: altura da fonte em px.
        chars: caracteres a incluir; None usa ASCII imprimível + Latin-1
            (acentos). Um caractere fora do conjunto é pulado no layout.

    Attributes:
        atlas_pixels: bytes RGBA (top-down) do atlas de glifos.
        atlas_size: (largura, altura) do atlas.
        line_height: altura de uma linha (ascent + descent), em px.
        size: a altura pedida.
        glyphs: dict char -> Glyph.
    """

    def __init__(self, size: int = 24, *, chars: str | None = None) -> None:
        chars = _DEFAULT_CHARS if chars is None else chars
        if not chars:
            raise ValueError("chars não pode ser vazio — passe ao menos um caractere.")
        font = ImageFont.load_default(size=size)
        self.size = size
        self.line_height = float(sum(font.getmetrics()))  # ascent + descent

        imgs: list[Image.Image] = []
        img_chars: list[str] = []
        meta: dict[str, tuple[tuple[float, float], float, tuple[float, float]]] = {}
        for ch in dict.fromkeys(chars):  # únicos, ordem estável
            mask = font.getmask(ch)
            w, h = mask.size
            adv = float(font.getlength(ch))
            l, t = font.getbbox(ch)[:2]
            meta[ch] = ((float(w), float(h)), adv, (float(l), float(t)))
            if w > 0 and h > 0:
                cov = np.array(mask, dtype="u1").reshape(h, w)
                rgba = np.zeros((h, w, 4), dtype="u1")
                rgba[..., 0:3] = 255
                rgba[..., 3] = cov
                imgs.append(Image.fromarray(rgba, "RGBA"))
                img_chars.append(ch)

        atlas = Atlas(imgs, max_size=_ATLAS_MAX, padding=1)
        self.atlas_pixels = atlas.pixels
        self.atlas_size = atlas.size

        self.glyphs: dict[str, Glyph] = {}
        for ch, (sz, adv, off) in meta.items():
            self.glyphs[ch] = Glyph(None, sz, adv, off)
        for i, ch in enumerate(img_chars):
            sz, adv, off = meta[ch]
            self.glyphs[ch] = Glyph(atlas.uvs[i].copy(), sz, adv, off)

    def layout(self, text: str):
        """Posiciona os glifos de `text` a partir de (0,0) topo-esquerda.

        Returns:
            (centers (n,2) f4, sizes (n,2) f4, uvs (n,4) f4, block (w,h)) —
            centros dos quads (sprites são center-based), tamanhos, UVs e o
            tamanho do bloco de texto. n = número de glifos com bitmap.
        """
        space = self.glyphs.get(" ")
        space_adv = space.advance if space else self.size * 0.5
        centers, sizes, uvs = [], [], []
        pen_x, pen_y = 0.0, 0.0
        max_w, n_lines = 0.0, 1
        for ch in text:
            if ch == "\n":
                max_w = max(max_w, pen_x)
                pen_x, pen_y = 0.0, pen_y + self.line_height
                n_lines += 1
                continue
            g = self.glyphs.get(ch)
            if g is None:
                pen_x += space_adv
                continue
            if g.uv is not None:
                w, h = g.size
                ox, oy = g.offset
                centers.append((pen_x + ox + w / 2.0, pen_y + oy + h / 2.0))
                sizes.append((w, h))
                uvs.append(g.uv)
            pen_x += g.advance
        max_w = max(max_w, pen_x)
        n = len(centers)
        return (
            np.array(centers, dtype="f4").reshape(n, 2),
            np.array(sizes, dtype="f4").reshape(n, 2),
            np.array(uvs, dtype="f4").reshape(n, 4),
            (max_w, n_lines * self.line_height),
        )

    def measure(self, text: str) -> tuple[float, float]:
        """Tamanho (largura, altura) do bloco de `text`, sem desenhar."""
        return self.layout(text)[3]
```

- [ ] **Step 4: Rodar** — `.venv\Scripts\python -m pytest tests/test_font.py -q` → 8 passed.

- [ ] **Step 5: Commit**

```powershell
git add fastobjects/font.py tests/test_font.py
git commit -m "feat: Font rasterizes a glyph atlas from Pillow's default font (no GL)"
```

---

### Task 2: `fastobjects/text.py` — TextBatch + exports + pixel tests

**Files:**
- Create: `fastobjects/text.py`
- Modify: `fastobjects/__init__.py` (exportar `Font`, `TextBatch`)
- Test: `tests/test_text.py`

**Interfaces:**
- Consumes: `Font` (T1), `BatchCore` (uv=True), `SpriteRenderer`, `SpriteGroup`, `_context.resolve`.
- Produces: `TextBatch(font, capacity, *, ctx=None, view_size=None)` com `write(text, x, y, color=(1,1,1,1), anchor="topleft") -> SpriteGroup`, `clear`/`count`/`draw` herdados. `fastobjects.Font`, `fastobjects.TextBatch`.

- [ ] **Step 1: Testes (falhando)** — `tests/test_text.py`:

```python
import moderngl
import numpy as np
import pytest

from fastobjects.font import Font
from fastobjects.text import TextBatch


@pytest.fixture(scope="module")
def gl():
    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.BLEND)
    fbo = ctx.framebuffer(color_attachments=[ctx.texture((128, 64), 4)])
    fbo.use()
    yield ctx, fbo
    ctx.release()


def read(fbo):
    raw = np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(64, 128, 4)
    return raw[::-1]


def test_write_paints_glyph_pixels(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    font = Font(size=32)
    txt = TextBatch(font, capacity=100, ctx=ctx, view_size=(128, 64))
    txt.write("I", x=20.0, y=10.0, color=(1.0, 1.0, 1.0, 1.0))
    txt.draw()
    px = read(fbo)
    assert px[:, :, :3].max() > 200  # o glifo apareceu
    assert px[:, 100:, :3].max() < 20  # nada à direita (texto está à esquerda)


def test_write_color(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    font = Font(size=32)
    txt = TextBatch(font, capacity=100, ctx=ctx, view_size=(128, 64))
    txt.write("H", x=20.0, y=10.0, color=(1.0, 0.0, 0.0, 1.0))
    txt.draw()
    px = read(fbo)
    lit = px[px[:, :, :3].sum(axis=2) > 200]
    assert lit[:, 0].mean() > 150 and lit[:, 1].mean() < 80  # vermelho


def test_newline_goes_down(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    font = Font(size=20)
    txt = TextBatch(font, capacity=100, ctx=ctx, view_size=(128, 64))
    txt.write("A\nA", x=10.0, y=2.0)
    txt.draw()
    px = read(fbo)
    rows = np.where(px[:, :, :3].max(axis=(1, 2)) > 150)[0]
    assert rows.max() - rows.min() > 20  # duas linhas separadas em y


def test_anchor_center(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    font = Font(size=24)
    txt = TextBatch(font, capacity=100, ctx=ctx, view_size=(128, 64))
    txt.write("Hi", x=64.0, y=32.0, anchor="center")
    txt.draw()
    px = read(fbo)
    cols = np.where(px[:, :, :3].max(axis=(0, 2)) > 150)[0]
    assert abs((cols.min() + cols.max()) / 2 - 64) < 20  # centrado em x=64


def test_spaces_and_unknown_do_not_crash(gl):
    ctx, _ = gl
    font = Font(size=20, chars="AB")
    txt = TextBatch(font, capacity=100, ctx=ctx, view_size=(128, 64))
    g = txt.write("A ?B", x=0.0, y=0.0)  # espaço + '?' fora do charset
    assert len(g) == 2  # só A e B


def test_write_returns_movable_group(gl):
    ctx, _ = gl
    font = Font(size=20)
    txt = TextBatch(font, capacity=100, ctx=ctx, view_size=(128, 64))
    g = txt.write("Hi", x=10.0, y=10.0)
    y0 = g.y.copy()
    g.pos += (0.0, 5.0)
    np.testing.assert_allclose(g.y, y0 + 5.0)


def test_exports():
    import fastobjects as fo

    assert fo.Font is not None and fo.TextBatch is not None
```

- [ ] **Step 2: Ver falhar** — `.venv\Scripts\python -m pytest tests/test_text.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implementar `fastobjects/text.py`**

```python
"""TextBatch: desenha texto como sprites de um atlas de glifos (um draw call)."""

from __future__ import annotations

import moderngl
import numpy as np

from fastobjects import _context
from fastobjects._batchcore import BatchCore
from fastobjects.core.renderer import SpriteRenderer
from fastobjects.font import Font
from fastobjects.group import SpriteGroup


class TextBatch(BatchCore):
    """Lote de texto de uma fonte, desenhado em um draw call.

    Cada glifo é um quad texturizado do atlas de glifos da fonte. Vários
    `write` acumulam e saem em um único draw call; para texto que muda por
    frame (score/FPS), chame `clear()` e `write()` de novo.

    Args:
        font: a Font cujos glifos serão desenhados.
        capacity: número máximo de glifos (somando todos os writes vivos).
        ctx: contexto moderngl; se None, usa o da janela atual.
        view_size: (largura, altura) do alvo de render; se None, usa a janela.
    """

    def __init__(
        self,
        font: Font,
        capacity: int,
        *,
        ctx: moderngl.Context | None = None,
        view_size: tuple[int, int] | None = None,
    ) -> None:
        super().__init__(capacity, "glifos", uv=True)
        ctx, view_size = _context.resolve(ctx, view_size)
        self.font = font
        texture = ctx.texture(font.atlas_size, 4, data=font.atlas_pixels)
        self._renderer = SpriteRenderer(ctx, texture, capacity, view_size)

    def write(
        self,
        text: str,
        x: float,
        y: float,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
        anchor: str = "topleft",
    ) -> SpriteGroup:
        """Escreve `text` em (x, y). anchor: "topleft" (padrão) ou "center".

        Returns:
            SpriteGroup sobre os quads dos glifos (mova/recolora o texto todo).

        Raises:
            ValueError: se anchor for inválido.
            CapacityError: se os glifos não couberem no capacity restante.
        """
        if anchor not in ("topleft", "center"):
            raise ValueError(f"anchor={anchor!r} inválido: use 'topleft' ou 'center'.")
        centers, sizes, uvs, (bw, bh) = self.font.layout(text)
        n = centers.shape[0]
        dx, dy = (x, y) if anchor == "topleft" else (x - bw / 2.0, y - bh / 2.0)
        s = self._alloc(n, "write")
        cols = self._cols
        cols["pos"][s, 0] = centers[:, 0] + dx
        cols["pos"][s, 1] = centers[:, 1] + dy
        cols["size"][s] = sizes
        cols["rot"][s] = 0.0
        cols["color"][s] = color
        cols["uv"][s] = uvs
        return self._make_group(s)
```

- [ ] **Step 4: Exportar no `__init__.py`**

Adicionar os imports (ordem alfabética: `font` após `external`, `text` após `sprite`... manter ordem):

```python
from fastobjects.font import Font
```
(após `from fastobjects.external import ExternalWindow, attach`)
```python
from fastobjects.text import TextBatch
```
(após `from fastobjects.shapes import ShapeBatch`)

e incluir `"Font"` e `"TextBatch"` no `__all__` (ordem alfabética).

- [ ] **Step 5: Suíte completa + lint**

Run: `.venv\Scripts\python -m pytest -q`
Expected: 126 passed (111 + 8 font + 7 text).
Run: `.venv\Scripts\python -m ruff check fastobjects tests`

- [ ] **Step 6: Commit**

```powershell
git add fastobjects/text.py fastobjects/__init__.py tests/test_text.py
git commit -m "feat: TextBatch draws text as glyph-atlas sprites in one draw call"
```

---

### Task 3: Pesquisa comparativa — pygame/pyglet/arcade em RESEARCH.md

**Files:**
- Modify: `docs/RESEARCH.md`

- [ ] **Step 1: Ler o código instalado**
- `.venv/Lib/site-packages/pygame/` — `font`/`ftfont`: `Font.render(text)` → uma `Surface` por string (SDL_ttf), sem atlas.
- `.venv/Lib/site-packages/pyglet/text/` e `pyglet/font/` — glyph atlas (`GlyphRenderer`, `base.Font`, `Text`/`Label` com vertex list batched).
- `.venv/Lib/site-packages/arcade/` — `arcade.Text` embrulha o texto do pyglet.

- [ ] **Step 2: Escrever a seção** `## Texto: como pygame/pyglet/arcade fazem (e por que atlas de glifos)` — resumir cada abordagem citando arquivo/classe, e a conclusão: atlas de glifos + 1 draw call (nosso/pyglet) escala para muito texto e texto dinâmico; a Surface-por-string do pygame re-rasteriza e é cara em volume. Nós reusamos o texture atlas já existente.

- [ ] **Step 3: Commit** — `git add docs/RESEARCH.md; git commit -m "docs: research on pygame/pyglet/arcade text rendering vs glyph atlas"`.

---

### Task 4: Benchmark de texto — `benchmarks/text/`

**Files:**
- Create: `benchmarks/text/bench_fastobjects.py`, `bench_pygame.py`, `bench_pyglet.py`, `run_all.py`
- Modify: `benchmarks/RESULTS.md`

**Interfaces:** consome `Font`/`TextBatch` (T2); reusa `common.py` da arena via `sys.path`.

- [ ] **Step 1: `bench_fastobjects.py`** — `Window`, `Font(size=16)`, `TextBatch(font, capacity=grande)`. `trial(n)`: escreve `n` strings curtas (ex.: `"Item 0042"`) em posições variadas (um `write` cada), física trivial ou estático, mede FPS/frame time no protocolo `run_ramp("fastobjects", trial)`; um draw call. Imprime JSON.
- [ ] **Step 2: `bench_pygame.py`** — `pygame.font.Font`, por string `render` + `blit` (idiomático).
- [ ] **Step 3: `bench_pyglet.py`** — `n` `pyglet.text.Label` num `Batch`.
- [ ] **Step 4: `run_all.py`** — subprocessos (timeout 600), parse JSON, tabela; `--save` anexa no `RESULTS.md` com data/hardware, rótulo "Texto (N strings)".
- [ ] **Step 5: Rodar (FOREGROUND)** — `.venv\Scripts\python benchmarks/text/run_all.py --save`. Expected: fastobjects em 1º (1 draw call vs surface/label por string). Regressão/perda inesperada → investigar com systematic-debugging antes de commitar.
- [ ] **Step 6: Lint + commit** — `ruff check benchmarks/text`; `git add benchmarks/text benchmarks/RESULTS.md; git commit -m "bench: text throughput vs pygame and pyglet"`.

---

### Task 5: Docs + exemplo + nota de packing

**Files:**
- Modify: `docs/site/guide/` (nova página `text.md`/`.pt.md` + entrada no `mkdocs.yml` nav), `docs/site/api.md`/`.pt.md`, `docs/site/performance.md`/`.pt.md` (nota de packing)
- Create: `examples/text_hud.py`

- [ ] **Step 1: `examples/text_hud.py`** — `Font`, um `TextBatch` estático (título/instruções) + um dinâmico (FPS via clear+write por frame); `--frames N` auto-teste imprimindo `text ok: <n> frames`; ESC sai. Verificar com `--frames 120`.
- [ ] **Step 2: Página "Text" no guia** (EN) `docs/site/guide/text.md`: criar `Font(size)`, `TextBatch`, `write` (cor, `\n`, anchor), texto dinâmico (clear+write), `font.measure`, limites (fonte embutida na 0.6.0; custom na 0.6.1). Adicionar ao `nav` do `mkdocs.yml`. Espelhar em `.pt.md`.
- [ ] **Step 3: API reference** (`api.md`/`.pt.md`): `Font(size, *, chars=None)` (+ `measure`, `line_height`), `TextBatch(font, capacity)` (+ `write`, `clear`, `draw`, `count`).
- [ ] **Step 4: Nota de packing** em `performance.md`/`.pt.md`: um parágrafo com o resultado vs PyTexturePacker (empate em tamanhos variados, 30-77x em spritesheet, mesmo tamanho de atlas), link para a seção do `RESULTS.md`.
- [ ] **Step 5: Build estrito** — `.venv\Scripts\python -m mkdocs build --strict`.
- [ ] **Step 6: Verificar exemplo** — `.venv\Scripts\python examples/text_hud.py --frames 120`.
- [ ] **Step 7: Lint + commit** — `git add docs/site mkdocs.yml examples/text_hud.py; git commit -m "docs: text guide (EN/PT), API, example, and packing-speed note"`.

---

### Task 6: Release 0.6.0

- [ ] **Step 1:** Bump 0.5.0 → 0.6.0 (pyproject, `fastobjects/__init__.py`, tests/test_smoke.py — via Edit, sem BOM); suíte verde; `git commit -m "chore: bump to 0.6.0 - text rendering"`.
- [ ] **Step 2:** Merge em main via superpowers:finishing-a-development-branch (suíte → merge → suíte → delete branch → push).
- [ ] **Step 3:** Tag `v0.6.0` + push; pre-release GitHub via REST API (token de `git credential fill`, sem gh CLI); notas com texto + números do benchmark + nota de packing. Acompanhar `publish.yml` e o docs workflow até success (re-executar jobs se um 503 do OIDC reincidir); confirmar PyPI 0.6.0.

---

## Fora deste plano (0.6.1+)

Fontes customizadas (`.ttf`/`.otf`) + encoding/formatação (utf-8, charset ampliado); alinhamento por linha e word-wrap; rich text; atlas de glifos dinâmico.
