# Shaping de Texto Complexo (0.6.2) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** texto correto para escritas complexas (RTL, kerning, ligaturas) via extra opcional `fastobjects[shaping]` com ativação automática e fallback, mais os testes de edge cases permanentes.

**Architecture:** backend isolado `shaping.py` — HarfBuzz (`uharfbuzz`) shapeia linha a linha com direção automática; `freetype-py` rasteriza **todos** os glifos da fonte por glyph-ID no `Atlas` estático existente. `Font` delega `layout`/atlas ao backend quando ativo (`Font.shaped`); `TextBatch`/renderer não mudam.

**Tech Stack:** uharfbuzz, freetype-py (extra `shaping`), Pillow+Raqm só como referência de corretude em teste.

## Global Constraints

- Deps de runtime do core continuam **só** moderngl, glfw, numpy, pillow; novo extra `shaping = ["uharfbuzz>=0.39", "freetype-py>=2.5"]`.
- Python ≥ 3.11; OpenGL 3.3 core.
- Commits **sem** trailer `Co-Authored-By` (regra do projeto).
- Arquivos sempre via Write/Edit (nunca `Set-Content -Encoding utf8` — BOM).
- Benchmarks GL em **foreground**.
- Regra permanente do usuário: fase inclui testes de edge cases (capacity zero, despawn em massa, resize/view_size).
- Aceite: árabe/hebraico corretos (validados vs Pillow+Raqm), kerning aplicado, fallback intacto sem extra, draw não regride de 145.873; se `pip install uharfbuzz` falhar → PARAR e reportar.
- Branch de trabalho: `shaping` a partir de `main`.

---

### Task 1: Testes de edge cases (regra permanente)

**Files:**
- Test: `tests/test_edge_cases.py` (novo)

**Interfaces:**
- Consumes: `ShapeBatch(capacity, *, ctx, view_size)` + `.rects(n, x, y, w, h, ...)`, `TextBatch(font, capacity, *, ctx, view_size)`, `BatchCore.despawn/clear/count`, `CapacityError` (`fastobjects.errors`).
- Produces: contratos pinados; nenhuma API nova.

- [ ] **Step 1: Escrever os testes** (característicos — pinam contrato; qualquer falha é bug a corrigir minimamente):

```python
"""Edge cases (regra permanente): capacity zero, despawn em massa, view_size."""

import random

import moderngl
import numpy as np
import pytest

from fastobjects.errors import CapacityError
from fastobjects.font import Font
from fastobjects.shapes import ShapeBatch
from fastobjects.text import TextBatch


@pytest.fixture(scope="module")
def gl():
    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.BLEND)
    yield ctx
    ctx.release()


def fbo_of(ctx, w, h):
    fbo = ctx.framebuffer(color_attachments=[ctx.texture((w, h), 4)])
    fbo.use()
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    return fbo


def read(fbo, w, h):
    return np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(h, w, 4)[::-1]


def test_capacity_zero_raises_actionable(gl):
    with pytest.raises(ValueError, match="capacity"):
        ShapeBatch(0, ctx=gl, view_size=(128, 64))
    with pytest.raises(ValueError, match="capacity"):
        TextBatch(Font(size=16), 0, ctx=gl, view_size=(128, 64))


def test_spawn_zero_objects_gives_empty_valid_group(gl):
    batch = ShapeBatch(10, ctx=gl, view_size=(128, 64))
    g = batch.rects(0)
    assert len(g) == 0 and batch.count == 0
    batch.draw()  # desenhar vazio não quebra


def test_write_empty_string_gives_empty_valid_group(gl):
    batch = TextBatch(Font(size=16), 10, ctx=gl, view_size=(128, 64))
    g = batch.write("", 0.0, 0.0)
    assert len(g) == 0 and batch.count == 0
    batch.draw()


def test_exact_fit_then_capacity_error(gl):
    batch = ShapeBatch(5, ctx=gl, view_size=(128, 64))
    batch.rects(5)  # lote cheio exato funciona
    assert batch.count == 5
    with pytest.raises(CapacityError, match="capacity"):
        batch.rects(1)


def test_mass_despawn_random_order(gl):
    batch = ShapeBatch(500, ctx=gl, view_size=(128, 64))
    groups = [batch.rects(10, x=float(i)) for i in range(50)]
    rng = random.Random(42)
    rng.shuffle(groups)
    for i, g in enumerate(groups):
        batch.despawn(g)
        for other in groups[i + 1 :]:  # sobreviventes seguem válidos
            assert len(other) == 10
            assert other.pos.shape == (10, 2)
        batch.draw()
    assert batch.count == 0


def test_despawn_twice_raises(gl):
    batch = ShapeBatch(10, ctx=gl, view_size=(128, 64))
    g = batch.rects(3)
    batch.despawn(g)
    with pytest.raises(RuntimeError):
        batch.despawn(g)


def test_view_size_anchors_topleft_after_resize(gl):
    """Contrato do resize: view_size novo => px continuam ancorados no topo-esq."""
    for w, h in ((128, 64), (256, 128)):
        fbo = fbo_of(gl, w, h)
        batch = ShapeBatch(10, ctx=gl, view_size=(w, h))
        batch.rects(1, x=10.0, y=10.0, w=6.0, h=6.0)
        batch.draw()
        px = read(fbo, w, h)
        ys, xs = np.where(px[:, :, 0] > 200)
        assert abs(xs.mean() - 10) < 3 and abs(ys.mean() - 10) < 3
        fbo.release()
```

- [ ] **Step 2: Rodar**

Run: `.venv\Scripts\python -m pytest tests/test_edge_cases.py -v`
Expected: 7 PASS (são characterization tests). Se algum falhar: é bug real — corrigir o mínimo no core (TDD: o teste já está vermelho) antes de seguir.

- [ ] **Step 3: Suíte inteira + commit**

Run: `.venv\Scripts\python -m pytest -q` → 143 passed; `ruff check .` limpo.

```bash
git add tests/test_edge_cases.py
git commit -m "test: edge cases permanentes - capacity zero, despawn em massa, view_size"
```

---

### Task 2: Backend de shaping (`shaping.py`)

**Files:**
- Create: `fastobjects/shaping.py`
- Modify: `pyproject.toml` (extra `shaping`)
- Test: `tests/test_shaping.py` (novo)

**Interfaces:**
- Consumes: `Atlas(images, *, max_size, padding)` (`fastobjects.atlas`), `Glyph` e `_ATLAS_MAX` (`fastobjects.font` — import seguro: `font.py` só importará `shaping` de forma lazy na Task 3).
- Produces: `shaping.available() -> bool`; `shaping.ShapedBackend(source: str, size: int)` com `line_height: float`, `glyphs: dict[int, Glyph]`, `atlas_pixels: bytes`, `atlas_size: tuple[int, int]`, `shape_line(line: str) -> list[tuple[int, float, float, float]]` (gid, x_advance, x_offset, y_offset em px, ordem visual) e `layout(text)` com o mesmo retorno do `Font.layout` atual, `char_index(ch: str) -> int` (cmap; 0 = sem glifo).

- [ ] **Step 1: Instalar o extra e registrar no pyproject**

Run: `.venv\Scripts\pip install uharfbuzz freetype-py`
(Se falhar no Windows/Python 3.13: PARAR e reportar ao usuário.)
Em `pyproject.toml`, abaixo do extra `bench`:

```toml
shaping = ["uharfbuzz>=0.39", "freetype-py>=2.5"]
```

- [ ] **Step 2: Testes falhando** — `tests/test_shaping.py`:

```python
"""Backend de shaping: HarfBuzz + FreeType (extra fastobjects[shaping])."""

from pathlib import Path

import pytest

from fastobjects import shaping

_ARIAL = Path("C:/Windows/Fonts/arial.ttf")
needs = pytest.mark.skipif(
    not (shaping.available() and _ARIAL.exists()),
    reason="extra shaping ou arial.ttf ausentes",
)


def test_available_reports_extra():
    assert shaping.available() is True  # extra instalado no ambiente de dev


@needs
def test_backend_rasterizes_whole_font():
    b = shaping.ShapedBackend(str(_ARIAL), 24)
    assert len(b.glyphs) > 1000  # arial tem milhares de glifos
    assert b.line_height > 0
    assert len(b.atlas_pixels) == b.atlas_size[0] * b.atlas_size[1] * 4
    gid_a = b.char_index("A")
    assert gid_a != 0 and b.glyphs[gid_a].uv is not None


@needs
def test_shape_line_applies_kerning():
    b = shaping.ShapedBackend(str(_ARIAL), 32)
    solo = sum(adv for _, adv, _, _ in b.shape_line("A")) + sum(
        adv for _, adv, _, _ in b.shape_line("V")
    )
    together = sum(adv for _, adv, _, _ in b.shape_line("AV"))
    assert together < solo - 0.5  # kern do par AV


@needs
def test_shape_line_lam_alef_ligature():
    b = shaping.ShapedBackend(str(_ARIAL), 32)
    assert len(b.shape_line("لا")) == 1  # lam+alef => 1 glifo (ligatura)


@needs
def test_shape_line_contextual_forms_differ():
    b = shaping.ShapedBackend(str(_ARIAL), 32)
    gids = [gid for gid, _, _, _ in b.shape_line("بب")]
    assert len(gids) == 2 and gids[0] != gids[1]  # forma final != inicial
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_shaping.py -v`
Expected: FAIL/ERROR (`No module named 'fastobjects.shaping'`).

- [ ] **Step 4: Implementar `fastobjects/shaping.py`**

```python
"""Backend de shaping (HarfBuzz + FreeType): RTL, kerning, ligaturas.

Opcional: `pip install fastobjects[shaping]`. Sem os pacotes o Font cai no
layout simples da 0.6.1 (fallback silencioso — veja Font.shaped). O atlas
contém TODOS os glifos da fonte (ligaturas e formas contextuais produzem
glyph-IDs sem caractere correspondente); linha mista LTR+RTL usa a direção
dominante detectada pelo HarfBuzz (bidi completo é limite documentado).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from fastobjects.atlas import Atlas
from fastobjects.font import _ATLAS_MAX, Glyph


def available() -> bool:
    """True se uharfbuzz e freetype-py estão instalados."""
    try:
        import freetype  # noqa: F401
        import uharfbuzz  # noqa: F401
    except ImportError:
        return False
    return True


class ShapedBackend:
    """Rasteriza a fonte inteira por glyph-ID e shapeia linhas com HarfBuzz."""

    def __init__(self, source: str, size: int) -> None:
        import freetype
        import uharfbuzz as hb

        self._hb_mod = hb
        try:
            self._ft = freetype.Face(source)
        except freetype.ft_errors.FT_Exception as e:
            raise OSError(f"FreeType não abriu {source!r}: {e}") from e
        self._ft.set_pixel_sizes(0, size)
        self._ascender = self._ft.size.ascender / 64.0
        self.line_height = (self._ft.size.ascender - self._ft.size.descender) / 64.0

        self._hb = hb.Font(hb.Face(hb.Blob(Path(source).read_bytes())))
        self._hb.scale = (size * 64, size * 64)

        imgs: list[Image.Image] = []
        ids: list[int] = []
        meta: dict[int, tuple] = {}
        for gid in range(self._ft.num_glyphs):
            self._ft.load_glyph(gid, freetype.FT_LOAD_RENDER)
            g = self._ft.glyph
            bmp = g.bitmap
            w, h = bmp.width, bmp.rows
            meta[gid] = (
                (float(w), float(h)),
                float(g.advance.x) / 64.0,
                (float(g.bitmap_left), self._ascender - float(g.bitmap_top)),
            )
            if w > 0 and h > 0:
                cov = np.frombuffer(bytes(bmp.buffer), dtype="u1").reshape(
                    h, bmp.pitch
                )[:, :w]
                rgba = np.zeros((h, w, 4), dtype="u1")
                rgba[..., 0:3] = 255
                rgba[..., 3] = cov
                imgs.append(Image.fromarray(rgba))
                ids.append(gid)

        atlas = Atlas(imgs, max_size=_ATLAS_MAX, padding=1)
        self.atlas_pixels = atlas.pixels
        self.atlas_size = atlas.size
        self.glyphs: dict[int, Glyph] = {}
        for gid, (sz, adv, off) in meta.items():
            self.glyphs[gid] = Glyph(None, sz, adv, off)
        for i, gid in enumerate(ids):
            sz, adv, off = meta[gid]
            self.glyphs[gid] = Glyph(atlas.uvs[i].copy(), sz, adv, off)

    def char_index(self, ch: str) -> int:
        """Glyph-ID do caractere na cmap da fonte (0 = não coberto)."""
        return self._ft.get_char_index(ch)

    def shape_line(self, line: str) -> list[tuple[int, float, float, float]]:
        """Shapeia uma linha: [(gid, x_advance, x_offset, y_offset)] em px,
        na ordem visual (RTL já sai invertido pronto para pen esquerda→direita)."""
        hb = self._hb_mod
        buf = hb.Buffer()
        buf.add_str(line)
        buf.guess_segment_properties()
        hb.shape(self._hb, buf)
        return [
            (info.codepoint, pos.x_advance / 64.0,
             pos.x_offset / 64.0, pos.y_offset / 64.0)
            for info, pos in zip(buf.glyph_infos, buf.glyph_positions)
        ]

    def layout(self, text: str):
        """Mesmo contrato do Font.layout: (centers, sizes, uvs, block)."""
        centers, sizes, uvs = [], [], []
        pen_y, max_w, n_lines = 0.0, 0.0, 0
        for line in text.split("\n"):
            n_lines += 1
            pen_x = 0.0
            for gid, adv, xoff, yoff in self.shape_line(line):
                g = self.glyphs.get(gid)
                if g is not None and g.uv is not None:
                    w, h = g.size
                    ox, oy = g.offset
                    centers.append(
                        (pen_x + xoff + ox + w / 2.0, pen_y - yoff + oy + h / 2.0)
                    )
                    sizes.append((w, h))
                    uvs.append(g.uv)
                pen_x += adv
            max_w = max(max_w, pen_x)
            pen_y += self.line_height
        n = len(centers)
        return (
            np.array(centers, dtype="f4").reshape(n, 2),
            np.array(sizes, dtype="f4").reshape(n, 2),
            np.array(uvs, dtype="f4").reshape(n, 4),
            (max_w, n_lines * self.line_height),
        )
```

- [ ] **Step 5: Rodar e ver passar**

Run: `.venv\Scripts\python -m pytest tests/test_shaping.py -v`
Expected: 5 PASS. `ruff check .` limpo.

- [ ] **Step 6: Commit**

```bash
git add fastobjects/shaping.py tests/test_shaping.py pyproject.toml
git commit -m "feat: backend de shaping (uharfbuzz+freetype-py) - extra fastobjects[shaping]"
```

---

### Task 3: Integração no `Font` (automático com fallback)

**Files:**
- Modify: `fastobjects/font.py` (`__init__` após resolver `chars`; `layout`; docstring)
- Test: `tests/test_shaping.py` (integração), `tests/test_text.py` (pixel árabe)

**Interfaces:**
- Consumes: `shaping.available()`, `shaping.ShapedBackend` (Task 2).
- Produces: `Font.shaped: bool`; caminho shaped com `Font.glyphs` público char→Glyph via cmap (charset define as chaves; atlas/layout cobrem a fonte inteira); `layout`/`measure` inalterados na assinatura.

- [ ] **Step 1: Testes falhando** — em `tests/test_shaping.py`:

```python
from fastobjects.font import Font  # no topo do arquivo


@needs
def test_font_goes_shaped_automatically():
    f = Font(str(_ARIAL), 24)
    assert f.shaped is True
    assert f.glyphs["A"].uv is not None  # visão pública por caractere preservada


def test_font_without_source_never_shaped():
    assert Font(size=16).shaped is False


@needs
def test_fallback_without_extra(monkeypatch):
    monkeypatch.setattr(shaping, "available", lambda: False)
    f = Font(str(_ARIAL), 24)
    assert f.shaped is False  # caminho 0.6.1 intacto
    assert f.glyphs["A"].uv is not None


@needs
def test_shaped_layout_rtl_order():
    f = Font(str(_ARIAL), 32)
    centers, _, uvs, _ = f.layout("אב")
    alef_uv = f.glyphs["א"].uv
    idx_alef = next(
        i for i in range(uvs.shape[0]) if bool((uvs[i] == alef_uv).all())
    )
    other = 1 - idx_alef
    assert centers[idx_alef, 0] > centers[other, 0]  # 1º char lógico à direita


@needs
def test_shaped_missing_font_raises_actionable():
    with pytest.raises(ValueError, match="fonte"):
        Font("nao-existe-esta-fonte.ttf", 24)


@needs
def test_raqm_reference_width_agrees():
    from PIL import Image, ImageDraw, ImageFont, features

    if not features.check("raqm"):
        pytest.skip("Pillow sem Raqm")
    pil_font = ImageFont.truetype(str(_ARIAL), 32)
    img = Image.new("L", (400, 80), 0)
    ImageDraw.Draw(img).text((10, 10), "سلام", font=pil_font, fill=255)
    arr_w = (np.array(img) > 40).any(axis=0).sum()
    fo_w = Font(str(_ARIAL), 32).measure("سلام")[0]
    assert abs(fo_w - arr_w) / arr_w < 0.3  # mesma ordem/conexão => largura próxima
```

(`import numpy as np` no topo.) E em `tests/test_text.py`:

```python
@pytest.mark.skipif(
    not Path("C:/Windows/Fonts/arial.ttf").exists(), reason="arial.ttf ausente"
)
def test_arabic_text_draws_pixels(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    font = Font("C:/Windows/Fonts/arial.ttf", 24)
    txt = TextBatch(font, capacity=100, ctx=ctx, view_size=(128, 64))
    txt.write("سلام", x=10.0, y=10.0)
    txt.draw()
    px = read(fbo)
    assert px[:, :, :3].max() > 200  # árabe renderiza (shaped ou fallback)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_shaping.py -v`
Expected: novos FALHAM (`AttributeError: shaped`).

- [ ] **Step 3: Implementar em `font.py`** — logo após o bloco que define `self.source` (fim do try/except do truetype), inserir o desvio shaped; o código existente do caminho simples permanece intacto abaixo dele:

```python
        self.shaped = False
        self._backend = None
        if source is not None:
            from fastobjects import shaping

            if shaping.available():
                try:
                    backend = shaping.ShapedBackend(str(source), size)
                except OSError as e:
                    raise ValueError(
                        f"fonte não encontrada: {source!r}. Passe um caminho "
                        ".ttf/.otf completo ou o nome de uma fonte instalada "
                        "(ex.: 'arial.ttf')."
                    ) from e
                self._backend = backend
                self.shaped = True
                self.size = size
                self.line_height = backend.line_height
                self.atlas_pixels = backend.atlas_pixels
                self.atlas_size = backend.atlas_size
                self.glyphs = {}
                for ch in dict.fromkeys(chars):
                    gid = backend.char_index(ch)
                    if gid:
                        self.glyphs[ch] = backend.glyphs[gid]
                return
```

Atenção à ordem no `__init__`: o caminho shaped precisa do `source` já validado como não-None e do `chars` resolvido — o desvio entra depois de `self.source = ...` e antes de `font = ImageFont...` ser usado para métricas/rasterização. Como `ImageFont.truetype` era quem validava a existência do arquivo, no caminho shaped a validação é o `OSError` do `ShapedBackend`; mover a criação do `ImageFont` para depois do desvio (só o caminho simples a executa). Em `layout`:

```python
    def layout(self, text: str):
        if self._backend is not None:
            return self._backend.layout(text)
        ...corpo atual inalterado...
```

Docstring da classe ganha: `shaped` (automático com extra `fastobjects[shaping]`; fallback silencioso), atlas com a fonte inteira no modo shaped, `charset`/`chars` definem só a visão `glyphs`, limite de linha mista LTR+RTL.

- [ ] **Step 4: Suíte inteira**

Run: `.venv\Scripts\python -m pytest -q`
Expected: 155 passed (148 + 7 novos). Atenção: os testes ttf da 0.6.1 agora passam pelo caminho shaped — devem continuar verdes sem mudança. `ruff check .` limpo.

- [ ] **Step 5: Commit**

```bash
git add fastobjects/font.py tests/test_shaping.py tests/test_text.py
git commit -m "feat: Font shapeia automaticamente com fastobjects[shaping] (fallback sem extra)"
```

---

### Task 4: Benchmark de shaping + não-regressão do draw

**Files:**
- Create: `benchmarks/text/bench_shaping.py`
- Modify: `benchmarks/RESULTS.md` (seção datada)

**Interfaces:**
- Consumes: `Font` (shaped/fallback via monkeypatch de `shaping.available`), Pillow+Raqm, `bench_fastobjects.py --font` (Task 3 instalada → shaped).

- [ ] **Step 1: `bench_shaping.py`** (sem GL — mede o custo de layout no `write`):

```python
"""Custo do shaping no layout: shaped vs simples vs Pillow+Raqm (publicado).

O draw não muda com shaping (mesmos quads/atlas) — o custo novo é todo no
layout/write. Pillow+Raqm é o código publicado equivalente para árabe correto
(rasteriza a string inteira por CPU a cada mudança).
"""

import time

from PIL import Image, ImageDraw, ImageFont, features

import fastobjects.shaping as shaping
from fastobjects.font import Font

FONT = "C:/Windows/Fonts/arial.ttf"
SIZE = 16
N = 2000
TEXTS = [f"سلام عليكم {i:04d}" for i in range(N)]


def rate(fn) -> float:
    fn()  # warmup
    t0 = time.perf_counter()
    fn()
    return N / (time.perf_counter() - t0)


f_shaped = Font(FONT, SIZE)
assert f_shaped.shaped, "extra shaping ausente"
print(f"layout shaped (HarfBuzz):  {rate(lambda: [f_shaped.layout(t) for t in TEXTS]):,.0f} strings/s")

_orig = shaping.available
shaping.available = lambda: False
f_simple = Font(FONT, SIZE)
shaping.available = _orig
print(f"layout simples (0.6.1):    {rate(lambda: [f_simple.layout(t) for t in TEXTS]):,.0f} strings/s  (árabe INCORRETO)")

if features.check("raqm"):
    pil = ImageFont.truetype(FONT, SIZE)

    def pil_render():
        for t in TEXTS:
            img = Image.new("L", (200, 24), 0)
            ImageDraw.Draw(img).text((0, 0), t, font=pil, fill=255)

    print(f"Pillow+Raqm (raster CPU):  {rate(pil_render):,.0f} strings/s")
else:
    print("Pillow sem Raqm — referência indisponível")
```

- [ ] **Step 2: Rodar**

Run: `.venv\Scripts\python benchmarks/text/bench_shaping.py`
Expected: três linhas de strings/s. Registrar também o tempo de construção do `Font(ttf)` shaped (fonte inteira) vs 0.6.1 — uma linha manual medida com `python -c "import time; from fastobjects.font import Font; t=time.perf_counter(); Font('C:/Windows/Fonts/arial.ttf', 16); print((time.perf_counter()-t)*1000, 'ms')"`.

- [ ] **Step 3: Não-regressão do draw (FOREGROUND)**

Run: `.venv\Scripts\python benchmarks/text/bench_fastobjects.py --font C:/Windows/Fonts/arial.ttf --name fastobjects-ttf-shaped`
Expected: `sprites_at_60fps` = 145.873 (± um degrau da rampa). Regressão além disso = bug; PARAR e investigar.

- [ ] **Step 4: Registrar em `RESULTS.md`** — seção `## Shaping 2026-07-13` com: as 3 taxas de layout, o load-time shaped vs simples, o resultado da não-regressão do draw e a nota "o custo do shaping é pago no write(), o frame não muda".

- [ ] **Step 5: Commit**

```bash
git add benchmarks/text/bench_shaping.py benchmarks/RESULTS.md
git commit -m "bench: custo do shaping no layout vs Pillow+Raqm + nao-regressao do draw"
```

---

### Task 5: Docs bilíngues

**Files:**
- Modify: `docs/site/guide/text.md`, `docs/site/guide/text.pt.md`, `docs/site/api.md`, `docs/site/api.pt.md`, `docs/site/performance.md`, `docs/site/performance.pt.md`

- [ ] **Step 1: Guia (EN; PT equivalente)** — nova seção após "Character sets":

````markdown
## Complex text: RTL, kerning, ligatures

Install the optional shaping extra and `Font` upgrades itself — Arabic and
Hebrew come out connected and in the right order, and kerning pairs apply:

```bash
pip install fastobjects[shaping]
```

```python
font = fo.Font("arial.ttf", 24)
font.shaped        # True when the extra is installed (False = simple layout)
labels.write("سلام عليكم", x=20, y=20)   # correct contextual forms + RTL
```

With shaping active the atlas contains **every glyph in the font** (ligatures
and contextual forms have no character of their own), so `charset`/`chars`
only choose which characters appear in the public `font.glyphs` dict. A line
mixing LTR and RTL uses the dominant direction detected by HarfBuzz — full
bidi is a known limit. Without the extra, `Font` falls back to the simple
per-character layout (fine for Latin/Greek/Cyrillic).
````

- [ ] **Step 2: API (EN/PT)** — na entrada de `Font`: atributo `shaped` (bool, automático com o extra `shaping`; fallback silencioso) e a nota de `charset`/`chars` no modo shaped.

- [ ] **Step 3: Performance (EN/PT)** — parágrafo em "Text throughput": shaping custa no `write()` (X strings/s vs Y do layout simples — números da Task 4), o frame não muda (draw idêntico, 145.873 sustentado); Pillow+Raqm como referência de corretude rasteriza por CPU a Z strings/s.

- [ ] **Step 4: Build + commit**

Run: `.venv\Scripts\python -m mkdocs build --strict` → limpo.

```bash
git add docs/site/
git commit -m "docs: shaping (RTL, kerning, ligaturas) EN/PT + numeros"
```

---

### Task 6: Release 0.6.2

**Files:**
- Modify: `pyproject.toml`, `fastobjects/__init__.py`, `tests/test_smoke.py` (0.6.1 → 0.6.2)

- [ ] **Step 1: Bump + verificação** — versão nos 3 arquivos; `.venv\Scripts\python -m pytest -q` → 155 passed; `ruff check .` limpo. (BOM: usar as ferramentas Write/Edit, nunca Set-Content.)

- [ ] **Step 2: Merge + push**

```bash
git add pyproject.toml fastobjects/__init__.py tests/test_smoke.py
git commit -m "chore: bump to 0.6.2 - shaping de texto complexo"
git checkout main
git merge --ff-only shaping
git branch -d shaping
git push origin main
```

- [ ] **Step 3: Tag + release**

```bash
git tag v0.6.2
git push origin v0.6.2
```

Notas no scratchpad (shaping automático com extra, RTL/kerning/ligaturas corretos validados vs Pillow+Raqm, números do bench, 154 testes incl. edge cases permanentes, limite de linha mista, prerelease=True) e criar via REST API (`create_release_v062.py`, token de `git credential fill`, nunca imprimir).

- [ ] **Step 4: Verificar pipeline** — Actions `Publish Python Package` (v0.6.2) e `Docs` até success (re-executar em OIDC 503); `https://pypi.org/pypi/fastobjects/0.6.2/json` → 200; guia com a seção de shaping no ar.
