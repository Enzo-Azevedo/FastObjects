# FastObjects Interop (hosts externos + despawn) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** FastObjects utilizável dentro de janelas de outras bibliotecas (`fo.attach()`), com remoção real de grupos (`despawn`) e composição de Surfaces clássicas do pygame (`fo.SurfaceLayer`), fechando com o exemplo pygame completo e a release 0.2.0.

**Architecture:** A lógica comum dos batches (alocação, registro de grupos por weakref, despawn com compactação vetorizada, clear com invalidação) sobe para uma base interna `BatchCore`; `fo.attach()` conecta um `ExternalWindow` ao contexto GL corrente do host e o registra como janela atual; `SurfaceLayer` reusa o `SpriteRenderer` com uma textura dinâmica alimentada por `pygame.image.tobytes` (lazy import). Spec: `docs/superpowers/specs/2026-07-07-fastobjects-interop-design.md`.

**Tech Stack:** Python 3.13, moderngl, glfw, numpy, pillow (core); pygame-ce (opcional em runtime: lazy import no SurfaceLayer, `importorskip` nos testes, exemplo); pytest, ruff (dev).

## Global Constraints

- Dependências do core em `pyproject.toml`: **apenas** `numpy`, `moderngl`, `glfw`, `pillow` — pygame NUNCA vira dependência (lazy import dentro de método; testes com `pytest.importorskip`).
- Nenhum loop Python por sprite — despawn é UMA cópia vetorizada; o registro de grupos só é tocado em spawn/despawn/clear (nunca em draw ou nas views).
- Mensagens de erro acionáveis (dizem o que fazer, valores/caminhos concretos).
- Benches da arena mantêm o loop manual; nenhum arquivo de benchmark muda nesta fase.
- Testes offscreen (moderngl standalone) sempre que possível; attach usa `Window(visible=False)` como host GL.
- Commits **sem** trailer `Co-Authored-By`.
- Suíte completa (`.venv\Scripts\python -m pytest -v`) verde antes de cada commit. Baseline: 64 testes.
- Shell: PowerShell 5.1 (sem `&&`; usar `;`).

---

### Task 1: `BatchCore` — base comum + registro de grupos + clear que invalida

**Files:**
- Create: `fastobjects/_batchcore.py`
- Modify: `fastobjects/group.py` (flag `_alive` + checagens + registro de sub-grupos)
- Modify: `fastobjects/batch.py` (SpriteBatch herda da base)
- Modify: `fastobjects/shapes.py` (ShapeBatch herda da base)
- Test: `tests/test_group.py` (novos testes de invalidação)

**Interfaces:**
- Consumes: `SpriteGroup` (group.py), `CapacityError` (errors.py), estado atual de SpriteBatch/ShapeBatch.
- Produces (usado pelos Tasks 2, 3, 4):
  - `class BatchCore` em `_batchcore.py`: `__init__(capacity: int, floats: int, unit: str)` (guard `capacity<=0` + `data (capacity, floats) f4` + `count=0` + registro weakref), `_alloc(n: int, method: str) -> slice`, `_register(group) -> None`, `_make_group(s: slice) -> SpriteGroup`, `clear() -> None` (invalida todos os grupos), `draw() -> None`.
  - `SpriteGroup._alive: bool`, `SpriteGroup._check_alive() -> None` (RuntimeError acionável com "removido"), todas as propriedades/`len`/`getitem`/`slice` checam antes de acessar; `group[a:b]` registra o sub-grupo no batch via `batch._register`.
  - Comportamento público de spawn/rects/circles/lines/draw **inalterado** (mesmas mensagens de erro; suíte atual continua verde).

- [ ] **Step 1: Escrever os testes novos (falhando)**

Adicionar ao final de `tests/test_group.py`:

```python
def test_clear_invalidates_groups(ctx):
    batch = make_batch(ctx)
    g = batch.spawn(5)
    batch.clear()
    with pytest.raises(RuntimeError, match="removido"):
        g.x
    with pytest.raises(RuntimeError, match="removido"):
        g.x = 1.0
    with pytest.raises(RuntimeError, match="removido"):
        len(g)
    with pytest.raises(RuntimeError, match="removido"):
        g[0:1]


def test_shapebatch_clear_invalidates_groups(ctx):
    from fastobjects.shapes import ShapeBatch

    batch = ShapeBatch(capacity=10, ctx=ctx, view_size=(64, 64))
    g = batch.rects(3)
    batch.clear()
    with pytest.raises(RuntimeError, match="removido"):
        g.color


def test_subgroup_is_registered_and_invalidated_by_clear(ctx):
    batch = make_batch(ctx)
    g = batch.spawn(10)
    sub = g[2:5]
    batch.clear()
    with pytest.raises(RuntimeError, match="removido"):
        sub.y


def test_new_groups_after_clear_work(ctx):
    batch = make_batch(ctx)
    batch.spawn(5)
    batch.clear()
    fresh = batch.spawn(3, x=9.0)
    np.testing.assert_allclose(fresh.x, 9.0)
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_group.py -v`
Expected: os 4 novos FALHAM (clear atual não invalida — nenhum RuntimeError é levantado); os antigos passam.

- [ ] **Step 3: Implementar `fastobjects/_batchcore.py`**

```python
"""Base interna dos batches: alocação, registro de grupos, despawn e clear."""

from __future__ import annotations

import weakref

import numpy as np

from fastobjects.errors import CapacityError
from fastobjects.group import SpriteGroup


class BatchCore:
    """Estado e ciclo de vida comuns a SpriteBatch e ShapeBatch.

    Mantém o array `data`, o contador `count` e um registro (weakrefs) dos
    grupos vivos — tocado apenas em spawn/despawn/clear, nunca no caminho
    quente de draw. Subclasses definem `_renderer` no próprio __init__.

    Args:
        capacity: número máximo de linhas do lote.
        floats: colunas de `data` (9 para sprites, 10 para formas).
        unit: nome plural dos objetos nas mensagens de erro ("sprites"/"formas").
    """

    def __init__(self, capacity: int, floats: int, unit: str) -> None:
        if capacity <= 0:
            raise ValueError(
                f"capacity={capacity} inválida: use um valor > 0 "
                f"(quantidade máxima de {unit} do lote)."
            )
        self.capacity = capacity
        self.count = 0
        self.data = np.zeros((capacity, floats), dtype="f4")
        self._groups: weakref.WeakSet[SpriteGroup] = weakref.WeakSet()

    def _alloc(self, n: int, method: str) -> slice:
        """Reserva n linhas contíguas; mensagens acionáveis."""
        if n < 0:
            raise ValueError(f"{method}({n}): n não pode ser negativo. Use n >= 0.")
        if self.count + n > self.capacity:
            raise CapacityError(
                f"{method}({n}) excede a capacidade: {self.count} usados de "
                f"{self.capacity}. Crie o batch com capacity={self.count + n} ou mais."
            )
        s = slice(self.count, self.count + n)
        self.count += n
        return s

    def _register(self, group: SpriteGroup) -> None:
        self._groups.add(group)

    def _make_group(self, s: slice) -> SpriteGroup:
        group = SpriteGroup(self, s)
        self._register(group)
        return group

    def clear(self) -> None:
        """Remove todos os objetos e invalida todos os handles de grupos."""
        self.count = 0
        for group in list(self._groups):
            group._alive = False
        self._groups.clear()

    def draw(self) -> None:
        """Sobe o estado atual e desenha o lote inteiro em um draw call."""
        self._renderer.render(self.data, self.count)
```

- [ ] **Step 4: Atualizar `fastobjects/group.py`**

Substituir o arquivo inteiro por:

```python
"""SpriteGroup: fatia de um batch com views NumPy que escrevem no array base."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from fastobjects._batchcore import BatchCore


class SpriteGroup:
    """Grupo de sprites contíguos de um batch. Um objeto por grupo, nunca por sprite.

    As propriedades são views do array do batch: operações in-place
    (`group.y += v`) escrevem direto no estado, sem cópia. Funciona para
    qualquer batch cujo `data` tenha as colunas 0-8 no layout
    x, y, w, h, rot, r, g, b, a (SpriteBatch e ShapeBatch).

    Após `batch.despawn(grupo)` ou `batch.clear()`, o handle fica inválido:
    qualquer acesso levanta RuntimeError.

    Args:
        batch: dono do array `data` (um BatchCore).
        s: slice absoluto das linhas deste grupo em `batch.data`.
    """

    def __init__(self, batch: BatchCore, s: slice) -> None:
        self._batch = batch
        self._slice = s
        self._alive = True

    def _check_alive(self) -> None:
        if not self._alive:
            raise RuntimeError(
                "Grupo removido do batch (despawn/clear) — handles removidos "
                "não são reutilizáveis; use spawn() para criar novos objetos."
            )

    @property
    def slice(self) -> slice:
        """Slice absoluto das linhas deste grupo no array do batch."""
        self._check_alive()
        return self._slice

    def __len__(self) -> int:
        self._check_alive()
        return self._slice.stop - self._slice.start

    def __getitem__(self, sub: slice) -> SpriteGroup:
        self._check_alive()
        if not isinstance(sub, slice):
            raise TypeError(
                "SpriteGroup aceita apenas slices (grupo[a:b]); não há handle "
                "individual — para um sprite use grupo[i:i+1]."
            )
        start, stop, step = sub.indices(len(self))
        if step != 1:
            raise ValueError("SpriteGroup não suporta step em slices (use passo 1).")
        base = self._slice.start
        group = SpriteGroup(self._batch, slice(base + start, base + stop))
        self._batch._register(group)
        return group

    # --- colunas escalares -------------------------------------------------

    @property
    def x(self) -> np.ndarray:
        self._check_alive()
        return self._batch.data[self._slice, 0]

    @x.setter
    def x(self, value) -> None:
        self._check_alive()
        self._batch.data[self._slice, 0] = value

    @property
    def y(self) -> np.ndarray:
        self._check_alive()
        return self._batch.data[self._slice, 1]

    @y.setter
    def y(self, value) -> None:
        self._check_alive()
        self._batch.data[self._slice, 1] = value

    @property
    def w(self) -> np.ndarray:
        self._check_alive()
        return self._batch.data[self._slice, 2]

    @w.setter
    def w(self, value) -> None:
        self._check_alive()
        self._batch.data[self._slice, 2] = value

    @property
    def h(self) -> np.ndarray:
        self._check_alive()
        return self._batch.data[self._slice, 3]

    @h.setter
    def h(self, value) -> None:
        self._check_alive()
        self._batch.data[self._slice, 3] = value

    @property
    def rot(self) -> np.ndarray:
        self._check_alive()
        return self._batch.data[self._slice, 4]

    @rot.setter
    def rot(self, value) -> None:
        self._check_alive()
        self._batch.data[self._slice, 4] = value

    # --- blocos ------------------------------------------------------------

    @property
    def pos(self) -> np.ndarray:
        self._check_alive()
        return self._batch.data[self._slice, 0:2]

    @pos.setter
    def pos(self, value) -> None:
        self._check_alive()
        self._batch.data[self._slice, 0:2] = value

    @property
    def size(self) -> np.ndarray:
        self._check_alive()
        return self._batch.data[self._slice, 2:4]

    @size.setter
    def size(self, value) -> None:
        self._check_alive()
        self._batch.data[self._slice, 2:4] = value

    @property
    def color(self) -> np.ndarray:
        self._check_alive()
        return self._batch.data[self._slice, 5:9]

    @color.setter
    def color(self, value) -> None:
        self._check_alive()
        self._batch.data[self._slice, 5:9] = value
```

- [ ] **Step 5: SpriteBatch herda da base**

Em `fastobjects/batch.py`:

1. Trocar o import de `CapacityError` — a linha

```python
from fastobjects.errors import CapacityError
```

vira

```python
from fastobjects._batchcore import BatchCore
```

(o guard de capacity/CapacityError agora vive na base).

2. Trocar `class SpriteBatch:` por `class SpriteBatch(BatchCore):`.

3. Substituir o corpo de `__init__` (mantendo assinatura e docstring) por:

```python
    def __init__(
        self,
        texture_path: str,
        capacity: int,
        *,
        ctx: moderngl.Context | None = None,
        view_size: tuple[int, int] | None = None,
    ) -> None:
        super().__init__(capacity, FLOATS_PER_SPRITE, "sprites")
        ctx, view_size = _context.resolve(ctx, view_size)
        path = Path(texture_path)
        if not path.is_file():
            raise FileNotFoundError(
                f"Textura não encontrada: {path.resolve()} — verifique o caminho "
                "(relativo ao diretório de execução) ou use um caminho absoluto."
            )
        img = Image.open(path).convert("RGBA")
        texture = ctx.texture(img.size, 4, data=img.tobytes())
        self.texture_size = img.size
        self.pos = self.data[:, 0:2]
        self.size = self.data[:, 2:4]
        self.rot = self.data[:, 4]
        self.color = self.data[:, 5:9]
        self._renderer = SpriteRenderer(ctx, texture, capacity, view_size)
```

4. Em `spawn`, substituir os dois guards (o `if n < 0:` e o `if self.count + n > self.capacity:` completos, incluindo os `raise`) e a linha `s = slice(self.count, self.count + n)` por:

```python
        s = self._alloc(n, "spawn")
```

e remover a linha `self.count += n` (a base já incrementa). A última linha muda de `return SpriteGroup(self, s)` para:

```python
        return self._make_group(s)
```

5. Remover os métodos `clear()` e `draw()` locais (herdam da base).

6. O import `from fastobjects.group import SpriteGroup` continua (a anotação de retorno de `spawn` usa o nome).

- [ ] **Step 6: ShapeBatch herda da base**

Em `fastobjects/shapes.py`:

1. Trocar `from fastobjects.errors import CapacityError` por `from fastobjects._batchcore import BatchCore`.

2. Trocar `class ShapeBatch:` por `class ShapeBatch(BatchCore):`.

3. Substituir o corpo de `__init__` (mantendo assinatura e docstring) por:

```python
    def __init__(
        self,
        capacity: int,
        *,
        ctx: moderngl.Context | None = None,
        view_size: tuple[int, int] | None = None,
    ) -> None:
        super().__init__(capacity, SHAPE_FLOATS, "formas")
        ctx, view_size = _context.resolve(ctx, view_size)
        self._renderer = _ShapeRenderer(ctx, capacity, view_size)
```

4. Remover o método `_alloc` local (herda da base, idêntico).

5. Em `rects`, `circles` e `lines`: trocar `return SpriteGroup(self, s)` por `return self._make_group(s)` (3 ocorrências).

6. Remover os métodos `clear()` e `draw()` locais.

- [ ] **Step 7: Rodar a suíte completa**

Run: `.venv\Scripts\python -m pytest -v`
Expected: `68 passed` (64 + 4 novos) — a refatoração não muda comportamento público; se algum teste antigo quebrar, a refatoração está errada (mensagens de erro devem ser byte a byte as mesmas).

- [ ] **Step 8: Commit**

```powershell
git add fastobjects/_batchcore.py fastobjects/group.py fastobjects/batch.py fastobjects/shapes.py tests/test_group.py
git commit -m "refactor: BatchCore base with group registry, clear invalidates handles"
```

---

### Task 2: `despawn()` — remoção real com compactação e handles sobreviventes

**Files:**
- Modify: `fastobjects/_batchcore.py` (método `despawn`)
- Test: `tests/test_despawn.py`

**Interfaces:**
- Consumes: `BatchCore` (Task 1): `data`, `count`, `_groups`, `SpriteGroup._alive`/`_slice`/`_check_alive`.
- Produces (usado pelo exemplo, Task 5):
  - `BatchCore.despawn(group: SpriteGroup) -> None` — herdado por SpriteBatch e ShapeBatch.
  - Regras pós-compactação sobre cada grupo vivo `g` vs trecho removido `[start, stop)`:
    o próprio grupo ou contido nele → invalidado; começa em/apos `stop` → desloca `n` à esquerda; contém o trecho → encolhe `n`; termina antes de `start` → intacto.

- [ ] **Step 1: Escrever os testes (falhando)**

`tests/test_despawn.py`:

```python
import moderngl
import numpy as np
import pytest

from fastobjects.batch import SpriteBatch
from fastobjects.shapes import ShapeBatch

BUNNY = "benchmarks/arena/assets/bunny.png"


@pytest.fixture(scope="module")
def gl():
    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.BLEND)
    fbo = ctx.framebuffer(color_attachments=[ctx.texture((64, 64), 4)])
    fbo.use()
    yield ctx, fbo
    ctx.release()


def make_batch(ctx, capacity=100):
    return SpriteBatch(BUNNY, capacity=capacity, ctx=ctx, view_size=(64, 64))


def test_despawn_compacts_and_frees_capacity(gl):
    ctx, _ = gl
    batch = make_batch(ctx, capacity=10)
    a = batch.spawn(6, x=1.0)
    batch.spawn(4, x=2.0)
    batch.despawn(a)
    assert batch.count == 4
    np.testing.assert_allclose(batch.data[:4, 0], 2.0)  # sobrevivente compactado
    batch.spawn(6)  # capacity devolvida: não levanta


def test_despawn_preserves_neighbor_data_exactly(gl):
    ctx, _ = gl
    batch = make_batch(ctx)
    a = batch.spawn(3, x=np.array([1.0, 2.0, 3.0], dtype=np.float32))
    middle = batch.spawn(2, x=99.0)
    c = batch.spawn(3, x=np.array([7.0, 8.0, 9.0], dtype=np.float32))
    before_a = batch.data[0:3].copy()
    batch.despawn(middle)
    np.testing.assert_array_equal(batch.data[0:3], before_a)  # antes: intacto
    np.testing.assert_allclose(c.x, [7.0, 8.0, 9.0])  # depois: realocado, dados ok
    np.testing.assert_allclose(a.x, [1.0, 2.0, 3.0])


def test_despawn_shifts_later_groups(gl):
    ctx, _ = gl
    batch = make_batch(ctx)
    a = batch.spawn(5)
    b = batch.spawn(5, x=42.0)
    batch.despawn(a)
    assert b.slice == slice(0, 5)
    np.testing.assert_allclose(b.x, 42.0)


def test_despawn_subgroup_shrinks_parent(gl):
    ctx, _ = gl
    batch = make_batch(ctx)
    g = batch.spawn(10, x=np.arange(10, dtype=np.float32))
    sub = g[4:7]
    batch.despawn(sub)
    assert len(g) == 7
    np.testing.assert_allclose(g.x, [0, 1, 2, 3, 7, 8, 9])
    with pytest.raises(RuntimeError, match="removido"):
        sub.x


def test_despawn_invalidates_group_and_contained(gl):
    ctx, _ = gl
    batch = make_batch(ctx)
    g = batch.spawn(10)
    inner = g[2:5]
    batch.despawn(g)
    with pytest.raises(RuntimeError, match="removido"):
        g.x
    with pytest.raises(RuntimeError, match="removido"):
        inner.x


def test_despawn_twice_raises(gl):
    ctx, _ = gl
    batch = make_batch(ctx)
    g = batch.spawn(5)
    batch.despawn(g)
    with pytest.raises(RuntimeError, match="removido"):
        batch.despawn(g)


def test_despawn_foreign_group_raises(gl):
    ctx, _ = gl
    b1 = make_batch(ctx)
    b2 = make_batch(ctx)
    g = b1.spawn(3)
    with pytest.raises(ValueError, match="outro batch"):
        b2.despawn(g)


def test_despawn_empty_group_is_noop_but_invalidates(gl):
    ctx, _ = gl
    batch = make_batch(ctx)
    g = batch.spawn(0)
    other = batch.spawn(5, x=3.0)
    batch.despawn(g)
    assert batch.count == 5
    np.testing.assert_allclose(other.x, 3.0)
    with pytest.raises(RuntimeError, match="removido"):
        len(g)


def test_despawn_after_despawn_chain(gl):
    ctx, _ = gl
    batch = make_batch(ctx)
    a = batch.spawn(3, x=1.0)
    b = batch.spawn(3, x=2.0)
    c = batch.spawn(3, x=3.0)
    batch.despawn(b)
    batch.despawn(a)
    assert batch.count == 3
    assert c.slice == slice(0, 3)
    np.testing.assert_allclose(c.x, 3.0)


def test_shapebatch_despawn_works_the_same(gl):
    ctx, _ = gl
    batch = ShapeBatch(capacity=10, ctx=ctx, view_size=(64, 64))
    a = batch.rects(4, x=1.0)
    b = batch.circles(3, x=2.0)
    batch.despawn(a)
    assert batch.count == 3
    assert b.slice == slice(0, 3)
    np.testing.assert_allclose(b.x, 2.0)


def test_despawn_pixel_only_remaining_group_visible(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    batch = ShapeBatch(capacity=10, ctx=ctx, view_size=(64, 64))
    left = batch.rects(1, x=16.0, y=32.0, w=10.0, h=10.0, color=(1.0, 0.0, 0.0, 1.0))
    batch.rects(1, x=48.0, y=32.0, w=10.0, h=10.0, color=(0.0, 1.0, 0.0, 1.0))
    batch.despawn(left)
    batch.draw()
    raw = np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(64, 64, 4)[::-1]
    assert raw[32, 16][0] < 10  # vermelho removido não aparece
    assert raw[32, 48][1] > 200  # verde continua
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_despawn.py -v`
Expected: FAIL com `AttributeError: ... has no attribute 'despawn'`

- [ ] **Step 3: Implementar `despawn` na base**

Adicionar em `fastobjects/_batchcore.py`, entre `_make_group` e `clear`:

```python
    def despawn(self, group: SpriteGroup) -> None:
        """Remove as linhas do grupo, compactando o array (1 cópia vetorizada).

        Os demais grupos vivos são realocados automaticamente: grupos
        posteriores deslocam para a esquerda; um grupo que contém o trecho
        removido (pai de sub-grupo) encolhe. O grupo removido — e sub-grupos
        contidos nele — ficam inválidos.

        Raises:
            ValueError: se o grupo pertence a outro batch.
            RuntimeError: se o grupo já foi removido.
        """
        if group._batch is not self:
            raise ValueError(
                "despawn: o grupo pertence a outro batch — chame despawn "
                "no batch que o criou."
            )
        group._check_alive()
        start, stop = group._slice.start, group._slice.stop
        n = stop - start
        if n:
            self.data[start : self.count - n] = self.data[stop : self.count]
            self.count -= n
        for g in list(self._groups):
            gs, ge = g._slice.start, g._slice.stop
            if g is group or (gs >= start and ge <= stop):
                g._alive = False
                self._groups.discard(g)
            elif gs >= stop:
                g._slice = slice(gs - n, ge - n)
            elif gs <= start and ge >= stop:
                g._slice = slice(gs, ge - n)
            # senão: termina antes do trecho removido — intacto.
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv\Scripts\python -m pytest -v`
Expected: `79 passed` (68 + 11).

- [ ] **Step 5: Commit**

```powershell
git add fastobjects/_batchcore.py tests/test_despawn.py
git commit -m "feat: despawn with vectorized compaction and surviving group handles"
```

---

### Task 3: `fo.attach()` + `ExternalWindow`

**Files:**
- Create: `fastobjects/external.py`
- Modify: `fastobjects/__init__.py` (exports)
- Test: `tests/test_external.py`

**Interfaces:**
- Consumes: `_context.set_current/get_current` (protocolo informal `ctx/width/height`, o mesmo de `Window`); `moderngl.create_context()` (conecta ao contexto GL corrente).
- Produces (usado pelo Task 4 implicitamente e pelo exemplo, Task 5):
  - `attach(view_size: tuple[int, int]) -> ExternalWindow` — exportado como `fastobjects.attach`.
  - `class ExternalWindow`: `.ctx: moderngl.Context`, `.width: int`, `.height: int`, `.clear(r, g, b) -> None`, `.close() -> None` (desregistra se atual). **Sem** run/frame/keys/mouse/swap.

- [ ] **Step 1: Escrever os testes (falhando)**

`tests/test_external.py`:

```python
import moderngl
import numpy as np
import pytest

import fastobjects as fo
from fastobjects import Window, _context
from fastobjects.shapes import ShapeBatch


def test_attach_registers_external_window_as_current():
    host = Window(320, 240, "host", visible=False)  # host GL genérico
    ext = fo.attach(view_size=(320, 240))
    assert isinstance(ext, fo.ExternalWindow)
    assert _context.get_current() is ext
    assert (ext.width, ext.height) == (320, 240)
    ext.close()
    assert _context.get_current() is None
    host.close()


def test_attach_implicit_batch_draws_pixels():
    host = Window(320, 240, "host2", visible=False)
    ext = fo.attach(view_size=(320, 240))
    fbo = ext.ctx.framebuffer(color_attachments=[ext.ctx.texture((64, 64), 4)])
    fbo.use()
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    batch = ShapeBatch(capacity=4, view_size=(64, 64))  # ctx implícito do attach
    batch.rects(1, x=32.0, y=32.0, w=20.0, h=20.0, color=(1.0, 0.0, 0.0, 1.0))
    batch.draw()
    raw = np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(64, 64, 4)[::-1]
    assert raw[32, 32][0] > 200
    ext.close()
    host.close()


def test_external_window_clear_fills_target():
    host = Window(320, 240, "host3", visible=False)
    ext = fo.attach(view_size=(320, 240))
    fbo = ext.ctx.framebuffer(color_attachments=[ext.ctx.texture((8, 8), 4)])
    fbo.use()
    ext.clear(1.0, 0.0, 0.0)
    raw = np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(8, 8, 4)
    assert raw[:, :, 0].min() > 200
    ext.close()
    host.close()


def test_attach_without_gl_context_raises_actionable(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("cannot detect context")

    monkeypatch.setattr(moderngl, "create_context", boom)
    with pytest.raises(RuntimeError, match="pygame.OPENGL"):
        fo.attach(view_size=(100, 100))
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_external.py -v`
Expected: FAIL com `AttributeError: module 'fastobjects' has no attribute 'attach'`

- [ ] **Step 3: Implementar `fastobjects/external.py`**

```python
"""Attach a janelas de hosts externos (pygame, pyglet, ...) via contexto GL corrente."""

from __future__ import annotations

import moderngl

from fastobjects import _context


class ExternalWindow:
    """Janela de um host externo à qual o FastObjects se conectou.

    O host é dono do loop, dos eventos, do input e do swap/flip; este objeto
    expõe apenas o contexto GL e utilitários de render.

    Args:
        ctx: contexto moderngl conectado ao contexto GL do host.
        width: largura da área de render do host, em pixels.
        height: altura da área de render do host, em pixels.
    """

    def __init__(self, ctx: moderngl.Context, width: int, height: int) -> None:
        self.ctx = ctx
        self.width = width
        self.height = height

    def clear(self, r: float, g: float, b: float) -> None:
        """Limpa o alvo de render atual com a cor dada."""
        self.ctx.clear(r, g, b, 1.0)

    def close(self) -> None:
        """Desregistra esta janela como atual (o host continua dono da janela)."""
        if _context.get_current() is self:
            _context.set_current(None)


def attach(view_size: tuple[int, int]) -> ExternalWindow:
    """Conecta o FastObjects ao contexto OpenGL corrente do host.

    Chame DEPOIS de o host criar a janela com contexto OpenGL. A janela
    externa vira a "atual": batches criados sem ctx explícito passam a
    usá-la, como no modo nativo.

    Args:
        view_size: (largura, altura) da área de render do host, em pixels.

    Returns:
        ExternalWindow registrado como janela atual.

    Raises:
        RuntimeError: se não houver contexto OpenGL ativo no processo.
    """
    try:
        ctx = moderngl.create_context()
    except Exception as exc:
        raise RuntimeError(
            "Nenhum contexto OpenGL ativo. Crie a janela do host com OpenGL "
            "antes de fo.attach() — ex.: pygame.display.set_mode((w, h), "
            "pygame.OPENGL | pygame.DOUBLEBUF)."
        ) from exc
    ctx.enable(moderngl.BLEND)
    window = ExternalWindow(ctx, view_size[0], view_size[1])
    _context.set_current(window)
    return window
```

- [ ] **Step 4: Exportar no `__init__.py`**

Em `fastobjects/__init__.py`, adicionar o import (ordem alfabética, após `errors`):

```python
from fastobjects.external import ExternalWindow, attach
```

e atualizar `__all__` para:

```python
__all__ = [
    "CapacityError",
    "ExternalWindow",
    "ShapeBatch",
    "SpriteBatch",
    "SpriteGroup",
    "Window",
    "__version__",
    "attach",
]
```

- [ ] **Step 5: Rodar os testes**

Run: `.venv\Scripts\python -m pytest -v`
Expected: `83 passed` (79 + 4).

- [ ] **Step 6: Commit**

```powershell
git add fastobjects/external.py fastobjects/__init__.py tests/test_external.py
git commit -m "feat: fo.attach() connects FastObjects to any host GL window"
```

---

### Task 4: `fo.SurfaceLayer` — surfaces do pygame compostas pela GPU

**Files:**
- Create: `fastobjects/layer.py`
- Modify: `fastobjects/__init__.py` (export)
- Test: `tests/test_layer.py`

**Interfaces:**
- Consumes: `SpriteRenderer` (core/renderer.py: `SpriteRenderer(ctx, texture, capacity, view_size)`, `.render(data, count)`), `_context.resolve`.
- Produces (usado pelo exemplo, Task 5):
  - `SurfaceLayer(surface, *, ctx=None, view_size=None)` — `surface` é uma `pygame.Surface` (duck-typed: só precisa de `get_size()`); tamanho fixo na criação.
  - `.update() -> None` — sobe a surface para a GPU (lazy import de pygame AQUI; `ImportError` acionável sem pygame; `ValueError` se a surface mudou de tamanho).
  - `.draw() -> None` — 1 draw call; quad em (0,0) cobrindo o tamanho da surface.
  - Exportado como `fastobjects.SurfaceLayer`. pygame NÃO entra no pyproject.

- [ ] **Step 1: Escrever os testes (falhando)**

`tests/test_layer.py`:

```python
import moderngl
import numpy as np
import pytest

pygame = pytest.importorskip("pygame")

from fastobjects.layer import SurfaceLayer  # noqa: E402


@pytest.fixture(scope="module")
def gl():
    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.BLEND)
    fbo = ctx.framebuffer(color_attachments=[ctx.texture((64, 64), 4)])
    fbo.use()
    yield ctx, fbo
    ctx.release()


def read_pixels(fbo) -> np.ndarray:
    raw = np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(64, 64, 4)
    return raw[::-1]


def test_surface_layer_composites_pygame_drawing(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    surf = pygame.Surface((64, 64), pygame.SRCALPHA)
    pygame.draw.rect(surf, (255, 0, 0, 255), pygame.Rect(10, 10, 20, 20))
    layer = SurfaceLayer(surf, ctx=ctx, view_size=(64, 64))
    layer.update()
    layer.draw()
    px = read_pixels(fbo)
    assert px[15, 15][0] > 200  # dentro do retângulo (pygame top-down == y-baixo)
    assert px[50, 50][0] < 10  # área transparente: fundo intacto


def test_surface_layer_update_reflects_new_drawing(gl):
    ctx, fbo = gl
    surf = pygame.Surface((64, 64), pygame.SRCALPHA)
    layer = SurfaceLayer(surf, ctx=ctx, view_size=(64, 64))
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    layer.update()
    layer.draw()
    assert read_pixels(fbo)[32, 32][1] < 10  # ainda vazio
    pygame.draw.circle(surf, (0, 255, 0, 255), (32, 32), 8)
    layer.update()
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    layer.draw()
    assert read_pixels(fbo)[32, 32][1] > 200  # círculo apareceu


def test_surface_layer_size_change_raises(gl):
    ctx, _ = gl
    surf = pygame.Surface((32, 32), pygame.SRCALPHA)
    layer = SurfaceLayer(surf, ctx=ctx, view_size=(64, 64))
    layer._surface = pygame.Surface((16, 16), pygame.SRCALPHA)  # troca indevida
    with pytest.raises(ValueError, match="tamanho"):
        layer.update()
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_layer.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'fastobjects.layer'`

- [ ] **Step 3: Implementar `fastobjects/layer.py`**

```python
"""SurfaceLayer: surfaces desenhadas por CPU (ex.: pygame) compostas pela GPU."""

from __future__ import annotations

import moderngl
import numpy as np

from fastobjects import _context
from fastobjects.core.renderer import SpriteRenderer


class SurfaceLayer:
    """Compõe uma pygame.Surface (desenho clássico por CPU) na cena.

    A surface é desenhada como um quad texturizado em (0, 0) cobrindo o seu
    próprio tamanho, com o mesmo blending dos sprites. Fluxo por frame:
    desenhe na surface com a API do pygame, chame update() (1 upload) e
    draw() (1 draw call) na ordem de composição desejada.

    Args:
        surface: pygame.Surface (tamanho fixo na criação).
        ctx: contexto moderngl; se None, usa o da janela atual.
        view_size: (largura, altura) do alvo de render em pixels;
            se None, usa o tamanho da janela atual.
    """

    def __init__(
        self,
        surface,
        *,
        ctx: moderngl.Context | None = None,
        view_size: tuple[int, int] | None = None,
    ) -> None:
        ctx, view_size = _context.resolve(ctx, view_size)
        self._surface = surface
        w, h = surface.get_size()
        self._size = (int(w), int(h))
        self._texture = ctx.texture(self._size, 4)
        self._renderer = SpriteRenderer(ctx, self._texture, 1, view_size)
        self._data = np.zeros((1, 9), dtype="f4")
        self._data[0] = [w / 2.0, h / 2.0, w, h, 0.0, 1.0, 1.0, 1.0, 1.0]

    def update(self) -> None:
        """Sobe o conteúdo atual da surface para a GPU (1 upload).

        Raises:
            ImportError: se o pygame não estiver instalado.
            ValueError: se a surface tiver mudado de tamanho.
        """
        try:
            import pygame
        except ImportError as exc:
            raise ImportError(
                "SurfaceLayer precisa do pygame para ler a surface — "
                "instale com: pip install pygame-ce"
            ) from exc
        if self._surface.get_size() != self._size:
            raise ValueError(
                f"A surface mudou de tamanho: era {self._size}, agora "
                f"{self._surface.get_size()}. Crie um novo SurfaceLayer."
            )
        self._texture.write(pygame.image.tobytes(self._surface, "RGBA"))

    def draw(self) -> None:
        """Desenha a surface na tela (1 draw call)."""
        self._renderer.render(self._data, 1)
```

(Ordem de linhas: `pygame.image.tobytes(..., "RGBA")` entrega linhas de cima para
baixo, exatamente a convenção y-para-baixo do renderer — sem flip.)

- [ ] **Step 4: Exportar no `__init__.py`**

Adicionar o import (ordem alfabética, após `group`):

```python
from fastobjects.layer import SurfaceLayer
```

e incluir `"SurfaceLayer"` no `__all__` (lista em ordem alfabética, entre
`"SpriteGroup"` e `"Window"`).

- [ ] **Step 5: Rodar os testes**

Run: `.venv\Scripts\python -m pytest -v`
Expected: `86 passed` (83 + 3).

- [ ] **Step 6: Commit**

```powershell
git add fastobjects/layer.py fastobjects/__init__.py tests/test_layer.py
git commit -m "feat: SurfaceLayer composites classic pygame surfaces on the GPU"
```

---

### Task 5: Exemplo `examples/pygame_interop.py`

**Files:**
- Create: `examples/pygame_interop.py`

**Interfaces:**
- Consumes: TODA a fase — `fo.attach`, `SpriteBatch`/`ShapeBatch`, `spawn`/`despawn`, `SurfaceLayer` — mais pygame (janela `OPENGL|DOUBLEBUF`, eventos, fonte, mouse).
- Produces: o critério de aceite da fase; primeiro arquivo de `examples/`.

- [ ] **Step 1: Escrever o exemplo**

`examples/pygame_interop.py`:

```python
"""FastObjects + pygame: janela/loop/eventos do pygame, objetos do fastobjects.

Requisitos: pygame-ce instalado (já vem com `pip install -e .[bench]` neste
repositório, ou `pip install pygame-ce`). Rode da raiz do repositório:

    .venv\\Scripts\\python examples/pygame_interop.py               # interativo
    .venv\\Scripts\\python examples/pygame_interop.py --frames 120  # auto-teste

Controles: clique esquerdo spawna 100 coelhos no cursor; D remove o último
grupo spawnado; ESC sai. O HUD (texto e círculo no cursor) é desenhado com a
API clássica do pygame numa Surface, composta na GPU pelo SurfaceLayer.
"""

import argparse
from pathlib import Path

import numpy as np
import pygame

import fastobjects as fo

WIDTH, HEIGHT = 1280, 720
BUNNY = Path(__file__).resolve().parent.parent / "benchmarks" / "arena" / "assets" / "bunny.png"
GRAVITY = 980.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--frames", type=int, default=0, help="roda N frames e sai (auto-teste)"
    )
    args = parser.parse_args()

    pygame.init()
    pygame.display.set_mode((WIDTH, HEIGHT), pygame.OPENGL | pygame.DOUBLEBUF)
    pygame.display.set_caption("fastobjects + pygame")

    ext = fo.attach(view_size=(WIDTH, HEIGHT))

    batch = fo.SpriteBatch(str(BUNNY), capacity=200_000)
    shapes = fo.ShapeBatch(capacity=64)
    shapes.lines(
        1, x1=0.0, y1=HEIGHT - 2.0, x2=float(WIDTH), y2=HEIGHT - 2.0,
        width=3.0, color=(0.2, 0.9, 0.2, 1.0),
    )

    hud_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    hud = fo.SurfaceLayer(hud_surface)
    font = pygame.font.Font(None, 28)

    rng = np.random.default_rng(42)
    groups: list[fo.SpriteGroup] = []
    velocities: list[np.ndarray] = []

    def spawn_at(x: float, y: float) -> None:
        n = 100
        groups.append(batch.spawn(n, x=x, y=y))
        v = np.empty((n, 2), dtype=np.float32)
        v[:, 0] = rng.uniform(-200, 200, n)
        v[:, 1] = rng.uniform(-300, 0, n)
        velocities.append(v)

    def despawn_last() -> None:
        if groups:
            batch.despawn(groups.pop())
            velocities.pop()

    spawn_at(WIDTH / 2, HEIGHT / 3)

    clock = pygame.time.Clock()
    frame = 0
    running = True
    while running:
        dt = min(clock.tick() / 1000.0, 1.0 / 30.0)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_d:
                    despawn_last()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                spawn_at(float(event.pos[0]), float(event.pos[1]))

        # física vetorizada direto nas views dos grupos (loop por GRUPO, não por sprite)
        for g, v in zip(groups, velocities):
            v[:, 1] += GRAVITY * dt
            g.pos += v * dt
            hit_floor = g.y > HEIGHT
            v[hit_floor, 1] *= -0.85
            g.y = np.minimum(g.y, HEIGHT)

        # HUD com a API clássica do pygame
        hud_surface.fill((0, 0, 0, 0))
        text = font.render(
            f"sprites: {batch.count}  |  clique: +100  |  D: remove grupo  |  ESC: sai",
            True,
            (255, 255, 255),
        )
        hud_surface.blit(text, (10, 10))
        mx, my = pygame.mouse.get_pos()
        pygame.draw.circle(hud_surface, (255, 200, 0), (mx, my), 12, width=2)

        # render fastobjects + composição, flip do pygame
        ext.clear(0.08, 0.08, 0.10)
        batch.draw()
        shapes.draw()
        hud.update()
        hud.draw()
        pygame.display.flip()

        frame += 1
        if args.frames:
            if frame == args.frames // 2:
                spawn_at(WIDTH / 4, HEIGHT / 4)  # exercita spawn no modo auto
            if frame == args.frames // 2 + 10:
                despawn_last()  # e despawn
            if frame >= args.frames:
                running = False

    count = batch.count
    pygame.quit()
    print(f"interop ok: {frame} frames, {count} sprites")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Rodar o auto-teste**

Run (da raiz do repo): `.venv\Scripts\python examples/pygame_interop.py --frames 120`
Expected: janela pygame abre por ~2s com coelhos caindo, linha verde no chão e HUD de texto; imprime `interop ok: 120 frames, 100 sprites` (100 iniciais + 100 no meio − 100 do despawn). Qualquer exceção = falha do aceite; investigar antes de commitar.

- [ ] **Step 3: Rodar a suíte e o lint**

Run: `.venv\Scripts\python -m pytest -v`
Expected: `86 passed`.

Run: `.venv\Scripts\python -m ruff check fastobjects tests examples`
Expected: sem erros (corrigir o que aparecer).

- [ ] **Step 4: Commit**

```powershell
git add examples/pygame_interop.py
git commit -m "feat: pygame interop example - host window, fastobjects objects, pygame HUD"
```

---

### Task 6: Higiene final + versão 0.2.0

**Files:**
- Modify: `pyproject.toml` (version)
- Modify: `fastobjects/__init__.py` (`__version__`)
- Modify: `tests/test_smoke.py` (assert da versão)
- Modify: `benchmarks/RESULTS.md` (via `run_all.py --save`)

**Interfaces:**
- Consumes: fase completa (Tasks 1–5).
- Produces: versão 0.2.0 pronta para a tag; arena confirmada sem regressão.

- [ ] **Step 1: Bump de versão**

Em `pyproject.toml`: `version = "0.1.0"` → `version = "0.2.0"`.
Em `fastobjects/__init__.py`: `__version__ = "0.1.0"` → `__version__ = "0.2.0"`.
Em `tests/test_smoke.py`: `assert fastobjects.__version__ == "0.1.0"` → `assert fastobjects.__version__ == "0.2.0"`.

- [ ] **Step 2: Rodar a arena (higiene — nada do caminho medido mudou)**

Run: `.venv\Scripts\python benchmarks/arena/run_all.py --save` (timeout 600000 ms; 5 janelas abrem)
Expected: fastobjects em 1º na mesma ordem de grandeza do baseline (218.809; um passo de ramp de variação é normal). Regressão real = parar e investigar com systematic-debugging (o registro de grupos não pode ter custo mensurável: o bench descarta o retorno de spawn, então o weakref morre na hora).

Depois, em `benchmarks/RESULTS.md`, renomear o heading recém-adicionado
`## Arena 2026-07-07` para `## Arena 2026-07-07 (pós-interop)` — os headings do
arquivo são todos rotulados.

- [ ] **Step 3: Suíte completa + lint**

Run: `.venv\Scripts\python -m pytest -v`
Expected: `86 passed` (test_smoke atualizado, não adicionado).

Run: `.venv\Scripts\python -m ruff check fastobjects tests examples`
Expected: sem erros.

- [ ] **Step 4: Commit**

```powershell
git add pyproject.toml fastobjects/__init__.py tests/test_smoke.py benchmarks/RESULTS.md
git commit -m "chore: bump to 0.2.0, arena re-run clean after interop"
```

---

### Task 7: Release 0.2.0 (PÓS-MERGE, executa em `main`)

**Files:**
- Nenhum — tag + release no GitHub.

**Interfaces:**
- Consumes: branch da fase merged em `main` (via superpowers:finishing-a-development-branch), suíte verde em `main`.
- Produces: tag `v0.2.0` + GitHub Release **pre-release**; PyPI atualizado pelo workflow.

**ATENÇÃO:** só roda DEPOIS do merge. O push da tag dispara `.github/workflows/publish.yml` → publicação no PyPI via trusted publishing (funcionou no v0.1.0). **Não há `gh` CLI nesta máquina** — a release é criada via REST API com o token do `git credential fill` (ver memória do projeto; script de referência do v0.1.0).

- [ ] **Step 1: Confirmar main**

```powershell
git checkout main; git pull; git log --oneline -3
.venv\Scripts\python -m pytest
```

Expected: merge presente, `86 passed`.

- [ ] **Step 2: Tag**

```powershell
git tag -a v0.2.0 -m "FastObjects 0.2.0 - interop com hosts externos, despawn e SurfaceLayer (pre-1.0)"
git push origin v0.2.0
```

- [ ] **Step 3: Release via REST API**

Notas (arquivo temporário no scratchpad):

```markdown
# FastObjects v0.2.0 (pré-1.0)

FastObjects agora funciona **dentro de janelas de outras bibliotecas** — pygame
cria a janela e cuida de eventos/input/som; o FastObjects insere, atualiza,
**remove** e desenha os objetos.

## Novidades

- **`fo.attach(view_size=...)`** — conecta o FastObjects ao contexto OpenGL de
  qualquer host (pygame com `OPENGL | DOUBLEBUF`, pyglet, ...).
- **`batch.despawn(grupo)`** — remoção real com compactação vetorizada; os
  handles dos demais grupos continuam válidos (realocados automaticamente).
- **`fo.SurfaceLayer(surface)`** — desenho clássico do pygame (`pygame.draw`,
  `pygame.font`) composto na GPU junto com os batches.
- Exemplo completo: `examples/pygame_interop.py` (clique spawna, D remove,
  HUD com fonte do pygame).

86 testes; arena inalterada: 218.809 sprites @ 60fps (~38x o melhor concorrente).

Requisitos: Python >= 3.11, OpenGL 3.3 core. pygame é opcional (só para
SurfaceLayer/exemplo).
```

Criar a release com um script Python no molde do usado no v0.1.0 (POST
`/repos/Enzo-Azevedo/FastObjects/releases`, token de `git credential fill`,
`"tag_name": "v0.2.0"`, `"prerelease": true`, corpo = notas acima). Sem
imprimir o token.

Expected: URL da release impressa, `prerelease: True`.

- [ ] **Step 4: Verificar workflow + PyPI**

Verificar o run do `publish.yml` (API `/actions/runs?per_page=3`) até `completed`;
depois confirmar `https://pypi.org/pypi/fastobjects/json` com `version == "0.2.0"`.
Reportar o resultado ao usuário em qualquer caso (sucesso ou falha do publish).

---

## Fora deste plano

- Hosts pyglet/arcade/raylib (fase seguinte, um exemplo validado por host).
- Task de higiene acumulada (itens minor (g)–(o) do ledger + recomendações das
  fases anteriores) — candidata à Fase 5 junto com docs/README.
