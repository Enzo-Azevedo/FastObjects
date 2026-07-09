# FastObjects Texture Atlas (estático) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (execução INLINE, a pedido do usuário). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Um `SpriteBatch` desenha várias imagens (atlas estático) em um único draw call — aditivo, sem quebrar o uso atual — com pesquisa comparativa (arcade/pyglet) e benchmark multi-imagem.

**Architecture:** `Atlas` (packing puro, sem GL) empacota N imagens numa textura + UVs; o SoA ganha uma coluna fria `uv` (dirty-tracked); o shader de sprite amostra o sub-retângulo via `mix(uv0, uv1, corner)`; `SpriteBatch(images, ...)` aceita str/list/dict e `spawn(image=)`/`group.image` selecionam a sub-imagem. Compat retro total (imagem única → uv full). Spec: `docs/superpowers/specs/2026-07-09-fastobjects-texture-atlas-design.md`.

**Tech Stack:** numpy (packing/extrude via `np.pad`), moderngl (5º VBO), pillow; arcade/pyglet no `[bench]` para o benchmark comparativo.

## Global Constraints

- **Aditivo:** `SpriteBatch("x.png", capacity)` e a suíte/benches/exemplos atuais permanecem funcionando sem edição (imagem única = atlas de 1 imagem, uv apontando para a sub-imagem). Baseline 98 testes.
- Nenhum loop Python por sprite; `image`/UV vetorizados (escalar ou array).
- Mensagens de erro acionáveis (overflow do atlas; índice/nome de imagem inválido; `image` em ShapeBatch).
- Pixel tests não afrouxam asserts; benchmarks GL em FOREGROUND.
- Commits sem `Co-Authored-By`; suíte + ruff verdes antes de cada commit.
- Branch: `texture-atlas`. Escrever arquivos com Write/Edit (não `Set-Content -Encoding utf8` — BOM).

---

### Task 1: `fastobjects/atlas.py` — empacotamento (sem GL) + testes unitários

**Files:**
- Create: `fastobjects/atlas.py`
- Modify: `fastobjects/errors.py` (nova `AtlasOverflowError`)
- Test: `tests/test_atlas.py`

**Interfaces:**
- Produces: `Atlas(images: list[Image], *, max_size: int, padding: int = 1)` com `.size: (W,H)`, `.pixels: bytes` (RGBA top-down), `.uvs: (n,4) f4`, `.sizes: (n,2) f4`. `AtlasOverflowError` acionável. Consumido pelo Task 3.

- [ ] **Step 1: Escrever os testes (falhando)** — `tests/test_atlas.py`:

```python
import numpy as np
import pytest
from PIL import Image

from fastobjects.atlas import Atlas
from fastobjects.errors import AtlasOverflowError


def solid(w, h, rgba):
    return Image.new("RGBA", (w, h), rgba)


def test_uvs_and_sizes_match_inputs():
    imgs = [solid(10, 20, (255, 0, 0, 255)), solid(30, 5, (0, 255, 0, 255))]
    atlas = Atlas(imgs, max_size=1024)
    assert atlas.uvs.shape == (2, 4)
    assert atlas.sizes.shape == (2, 2)
    np.testing.assert_array_equal(atlas.sizes[0], [10, 20])
    np.testing.assert_array_equal(atlas.sizes[1], [30, 5])
    # uvs dentro de [0,1] e o retângulo tem o tamanho da imagem em px
    W, H = atlas.size
    for i, (w, h) in enumerate([(10, 20), (30, 5)]):
        u0, v0, u1, v1 = atlas.uvs[i]
        assert 0.0 <= u0 < u1 <= 1.0 and 0.0 <= v0 < v1 <= 1.0
        assert round((u1 - u0) * W) == w
        assert round((v1 - v0) * H) == h


def test_images_do_not_overlap_in_uv_space():
    imgs = [solid(20, 20, (255, 0, 0, 255)) for _ in range(4)]
    atlas = Atlas(imgs, max_size=1024)
    W, H = atlas.size
    boxes = []
    for u0, v0, u1, v1 in atlas.uvs:
        boxes.append((round(u0 * W), round(v0 * H), round(u1 * W), round(v1 * H)))
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            ax0, ay0, ax1, ay1 = boxes[i]
            bx0, by0, bx1, by1 = boxes[j]
            overlap = ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1
            assert not overlap


def test_pixels_contain_each_image_color():
    imgs = [solid(8, 8, (255, 0, 0, 255)), solid(8, 8, (0, 255, 0, 255))]
    atlas = Atlas(imgs, max_size=1024)
    W, H = atlas.size
    arr = np.frombuffer(atlas.pixels, dtype="u1").reshape(H, W, 4)
    for i, color in enumerate([(255, 0, 0), (0, 255, 0)]):
        u0, v0, u1, v1 = atlas.uvs[i]
        cx = int((u0 + u1) / 2 * W)
        cy = int((v0 + v1) / 2 * H)
        assert tuple(arr[cy, cx, :3]) == color


def test_edge_extruded_padding_no_transparent_gutter():
    # com padding, o pixel imediatamente FORA do retângulo (na borda) repete a
    # cor da borda (extrusão), não é transparente
    imgs = [solid(8, 8, (255, 0, 0, 255)), solid(8, 8, (0, 255, 0, 255))]
    atlas = Atlas(imgs, max_size=1024, padding=1)
    W, H = atlas.size
    arr = np.frombuffer(atlas.pixels, dtype="u1").reshape(H, W, 4)
    u0, v0, u1, v1 = atlas.uvs[0]
    x0 = round(u0 * W)
    ymid = int((v0 + v1) / 2 * H)
    assert tuple(arr[ymid, x0 - 1, :3]) == (255, 0, 0)  # borda extrudada, não vizinho


def test_overflow_raises_actionable():
    imgs = [solid(200, 200, (255, 0, 0, 255))]
    with pytest.raises(AtlasOverflowError, match="não cabem"):
        Atlas(imgs, max_size=64)


def test_deterministic():
    imgs = [solid(10, 20, (1, 2, 3, 255)), solid(15, 15, (4, 5, 6, 255))]
    a = Atlas(imgs, max_size=1024)
    b = Atlas(imgs, max_size=1024)
    assert a.size == b.size
    np.testing.assert_array_equal(a.uvs, b.uvs)
```

- [ ] **Step 2: Ver falhar** — `.venv\Scripts\python -m pytest tests/test_atlas.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Erro em `errors.py`** — adicionar:

```python
class AtlasOverflowError(Exception):
    """Levantada quando as imagens não cabem num atlas do tamanho máximo."""
```

- [ ] **Step 4: Implementar `fastobjects/atlas.py`**

```python
"""Empacotamento de imagens num texture atlas (shelf packing, sem GL)."""

from __future__ import annotations

import numpy as np
from PIL import Image

from fastobjects.errors import AtlasOverflowError


def _next_pow2(n: int) -> int:
    p = 1
    while p < n:
        p *= 2
    return p


class Atlas:
    """Empacota imagens numa única textura RGBA e produz as UVs de cada uma.

    Shelf packing (imagens ordenadas por altura desc, colocadas em prateleiras),
    com `padding` px de borda extrudada entre as sub-imagens para evitar bleeding
    sob filtragem linear. A textura é montada top-down (coerente com o renderer
    y-para-baixo).

    Args:
        images: imagens PIL (serão convertidas para RGBA).
        max_size: dimensão máxima da textura (GL_MAX_TEXTURE_SIZE).
        padding: px de borda extrudada em volta de cada imagem.

    Attributes:
        size: (largura, altura) da textura empacotada.
        pixels: bytes RGBA (top-down) para ctx.texture(size, 4, data=pixels).
        uvs: (n, 4) float32 — (u0, v0, u1, v1) por imagem de entrada.
        sizes: (n, 2) float32 — (w, h) em pixels por imagem.

    Raises:
        AtlasOverflowError: se as imagens não couberem em max_size.
    """

    def __init__(
        self, images: list[Image.Image], *, max_size: int, padding: int = 1
    ) -> None:
        rgba = [im.convert("RGBA") for im in images]
        self.sizes = np.array([im.size for im in rgba], dtype="f4")
        cells = [(im.size[0] + 2 * padding, im.size[1] + 2 * padding) for im in rgba]

        order = sorted(range(len(cells)), key=lambda i: cells[i][1], reverse=True)
        widest = max(cw for cw, _ in cells)
        total = sum(cw * ch for cw, ch in cells)
        atlas_w = min(max_size, _next_pow2(max(widest, int(total**0.5) + 1)))

        placements = [(0, 0)] * len(cells)
        x = y = shelf_h = 0
        for i in order:
            cw, ch = cells[i]
            if x + cw > atlas_w:
                x = 0
                y += shelf_h
                shelf_h = 0
            placements[i] = (x, y)
            x += cw
            shelf_h = max(shelf_h, ch)
        atlas_h = _next_pow2(y + shelf_h)

        if atlas_w > max_size or atlas_h > max_size:
            biggest = max(rgba, key=lambda im: im.size[0] * im.size[1]).size
            raise AtlasOverflowError(
                f"As imagens não cabem num atlas de {max_size}x{max_size} — a "
                f"maior é {biggest[0]}x{biggest[1]}. Reduza as imagens ou divida "
                "em vários batches (um SpriteBatch por atlas)."
            )

        atlas = np.zeros((atlas_h, atlas_w, 4), dtype="u1")
        uvs = np.zeros((len(cells), 4), dtype="f4")
        for i, im in enumerate(rgba):
            cx, cy = placements[i]
            w, h = im.size
            block = np.pad(
                np.asarray(im, dtype="u1"),
                ((padding, padding), (padding, padding), (0, 0)),
                mode="edge",
            )
            bh, bw = block.shape[:2]
            atlas[cy : cy + bh, cx : cx + bw] = block
            x0, y0 = cx + padding, cy + padding
            uvs[i] = [x0 / atlas_w, y0 / atlas_h,
                      (x0 + w) / atlas_w, (y0 + h) / atlas_h]

        self.size = (atlas_w, atlas_h)
        self.pixels = atlas.tobytes()
        self.uvs = uvs
```

- [ ] **Step 5: Rodar** — `.venv\Scripts\python -m pytest tests/test_atlas.py -q` → 6 passed.

- [ ] **Step 6: Commit**

```powershell
git add fastobjects/atlas.py fastobjects/errors.py tests/test_atlas.py
git commit -m "feat: static texture atlas packing with edge-extruded padding"
```

---

### Task 2: Coluna `uv` no SoA + shader + renderer (compat retro)

**Files:**
- Modify: `fastobjects/_batchcore.py` (flag `uv`), `fastobjects/core/renderer.py` (5º VBO + COLUMN_*), `fastobjects/core/shaders.py` (SPRITE_VS), `fastobjects/layer.py` (SurfaceLayer com uv full)
- Test: `tests/test_renderer.py` (cols com uv)

**Interfaces:**
- Produces: `SpriteRenderer` com colunas `(pos, size, rot, color, uv)`; `render(cols, count, dirty)` sobe `uv` como coluna fria; `BatchCore(capacity, unit, *, kind=False, uv=False)` cria a coluna `uv (cap,4)` quando `uv=True`.

- [ ] **Step 1: `_batchcore.py` — flag uv**

Na assinatura: `def __init__(self, capacity, unit, *, kind=False, uv=False)`. Após o bloco que adiciona `kind`:

```python
        if uv:
            self._cols["uv"] = np.zeros((capacity, 4), dtype="f4")
```

(`_mark_all` já marca toda coluna != "pos", então `uv` entra no dirty em spawn/despawn/clear sem mudança.)

- [ ] **Step 2: `core/renderer.py` — coluna uv nos dicts + COLUMNS do sprite**

Em `COLUMN_BYTES/COLUMN_FORMATS/COLUMN_ATTRS`, adicionar a entrada `uv`:

```python
COLUMN_BYTES = {"pos": 8, "size": 8, "rot": 4, "color": 16, "kind": 4, "uv": 16}
COLUMN_FORMATS = {
    "pos": "2f/i", "size": "2f/i", "rot": "1f/i", "color": "4f/i",
    "kind": "1f/i", "uv": "4f/i",
}
COLUMN_ATTRS = {
    "pos": "in_pos", "size": "in_size", "rot": "in_rot", "color": "in_color",
    "kind": "in_kind", "uv": "in_uv",
}
```

Em `SpriteRenderer`, trocar `COLUMNS = ("pos", "size", "rot", "color")` por:

```python
    COLUMNS = ("pos", "size", "rot", "color", "uv")
```

- [ ] **Step 3: `core/shaders.py` — SPRITE_VS amostra o sub-retângulo**

Adicionar `in vec4 in_uv;` (após `in vec4 in_color;`) e trocar a linha
`v_uv = CORNERS[gl_VertexID] + 0.5;` por:

```glsl
    vec2 c_uv = CORNERS[gl_VertexID] + 0.5;
    v_uv = mix(in_uv.xy, in_uv.zw, c_uv);
```

(`SPRITE_FS` inalterado.)

- [ ] **Step 4: `layer.py` — SurfaceLayer fornece uv full**

O SurfaceLayer usa `SpriteRenderer` (que agora exige a coluna `uv`). No `__init__`,
adicionar a coluna ao `self._cols` e ao `self._dirty` inicial:

```python
        self._cols = {
            "pos": np.array([[w / 2.0, h / 2.0]], dtype="f4"),
            "size": np.array([[float(w), float(h)]], dtype="f4"),
            "rot": np.zeros(1, dtype="f4"),
            "color": np.ones((1, 4), dtype="f4"),
            "uv": np.array([[0.0, 0.0, 1.0, 1.0]], dtype="f4"),
        }
        self._dirty = {"size", "rot", "color", "uv"}
```

- [ ] **Step 5: `tests/test_renderer.py` — cols com uv**

Em `make_sprite_cols`, adicionar a chave `uv` full e incluir `"uv"` no dirty
passado ao `render`:

```python
def make_sprite_cols(x, y, w, h, rot, color) -> dict:
    return {
        "pos": np.array([[x, y]], dtype="f4"),
        "size": np.array([[w, h]], dtype="f4"),
        "rot": np.array([rot], dtype="f4"),
        "color": np.array([color], dtype="f4"),
        "uv": np.array([[0.0, 0.0, 1.0, 1.0]], dtype="f4"),
    }
```

Nos três `renderer.render(cols, 1, {...})`, incluir `"uv"` no set dirty
(ex.: `{"size", "rot", "color", "uv"}`); no de count 0, manter `set()`.

- [ ] **Step 6: Suíte parcial (estado intencional vermelho)** — `.venv\Scripts\python -m pytest -q`

**NÃO commitar aqui.** O SpriteRenderer agora exige 5 colunas (com `uv`), mas o
SpriteBatch atual ainda cria 4 — só o SpriteBatch-atlas do Task 3 fornece a
coluna `uv`. Logo `test_batch`/`test_group`/`test_dirty` vão falhar
temporariamente (esperado); `test_atlas`, `test_renderer`, `test_shapes`,
`test_layer` devem estar verdes. T2 e T3 são uma unidade lógica e são
**commitados juntos ao final do Task 3** (quando a suíte volta 100% verde).
Confirmar aqui que as únicas falhas são as três acima, por `uv` ausente no
SpriteBatch — qualquer outra falha (shape/renderer/layer/atlas) é um bug deste
task, corrigir antes de seguir.

---

### Task 3: SpriteBatch multi-imagem + SpriteGroup.image (feature completa)

**Files:**
- Modify: `fastobjects/batch.py` (atlas, `images`, `spawn(image=)`, `set_group_image`, `image_index`)
- Modify: `fastobjects/group.py` (`image` setter)
- Test: `tests/test_batch.py` (uv em imagem única — ajuste mínimo), `tests/test_atlas_sprites.py` (novo, pixel tests de ponta a ponta)

**Interfaces:**
- Consumes: `Atlas` (T1), coluna `uv` (T2).
- Produces: `SpriteBatch(images: str|list[str]|dict, capacity, ...)`; `spawn(..., image=0)`; `SpriteGroup.image = i`; comportamento de imagem única inalterado.

- [ ] **Step 1: Testes de ponta a ponta (falhando)** — `tests/test_atlas_sprites.py`:

```python
import moderngl
import numpy as np
import pytest
from PIL import Image

from fastobjects.batch import SpriteBatch


@pytest.fixture(scope="module")
def gl():
    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.BLEND)
    fbo = ctx.framebuffer(color_attachments=[ctx.texture((64, 64), 4)])
    fbo.use()
    yield ctx, fbo
    ctx.release()


def read(fbo):
    raw = np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(64, 64, 4)
    return raw[::-1]


def make_pngs(tmp_path):
    red = tmp_path / "red.png"
    green = tmp_path / "green.png"
    Image.new("RGBA", (16, 16), (255, 0, 0, 255)).save(red)
    Image.new("RGBA", (16, 16), (0, 255, 0, 255)).save(green)
    return str(red), str(green)


def test_each_image_renders_its_own_pixels(gl, tmp_path):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    red, green = make_pngs(tmp_path)
    batch = SpriteBatch([red, green], capacity=10, ctx=ctx, view_size=(64, 64))
    batch.spawn(1, x=16.0, y=32.0, image=0)   # vermelho à esquerda
    batch.spawn(1, x=48.0, y=32.0, image=1)   # verde à direita
    batch.draw()
    px = read(fbo)
    assert px[32, 16][0] > 200 and px[32, 16][1] < 60   # vermelho
    assert px[32, 48][1] > 200 and px[32, 48][0] < 60   # verde


def test_group_image_retextures(gl, tmp_path):
    ctx, fbo = gl
    red, green = make_pngs(tmp_path)
    batch = SpriteBatch([red, green], capacity=10, ctx=ctx, view_size=(64, 64))
    g = batch.spawn(1, x=32.0, y=32.0, image=0)
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    batch.draw()
    assert read(fbo)[32, 32][0] > 200      # vermelho
    g.image = 1
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    batch.draw()
    assert read(fbo)[32, 32][1] > 200      # agora verde


def test_vectorized_image_array(gl, tmp_path):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    red, green = make_pngs(tmp_path)
    batch = SpriteBatch([red, green], capacity=10, ctx=ctx, view_size=(64, 64))
    batch.spawn(2, x=np.array([16.0, 48.0], dtype="f4"), y=32.0,
                image=np.array([0, 1]))
    batch.draw()
    px = read(fbo)
    assert px[32, 16][0] > 200   # imagem 0 = vermelho
    assert px[32, 48][1] > 200   # imagem 1 = verde


def test_named_images(gl, tmp_path):
    ctx, _ = gl
    red, green = make_pngs(tmp_path)
    batch = SpriteBatch({"vermelho": red, "verde": green}, capacity=10,
                        ctx=ctx, view_size=(64, 64))
    g = batch.spawn(1, x=32.0, y=32.0, image="verde")
    np.testing.assert_allclose(g.size[0], [16.0, 16.0])
    with pytest.raises(ValueError, match="azul"):
        batch.spawn(1, image="azul")


def test_default_size_is_selected_image_size(gl, tmp_path):
    ctx, _ = gl
    red, green = make_pngs(tmp_path)
    Image.new("RGBA", (10, 40), (0, 0, 255, 255)).save(tmp_path / "tall.png")
    batch = SpriteBatch([red, str(tmp_path / "tall.png")], capacity=10,
                        ctx=ctx, view_size=(64, 64))
    g = batch.spawn(1, image=1)
    np.testing.assert_allclose(g.size[0], [10.0, 40.0])


def test_image_index_out_of_range_raises(gl, tmp_path):
    ctx, _ = gl
    red, green = make_pngs(tmp_path)
    batch = SpriteBatch([red, green], capacity=10, ctx=ctx, view_size=(64, 64))
    with pytest.raises(ValueError, match="0..1"):
        batch.spawn(1, image=5)


def test_image_on_shapebatch_raises(gl):
    from fastobjects.shapes import ShapeBatch

    ctx, _ = gl
    batch = ShapeBatch(capacity=10, ctx=ctx, view_size=(64, 64))
    g = batch.rects(1)
    with pytest.raises(AttributeError, match="imagem"):
        g.image = 0
```

- [ ] **Step 2: Ver falhar** — `.venv\Scripts\python -m pytest tests/test_atlas_sprites.py -q` (falha: SpriteBatch não aceita lista / sem `image`).

- [ ] **Step 3: Reescrever `SpriteBatch` (`batch.py`)**

```python
"""SpriteBatch: sprites de um texture atlas, estado em colunas NumPy."""

from __future__ import annotations

from pathlib import Path

import moderngl
import numpy as np
from PIL import Image

from fastobjects import _context
from fastobjects._batchcore import BatchCore
from fastobjects.atlas import Atlas
from fastobjects.core.renderer import SpriteRenderer
from fastobjects.group import SpriteGroup


def _normalize_images(images):
    """Retorna (paths: list[str], names: dict[str,int] | None)."""
    if isinstance(images, str):
        return [images], None
    if isinstance(images, dict):
        keys = list(images.keys())
        return [images[k] for k in keys], {k: i for i, k in enumerate(keys)}
    return list(images), None


class SpriteBatch(BatchCore):
    """Lote de sprites desenhado em um draw call, de um ou vários assets (atlas).

    As imagens são empacotadas numa única textura na criação; cada sprite
    guarda o retângulo UV da sua sub-imagem. `spawn(image=i)` e `group.image = i`
    escolhem a imagem (índice inteiro, ou nome se `images` for um dict).

    Args:
        images: caminho (str), lista de caminhos (índice por posição) ou dict
            nome->caminho.
        capacity: número máximo de sprites do lote.
        ctx: contexto moderngl; se None, usa o da janela atual.
        view_size: (largura, altura) do alvo de render; se None, usa a janela.
    """

    def __init__(
        self,
        images: str | list[str] | dict[str, str],
        capacity: int,
        *,
        ctx: moderngl.Context | None = None,
        view_size: tuple[int, int] | None = None,
    ) -> None:
        super().__init__(capacity, "sprites", uv=True)
        ctx, view_size = _context.resolve(ctx, view_size)
        paths, names = _normalize_images(images)
        pil = []
        for p in paths:
            path = Path(p)
            if not path.is_file():
                raise FileNotFoundError(
                    f"Textura não encontrada: {path.resolve()} — verifique o "
                    "caminho (relativo ao diretório de execução) ou use absoluto."
                )
            pil.append(Image.open(path).convert("RGBA"))
        atlas = Atlas(pil, max_size=ctx.info["GL_MAX_TEXTURE_SIZE"])
        self._uvs = atlas.uvs
        self._img_sizes = atlas.sizes
        self._names = names
        texture = ctx.texture(atlas.size, 4, data=atlas.pixels)
        self._renderer = SpriteRenderer(ctx, texture, capacity, view_size)

    def _resolve_image(self, image):
        """Escalar/array, int/str -> índice(s) inteiro(s) validados."""
        if isinstance(image, str):
            if not self._names or image not in self._names:
                disponiveis = list(self._names) if self._names else "(nenhum nome)"
                raise ValueError(
                    f"Imagem '{image}' não existe — disponíveis: {disponiveis}."
                )
            return self._names[image]
        idx = np.asarray(image)
        n = len(self._uvs)
        if idx.min() < 0 or idx.max() >= n:
            raise ValueError(
                f"image={image} fora de faixa: use índices 0..{n - 1}."
            )
        return image

    def spawn(
        self,
        n: int,
        x: float | np.ndarray = 0.0,
        y: float | np.ndarray = 0.0,
        w: float | np.ndarray | None = None,
        h: float | np.ndarray | None = None,
        rot: float | np.ndarray = 0.0,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
        image: int | str | np.ndarray = 0,
    ) -> SpriteGroup:
        """Adiciona n sprites. Escalares ou arrays de tamanho n; `image` escolhe
        a sub-imagem (índice ou nome; `w`/`h` None usam o tamanho dela).
        """
        s = self._alloc(n, "spawn")
        idx = self._resolve_image(image)
        cols = self._cols
        cols["pos"][s, 0] = x
        cols["pos"][s, 1] = y
        cols["size"][s, 0] = self._img_sizes[idx, 0] if w is None else w
        cols["size"][s, 1] = self._img_sizes[idx, 1] if h is None else h
        cols["rot"][s] = rot
        cols["color"][s] = color
        cols["uv"][s] = self._uvs[idx]
        return self._make_group(s)

    def set_group_image(self, s: slice, image) -> None:
        """Re-textura as linhas do slice para a imagem dada (usado por group.image)."""
        idx = self._resolve_image(image)
        self._cols["uv"][s] = self._uvs[idx]
        self._dirty.add("uv")
```

- [ ] **Step 4: `group.py` — setter `image`**

Adicionar à classe `SpriteGroup` (após `color`):

```python
    @property
    def image(self):
        raise AttributeError(
            "image é write-only — atribua um índice/nome (group.image = i)."
        )

    @image.setter
    def image(self, value) -> None:
        self._check_alive()
        setter = getattr(self._batch, "set_group_image", None)
        if setter is None:
            raise AttributeError(
                "este grupo não tem imagem — image só existe em SpriteBatch "
                "(um ShapeBatch não tem atlas)."
            )
        setter(self._slice, value)
```

- [ ] **Step 5: Ajuste mínimo em `tests/test_batch.py`**

O `BUNNY` (imagem única) continua válido: `SpriteBatch(BUNNY, capacity=..., ...)`.
Os asserts de `batch.size[0,0]==26.0`/`37.0` continuam (tamanho da imagem). Não
deve precisar de mudança; se algum assert dependia do layout antigo, ajustar
para a coluna correspondente. Rodar e corrigir só o que quebrar.

- [ ] **Step 6: Suíte completa + lint**

Run: `.venv\Scripts\python -m pytest -q`
Expected: 111 passed (104 + 7 novos de atlas_sprites). Compat retro: os testes
de imagem única (`test_batch`, `test_group`, `test_dirty`) voltam a passar (o
SpriteBatch agora cria e preenche a coluna `uv`).
Run: `.venv\Scripts\python -m ruff check fastobjects tests`

- [ ] **Step 7: Commit (T2 + T3 juntos — suíte 100% verde)**

```powershell
git add fastobjects/_batchcore.py fastobjects/core/renderer.py fastobjects/core/shaders.py fastobjects/layer.py fastobjects/batch.py fastobjects/group.py tests/test_renderer.py tests/test_atlas_sprites.py tests/test_batch.py
git commit -m "feat: multi-image SpriteBatch via atlas (uv column, shader, spawn image=, group.image)"
```

---

### Task 4: Pesquisa comparativa — arcade e pyglet em RESEARCH.md

**Files:**
- Modify: `docs/RESEARCH.md`

**Interfaces:** documentação; consome o código instalado de arcade/pyglet.

- [ ] **Step 1: Ler o código dos concorrentes**

Ler (instalados no venv):
- `.venv/Lib/site-packages/arcade/texture_atlas/atlas_default.py` (alocador,
  region allocation, resize dinâmico, `uv_data.py`, `region.py`).
- `.venv/Lib/site-packages/pyglet/image/atlas.py` (`Allocator`, `TextureAtlas`,
  `TextureBin` — cresce criando novos atlas quando cheio).

- [ ] **Step 2: Escrever a seção em `docs/RESEARCH.md`**

Anexar `## Texture atlas: como arcade e pyglet fazem (e por que o nosso é estático)`
respondendo, citando arquivo/classe:
- arcade: atlas **dinâmico** com alocador de regiões e **resize** quando enche;
  UVs guardadas num buffer de textura; custo do resize (recopiar tudo).
- pyglet: `Allocator` de prateleiras; `TextureBin` cria **novos** atlas quando
  o atual enche (não faz resize).
- FastObjects: atlas **estático** montado uma vez na criação do batch — o caso
  de arte conhecida na criação; sem alocador dinâmico/resize (mais simples,
  determinístico, testável). Trade-off: não dá para adicionar imagens em runtime
  (fase futura). Ganho: zero complexidade de realocação no caminho de criação e
  nenhum custo em runtime.

- [ ] **Step 3: Commit**

```powershell
git add docs/RESEARCH.md
git commit -m "docs: research on arcade/pyglet atlas internals vs our static atlas"
```

---

### Task 5: Benchmark multi-imagem (FastObjects vs arcade vs pyglet)

**Files:**
- Create: `benchmarks/multi_image/gen_images.py`, `bench_fastobjects.py`, `bench_arcade.py`, `bench_pyglet.py`, `run_all.py`
- Modify: `benchmarks/RESULTS.md`

**Interfaces:** consome a API do Task 3; produz números comparativos.

- [ ] **Step 1: `gen_images.py`** — gera M=8 PNGs distintos (cores/formas
  determinísticas, 32x32) em `benchmarks/multi_image/assets/`.

- [ ] **Step 2: `bench_fastobjects.py`** — reusa o harness `common.py` da arena
  (via `sys.path`): `Window`, `SpriteBatch(list_of_8_images, capacity=N)`,
  `spawn(N, x=, y=, image=<array (np.arange(N) % 8)>)`, física vetorizada nas
  views, `run_ramp("fastobjects-atlas", trial)`; imprime a linha JSON.

- [ ] **Step 3: `bench_arcade.py`** — `arcade.SpriteList`, N sprites, cada um com
  uma das 8 texturas (`arcade.load_texture`), posições setadas por sprite (uso
  idiomático do arcade); mesma medição/ramp; JSON `"arcade"`.

- [ ] **Step 4: `bench_pyglet.py`** — N `pyglet.sprite.Sprite` com 8 imagens
  cicladas, `Batch`; JSON `"pyglet"`.

- [ ] **Step 5: `run_all.py`** — roda os três em subprocessos (timeout 600),
  parse do JSON da última linha, tabela markdown; `--save` anexa em
  `benchmarks/RESULTS.md` com data/hardware e o rótulo "Multi-imagem".

- [ ] **Step 6: Rodar (FOREGROUND)** — `.venv\Scripts\python benchmarks/multi_image/run_all.py --save`
Expected: tabela com fastobjects em 1º; valida que N sprites de 8 imagens saem
em 1 draw call e mais rápido que arcade/pyglet. Se fastobjects não vencer,
investigar com systematic-debugging antes de commitar.

- [ ] **Step 7: Re-rodar a arena (sem regressão)** — `.venv\Scripts\python benchmarks/arena/run_all.py --save --label "pós-atlas"`
Expected: fastobjects na mesma ordem de grandeza do baseline (a coluna `uv` é
fria e sobe uma vez para imagem única). Regressão real = investigar.

- [ ] **Step 8: Lint + commit**

```powershell
git add benchmarks/multi_image benchmarks/RESULTS.md
git commit -m "bench: multi-image atlas benchmark vs arcade and pyglet"
```

---

### Task 6: Docs (guia + API, EN/PT) + exemplo de animação

**Files:**
- Modify: `docs/site/guide/sprites.md` e `.pt.md` (seção de atlas), `docs/site/api.md` e `.pt.md` (`images`, `image`, `group.image`)
- Create: `examples/atlas_animation.py`

- [ ] **Step 1: `examples/atlas_animation.py`** — gera um spritesheet de K frames
  (cores girando), `SpriteBatch(frames, capacity=...)`, um grupo, e anima
  `group.image = (frame // held) % K` a cada frame; `--frames N` auto-teste;
  ESC sai. Verificar com `--frames 120`.

- [ ] **Step 2: Seção "Multiple images (atlas)"** em `guide/sprites.md` (EN):
  criar batch com lista/dict, `spawn(image=)` escalar e array, `group.image`
  para animação de spritesheet, limites (estático; `GL_MAX_TEXTURE_SIZE`),
  snippet executável. Espelhar em `.pt.md`.

- [ ] **Step 3: API reference** (`api.md`/`.pt.md`): assinatura `SpriteBatch(images, ...)`
  (str/list/dict), o parâmetro `image` em `spawn`, e `group.image`.

- [ ] **Step 4: Build estrito** — `.venv\Scripts\python -m mkdocs build --strict`

- [ ] **Step 5: Verificar o exemplo** — `.venv\Scripts\python examples/atlas_animation.py --frames 120`

- [ ] **Step 6: Lint + commit**

```powershell
git add docs/site examples/atlas_animation.py
git commit -m "docs: atlas guide, API reference and spritesheet animation example"
```

---

### Task 7: Release 0.5.0

- [ ] **Step 1:** Bump 0.4.0 → 0.5.0 (pyproject, `__init__`, test_smoke — via Edit, sem BOM); suíte verde; `git commit -m "chore: bump to 0.5.0 - texture atlas"`.
- [ ] **Step 2:** Merge em main via superpowers:finishing-a-development-branch (suíte → merge → suíte → delete branch → push).
- [ ] **Step 3:** Tag `v0.5.0` + push; pre-release GitHub via REST API (token de `git credential fill`); notas com a feature de atlas + números do benchmark multi-imagem. Acompanhar `publish.yml` e o docs workflow até success (re-executar jobs se um 503 do OIDC reincidir, como no 0.4.0); confirmar PyPI 0.5.0.

---

## Fora deste plano

Atlas dinâmico (add/remove/resize em runtime); texture array; mipmaps — fases futuras.
