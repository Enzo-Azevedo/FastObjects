# FastObjects Fase 4 (API pública) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Camada pública ergonômica sobre o core validado — frame loop (`@win.frame`/`run`), `SpriteGroup` vetorizado, `ShapeBatch` (retângulo/círculo/linha), input por polling e janela implícita — terminando com release pré-1.0 no GitHub (tag `v0.1.0` + pre-release).

**Architecture:** Evoluir as classes existentes (sem camada wrapper): `Window` ganha loop/input, `SpriteBatch.spawn` passa a retornar `SpriteGroup` (views NumPy no array do batch), `ShapeBatch` reusa o padrão instanciado com shader próprio (kind por instância; linha é açúcar da API). Um módulo interno `_context` guarda a janela atual para criação implícita de batches. Spec: `docs/superpowers/specs/2026-07-06-fastobjects-phase4-api-design.md`.

**Tech Stack:** Python 3.13, moderngl, glfw, numpy, pillow (core); pytest, ruff (dev).

## Global Constraints

- Dependências do core: **apenas** `numpy`, `moderngl`, `glfw`, `pillow`.
- Nenhum loop Python por sprite em caminho quente — sempre NumPy vetorizado; o frame loop e os grupos não adicionam trabalho por sprite.
- Mensagens de erro acionáveis (dizem o que fazer, valores esperados, caminho resolvido).
- Pré-1.0: quebras de assinatura são permitidas, mas todo consumidor no repositório (testes, benches) é atualizado **no mesmo task** — a suíte termina verde em todo task.
- Testes offscreen (moderngl standalone) sempre que possível; testes de janela/loop/input usam `Window(..., visible=False)`.
- Benches da arena **mantêm o loop manual** (`poll/clear/swap`) — é o protocolo de medição; não migrar para `run()`.
- Commits **sem** trailer `Co-Authored-By`.
- Rodar a suíte completa (`.venv\Scripts\python -m pytest -v`) antes de cada commit; todos os testes passam.
- Shell: PowerShell 5.1 (sem `&&`; usar `;`).

---

### Task 1: Janela implícita (`_context.py`) + registro na Window

**Files:**
- Create: `fastobjects/_context.py`
- Modify: `fastobjects/window.py` (registrar/desregistrar a janela atual)
- Test: `tests/test_context.py`

**Interfaces:**
- Consumes: `fastobjects.window.Window` existente (`.ctx`, `.width`, `.height`, `.close()`).
- Produces (usado pelos Tasks 2 e 7):
  - `_context.set_current(win: Window | None) -> None`
  - `_context.get_current() -> Window | None`
  - `_context.require_current() -> Window` — levanta `RuntimeError` acionável se não houver janela
  - `_context.resolve(ctx, view_size) -> tuple[moderngl.Context, tuple[int, int]]` — completa os argumentos com a janela atual quando `None`
  - `Window.__init__` registra a janela como atual; `Window.close()` desregistra se for a atual.

- [ ] **Step 1: Escrever os testes (falhando)**

`tests/test_context.py`:

```python
import pytest

from fastobjects import Window, _context


def test_window_registers_as_current():
    win = Window(320, 240, "ctx", visible=False)
    assert _context.get_current() is win
    win.close()
    assert _context.get_current() is None


def test_second_window_becomes_current():
    a = Window(320, 240, "a", visible=False)
    b = Window(320, 240, "b", visible=False)
    assert _context.get_current() is b
    b.close()
    a.close()


def test_close_non_current_window_keeps_current():
    a = Window(320, 240, "a", visible=False)
    b = Window(320, 240, "b", visible=False)
    a.close()  # a não é a atual; b continua registrada
    assert _context.get_current() is b
    b.close()


def test_require_current_raises_actionable():
    _context.set_current(None)
    with pytest.raises(RuntimeError, match="fo.Window"):
        _context.require_current()


def test_resolve_uses_current_window():
    win = Window(320, 240, "res", visible=False)
    ctx, view_size = _context.resolve(None, None)
    assert ctx is win.ctx
    assert view_size == (320, 240)
    win.close()


def test_resolve_explicit_args_pass_through():
    _context.set_current(None)
    sentinel = object()
    ctx, view_size = _context.resolve(sentinel, (64, 64))
    assert ctx is sentinel
    assert view_size == (64, 64)
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_context.py -v`
Expected: FAIL com `ImportError: cannot import name '_context'`

- [ ] **Step 3: Implementar `fastobjects/_context.py`**

```python
"""Registro interno da janela 'atual' para criação implícita de batches."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import moderngl

    from fastobjects.window import Window

_current: Window | None = None


def set_current(win: Window | None) -> None:
    """Define a janela atual (chamado por Window.__init__/close)."""
    global _current
    _current = win


def get_current() -> Window | None:
    """Retorna a janela atual, ou None se nenhuma foi criada."""
    return _current


def require_current() -> Window:
    """Retorna a janela atual ou levanta um erro acionável."""
    if _current is None:
        raise RuntimeError(
            "Nenhuma janela ativa. Crie fo.Window(...) antes de criar batches, "
            "ou passe ctx= e view_size= explicitamente."
        )
    return _current


def resolve(
    ctx: moderngl.Context | None,
    view_size: tuple[int, int] | None,
) -> tuple[moderngl.Context, tuple[int, int]]:
    """Completa ctx/view_size com a janela atual quando não fornecidos."""
    if ctx is not None and view_size is not None:
        return ctx, view_size
    win = require_current()
    return (
        ctx if ctx is not None else win.ctx,
        view_size if view_size is not None else (win.width, win.height),
    )
```

- [ ] **Step 4: Registrar na Window**

Em `fastobjects/window.py`, adicionar o import (após `import moderngl`):

```python
from fastobjects import _context
```

No final de `Window.__init__` (após `self.height = height`):

```python
        _context.set_current(self)
```

Em `Window.close()`, antes de destruir a janela:

```python
    def close(self) -> None:
        if _context.get_current() is self:
            _context.set_current(None)
        if self._win is not None:
            glfw.destroy_window(self._win)
            self._win = None
```

Exportar `_context` no `fastobjects/__init__.py` NÃO é necessário — o teste importa `from fastobjects import _context`, que funciona por ser submódulo (o import direto o carrega).

- [ ] **Step 5: Rodar os testes**

Run: `.venv\Scripts\python -m pytest tests/test_context.py -v`
Expected: `6 passed`

Run: `.venv\Scripts\python -m pytest -v`
Expected: todos passam (25 existentes + 6 novos)

- [ ] **Step 6: Commit**

```powershell
git add fastobjects/_context.py fastobjects/window.py tests/test_context.py
git commit -m "feat: implicit current-window registry for batch creation"
```

---

### Task 2: Nova assinatura do SpriteBatch (ctx opcional + erro de textura)

**Files:**
- Modify: `fastobjects/batch.py` (assinatura de `__init__`)
- Modify: `tests/test_batch.py` (chamadas de construtor + 2 testes novos)
- Modify: `benchmarks/arena/bench_fastobjects.py` (linha do construtor)

**Interfaces:**
- Consumes: `_context.resolve` (Task 1).
- Produces (assinatura pública final, usada pelo Task 12 da Fase 1–3 e pelo aceite):
  - `SpriteBatch(texture_path: str, capacity: int, *, ctx: moderngl.Context | None = None, view_size: tuple[int, int] | None = None)` — **QUEBRA**: antes era `SpriteBatch(ctx, texture_path, capacity, view_size)`.
  - `FileNotFoundError` acionável para textura inexistente (mostra o caminho resolvido).
  - `spawn`/`clear`/`draw` inalterados neste task (spawn ainda retorna `slice`; muda no Task 3).

- [ ] **Step 1: Escrever os testes novos (falhando)**

Adicionar ao final de `tests/test_batch.py`:

```python
def test_missing_texture_raises_actionable_error(gl):
    ctx, _ = gl
    with pytest.raises(FileNotFoundError, match="nao_existe.png"):
        SpriteBatch("nao_existe.png", capacity=10, ctx=ctx, view_size=(64, 64))


def test_no_window_and_no_ctx_raises_actionable_error():
    from fastobjects import _context

    _context.set_current(None)
    with pytest.raises(RuntimeError, match="fo.Window"):
        SpriteBatch(BUNNY, capacity=10)
```

- [ ] **Step 2: Atualizar as chamadas de construtor nos testes existentes**

Em `tests/test_batch.py`, substituir cada ocorrência do padrão antigo pelo novo (keyword `ctx=` depois dos posicionais):

| Antes | Depois |
|---|---|
| `SpriteBatch(ctx, BUNNY, capacity=100, view_size=(64, 64))` | `SpriteBatch(BUNNY, capacity=100, ctx=ctx, view_size=(64, 64))` |
| `SpriteBatch(ctx, BUNNY, capacity=10, view_size=(64, 64))` | `SpriteBatch(BUNNY, capacity=10, ctx=ctx, view_size=(64, 64))` |
| `SpriteBatch(ctx, BUNNY, capacity=0, view_size=(64, 64))` | `SpriteBatch(BUNNY, capacity=0, ctx=ctx, view_size=(64, 64))` |
| `SpriteBatch(ctx, BUNNY, capacity=-1, view_size=(64, 64))` | `SpriteBatch(BUNNY, capacity=-1, ctx=ctx, view_size=(64, 64))` |

(Ocorrências: `test_spawn_scalar_fills_rows`, `test_spawn_vectorized`, `test_spawn_appends_after_existing`, `test_spawn_over_capacity_raises_actionable_error`, `test_spawn_negative_n_raises_value_error`, `test_init_non_positive_capacity_raises_value_error` (2x), `test_clear_resets_count`, `test_views_write_through_to_data`, `test_draw_renders_pixels`.)

- [ ] **Step 3: Rodar para ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_batch.py -v`
Expected: FAIL — os testes atualizados quebram com `TypeError` (assinatura antiga ainda vigente).

- [ ] **Step 4: Implementar a nova assinatura**

Em `fastobjects/batch.py`, adicionar imports (após `from __future__ import annotations`):

```python
from pathlib import Path
```

e (após os imports de terceiros):

```python
from fastobjects import _context
```

Substituir `__init__` inteiro (docstring incluída) por:

```python
    def __init__(
        self,
        texture_path: str,
        capacity: int,
        *,
        ctx: moderngl.Context | None = None,
        view_size: tuple[int, int] | None = None,
    ) -> None:
        if capacity <= 0:
            raise ValueError(
                f"capacity={capacity} inválida: use um valor > 0 "
                "(quantidade máxima de sprites do lote)."
            )
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
        self.capacity = capacity
        self.count = 0
        self.data = np.zeros((capacity, FLOATS_PER_SPRITE), dtype="f4")
        self.pos = self.data[:, 0:2]
        self.size = self.data[:, 2:4]
        self.rot = self.data[:, 4]
        self.color = self.data[:, 5:9]
        self._renderer = SpriteRenderer(ctx, texture, capacity, view_size)
```

Atualizar a docstring da classe (o bloco `Args:`) para:

```python
    Args:
        texture_path: caminho de uma imagem (qualquer formato PIL).
        capacity: número máximo de sprites do lote.
        ctx: contexto moderngl; se None, usa o da janela atual.
        view_size: (largura, altura) do alvo de render em pixels;
            se None, usa o tamanho da janela atual.
```

- [ ] **Step 5: Atualizar o bench**

Em `benchmarks/arena/bench_fastobjects.py`, substituir:

```python
    batch = SpriteBatch(win.ctx, str(ASSET), capacity=MAX_CAPACITY, view_size=(WIDTH, HEIGHT))
```

por (a janela criada na linha anterior é a atual — dogfooding da API implícita):

```python
    batch = SpriteBatch(str(ASSET), capacity=MAX_CAPACITY)
```

- [ ] **Step 6: Rodar os testes**

Run: `.venv\Scripts\python -m pytest -v`
Expected: todos passam (33 testes; os benches não fazem parte da suíte).

- [ ] **Step 7: Commit**

```powershell
git add fastobjects/batch.py tests/test_batch.py benchmarks/arena/bench_fastobjects.py
git commit -m "feat!: SpriteBatch(texture_path, capacity) with implicit window context"
```

---

### Task 3: SpriteGroup (`group.py`) — spawn retorna grupo vetorizado

**Files:**
- Create: `fastobjects/group.py`
- Modify: `fastobjects/batch.py` (`spawn` retorna `SpriteGroup`)
- Modify: `tests/test_batch.py` (asserts de slice → grupo)
- Test: `tests/test_group.py`

**Interfaces:**
- Consumes: `SpriteBatch.data` (array `(capacity, 9) f4`) e o `slice` interno do spawn.
- Produces (usado pelo Task 7 e pelo aceite):
  - `class SpriteGroup(batch, s: slice)` — genérico: funciona com qualquer objeto que tenha `.data` com as colunas 0–8 no layout `x,y,w,h,rot,r,g,b,a`.
  - Propriedades leitura/escrita (views NumPy do array base): `.x`, `.y`, `.w`, `.h`, `.rot` (1D), `.pos` (n,2), `.size` (n,2), `.color` (n,4).
  - `.slice: slice` (absoluto no batch), `len(group)`, `group[a:b] -> SpriteGroup` (sub-slice relativo, sem step).
  - `SpriteBatch.spawn(...) -> SpriteGroup` — **QUEBRA**: retornava `slice`.

- [ ] **Step 1: Escrever os testes (falhando)**

`tests/test_group.py`:

```python
import moderngl
import numpy as np
import pytest

from fastobjects.batch import SpriteBatch
from fastobjects.group import SpriteGroup

BUNNY = "benchmarks/arena/assets/bunny.png"


@pytest.fixture(scope="module")
def ctx():
    ctx = moderngl.create_standalone_context()
    yield ctx
    ctx.release()


def make_batch(ctx, capacity=100):
    return SpriteBatch(BUNNY, capacity=capacity, ctx=ctx, view_size=(64, 64))


def test_spawn_returns_group(ctx):
    batch = make_batch(ctx)
    g = batch.spawn(10)
    assert isinstance(g, SpriteGroup)
    assert g.slice == slice(0, 10)
    assert len(g) == 10


def test_group_views_write_to_batch_data(ctx):
    batch = make_batch(ctx)
    g = batch.spawn(10, x=1.0, y=2.0)
    g.y += 100.0  # in-place na view: zero cópia
    assert batch.data[0, 1] == 102.0


def test_group_assignment_broadcasts(ctx):
    batch = make_batch(ctx)
    g = batch.spawn(5)
    g.x = 7.0
    np.testing.assert_allclose(batch.data[:5, 0], 7.0)
    g.color = (0.0, 1.0, 0.0, 1.0)
    np.testing.assert_allclose(batch.data[:5, 5:9], [[0.0, 1.0, 0.0, 1.0]] * 5)


def test_scalar_columns_and_size(ctx):
    batch = make_batch(ctx)
    g = batch.spawn(4)
    g.rot = 0.5
    np.testing.assert_allclose(batch.data[:4, 4], 0.5)
    g.w = 10.0
    g.h = 20.0
    np.testing.assert_allclose(batch.data[:4, 2], 10.0)
    np.testing.assert_allclose(batch.data[:4, 3], 20.0)
    np.testing.assert_allclose(g.size, [[10.0, 20.0]] * 4)
    np.testing.assert_allclose(g.pos[:, 0], g.x)


def test_subslice_offsets_into_batch(ctx):
    batch = make_batch(ctx)
    g = batch.spawn(20)
    sub = g[5:10]
    assert isinstance(sub, SpriteGroup)
    assert len(sub) == 5
    assert sub.slice == slice(5, 10)
    sub.x = 9.0
    np.testing.assert_allclose(batch.data[5:10, 0], 9.0)
    assert batch.data[4, 0] == 0.0  # vizinho intacto


def test_subslice_of_second_group_is_absolute(ctx):
    batch = make_batch(ctx)
    batch.spawn(10)
    b = batch.spawn(10)
    sub = b[2:4]
    assert sub.slice == slice(12, 14)


def test_two_groups_do_not_overlap(ctx):
    batch = make_batch(ctx)
    a = batch.spawn(10, x=1.0)
    b = batch.spawn(10, x=2.0)
    assert a.slice == slice(0, 10)
    assert b.slice == slice(10, 20)
    b.x = 5.0
    np.testing.assert_allclose(a.x, 1.0)


def test_getitem_requires_slice_without_step(ctx):
    batch = make_batch(ctx)
    g = batch.spawn(3)
    with pytest.raises(TypeError, match="slices"):
        g[0]
    with pytest.raises(ValueError, match="step"):
        g[::2]
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_group.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'fastobjects.group'`

- [ ] **Step 3: Implementar `fastobjects/group.py`**

```python
"""SpriteGroup: fatia de um batch com views NumPy que escrevem no array base."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from fastobjects.batch import SpriteBatch


class SpriteGroup:
    """Grupo de sprites contíguos de um batch. Um objeto por grupo, nunca por sprite.

    As propriedades são views do array do batch: operações in-place
    (`group.y += v`) escrevem direto no estado, sem cópia. Funciona para
    qualquer batch cujo `data` tenha as colunas 0-8 no layout
    x, y, w, h, rot, r, g, b, a (SpriteBatch e ShapeBatch).

    Args:
        batch: dono do array `data`.
        s: slice absoluto das linhas deste grupo em `batch.data`.
    """

    def __init__(self, batch: SpriteBatch, s: slice) -> None:
        self._batch = batch
        self._slice = s

    @property
    def slice(self) -> slice:
        """Slice absoluto das linhas deste grupo no array do batch."""
        return self._slice

    def __len__(self) -> int:
        return self._slice.stop - self._slice.start

    def __getitem__(self, sub: slice) -> SpriteGroup:
        if not isinstance(sub, slice):
            raise TypeError(
                "SpriteGroup aceita apenas slices (grupo[a:b]); não há handle "
                "individual — para um sprite use grupo[i:i+1]."
            )
        start, stop, step = sub.indices(len(self))
        if step != 1:
            raise ValueError("SpriteGroup não suporta step em slices (use passo 1).")
        base = self._slice.start
        return SpriteGroup(self._batch, slice(base + start, base + stop))

    # --- colunas escalares -------------------------------------------------

    @property
    def x(self) -> np.ndarray:
        return self._batch.data[self._slice, 0]

    @x.setter
    def x(self, value) -> None:
        self._batch.data[self._slice, 0] = value

    @property
    def y(self) -> np.ndarray:
        return self._batch.data[self._slice, 1]

    @y.setter
    def y(self, value) -> None:
        self._batch.data[self._slice, 1] = value

    @property
    def w(self) -> np.ndarray:
        return self._batch.data[self._slice, 2]

    @w.setter
    def w(self, value) -> None:
        self._batch.data[self._slice, 2] = value

    @property
    def h(self) -> np.ndarray:
        return self._batch.data[self._slice, 3]

    @h.setter
    def h(self, value) -> None:
        self._batch.data[self._slice, 3] = value

    @property
    def rot(self) -> np.ndarray:
        return self._batch.data[self._slice, 4]

    @rot.setter
    def rot(self, value) -> None:
        self._batch.data[self._slice, 4] = value

    # --- blocos ------------------------------------------------------------

    @property
    def pos(self) -> np.ndarray:
        return self._batch.data[self._slice, 0:2]

    @pos.setter
    def pos(self, value) -> None:
        self._batch.data[self._slice, 0:2] = value

    @property
    def size(self) -> np.ndarray:
        return self._batch.data[self._slice, 2:4]

    @size.setter
    def size(self, value) -> None:
        self._batch.data[self._slice, 2:4] = value

    @property
    def color(self) -> np.ndarray:
        return self._batch.data[self._slice, 5:9]

    @color.setter
    def color(self, value) -> None:
        self._batch.data[self._slice, 5:9] = value
```

- [ ] **Step 4: spawn retorna SpriteGroup**

Em `fastobjects/batch.py`, adicionar o import:

```python
from fastobjects.group import SpriteGroup
```

Em `spawn`, mudar a anotação de retorno de `-> slice` para `-> SpriteGroup`, o
trecho do docstring `Returns:` para:

```python
        Returns:
            SpriteGroup das linhas recém-criadas (views escrevem no batch).
```

e a última linha de `return s` para:

```python
        return SpriteGroup(self, s)
```

- [ ] **Step 5: Atualizar asserts em test_batch.py**

Em `tests/test_batch.py`:

- `test_spawn_scalar_fills_rows`: trocar

```python
    assert s == slice(0, 10)
    np.testing.assert_allclose(batch.pos[s][:, 0], 5.0)
    np.testing.assert_allclose(batch.pos[s][:, 1], 7.0)
```

por

```python
    assert s.slice == slice(0, 10)
    np.testing.assert_allclose(s.x, 5.0)
    np.testing.assert_allclose(s.y, 7.0)
```

- `test_spawn_appends_after_existing`: trocar `assert s2 == slice(10, 15)` por `assert s2.slice == slice(10, 15)`.

- [ ] **Step 6: Rodar os testes**

Run: `.venv\Scripts\python -m pytest -v`
Expected: todos passam (33 + 8 novos = 41).

- [ ] **Step 7: Commit**

```powershell
git add fastobjects/group.py fastobjects/batch.py tests/test_group.py tests/test_batch.py
git commit -m "feat!: spawn returns vectorized SpriteGroup view over batch arrays"
```

---

### Task 4: Frame loop (`@win.frame`, `run`, `draw`, `request_close`)

**Files:**
- Modify: `fastobjects/window.py`
- Test: `tests/test_frame_loop.py`

**Interfaces:**
- Consumes: `Window` existente (`poll/swap/should_close`).
- Produces (usado pelo aceite, Task 8):
  - `Window.frame(fn: Callable[[float], None]) -> Callable[[float], None]` — decorator; registra `fn(dt)`; registrar de novo substitui.
  - `Window.run() -> None` — loop `poll → dt (perf_counter) → fn(dt) → swap` até `should_close`; sem função registrada levanta `RuntimeError` acionável.
  - `Window.draw(*batches) -> None` — chama `batch.draw()` de cada um, na ordem.
  - `Window.request_close() -> None` — seta should_close (única forma de sair de `run()` de dentro do update; justificativa: sem isso o loop não tem saída programática).

- [ ] **Step 1: Escrever os testes (falhando)**

`tests/test_frame_loop.py`:

```python
import pytest

from fastobjects import Window


@pytest.fixture
def win():
    w = Window(320, 240, "loop", visible=False)
    yield w
    w.close()


def test_run_calls_update_until_close(win):
    dts = []

    @win.frame
    def update(dt):
        dts.append(dt)
        if len(dts) >= 3:
            win.request_close()

    win.run()
    assert len(dts) == 3
    assert all(dt >= 0.0 for dt in dts)  # perf_counter é monotônico


def test_frame_reregister_replaces(win):
    calls = []

    @win.frame
    def a(dt):
        calls.append("a")
        win.request_close()

    @win.frame
    def b(dt):
        calls.append("b")
        win.request_close()

    win.run()
    assert calls == ["b"]


def test_run_without_frame_raises_actionable(win):
    with pytest.raises(RuntimeError, match="win.frame"):
        win.run()


def test_draw_calls_batches_in_order(win):
    calls = []

    class Fake:
        def __init__(self, tag):
            self.tag = tag

        def draw(self):
            calls.append(self.tag)

    win.draw(Fake("a"), Fake("b"))
    assert calls == ["a", "b"]
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_frame_loop.py -v`
Expected: FAIL com `AttributeError: 'Window' object has no attribute 'frame'`

- [ ] **Step 3: Implementar na Window**

Em `fastobjects/window.py`, adicionar imports:

```python
import time
from typing import Callable
```

No final de `Window.__init__` (antes de `_context.set_current(self)`):

```python
        self._update: Callable[[float], None] | None = None
```

Adicionar os métodos (após `swap`):

```python
    def frame(self, fn: Callable[[float], None]) -> Callable[[float], None]:
        """Decorator: registra fn(dt) como o update chamado por run().

        Registrar uma nova função substitui a anterior.
        """
        self._update = fn
        return fn

    def draw(self, *batches) -> None:
        """Desenha cada batch na ordem dada (açúcar para batch.draw())."""
        for batch in batches:
            batch.draw()

    def request_close(self) -> None:
        """Pede o fim do loop: should_close passa a True e run() retorna."""
        glfw.set_window_should_close(self._win, True)

    def run(self) -> None:
        """Executa o loop de frames até a janela fechar.

        Por frame: poll de eventos, dt real (perf_counter), update(dt), swap.

        Raises:
            RuntimeError: se nenhuma função foi registrada com @win.frame.
        """
        if self._update is None:
            raise RuntimeError(
                "Nenhuma função de frame registrada — decore seu update com "
                "@win.frame antes de chamar win.run()."
            )
        last = time.perf_counter()
        while not self.should_close:
            self.poll()
            now = time.perf_counter()
            dt = now - last
            last = now
            self._update(dt)
            self.swap()
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv\Scripts\python -m pytest -v`
Expected: todos passam (41 + 4 = 45).

- [ ] **Step 5: Commit**

```powershell
git add fastobjects/window.py tests/test_frame_loop.py
git commit -m "feat: frame loop with @win.frame decorator, run() and draw()"
```

---

### Task 5: Input por polling (`input.py`) + re-export de constantes

**Files:**
- Create: `fastobjects/input.py`
- Modify: `fastobjects/window.py` (instanciar e ligar callbacks)
- Modify: `fastobjects/__init__.py` (exports + `KEY_*`/`MOUSE_BUTTON_*`)
- Test: `tests/test_input.py`

**Interfaces:**
- Consumes: constantes/callbacks do glfw; `Window._win` (handle interno).
- Produces (usado pelo aceite):
  - `class Keyboard` — `keys[keycode] -> bool`; método interno `_on_key(window, key, scancode, action, mods)`.
  - `class Mouse` — `.x: float`, `.y: float` (pixels, y para baixo), `.left/.right/.middle: bool`; internos `_on_move(window, x, y)`, `_on_button(window, button, action, mods)`.
  - `Window.keys: Keyboard`, `Window.mouse: Mouse` — ligados via `glfw.set_key_callback`/`set_cursor_pos_callback`/`set_mouse_button_callback`.
  - `fastobjects.KEY_*` e `fastobjects.MOUSE_BUTTON_*` — re-export das constantes glfw.
  - `fastobjects.__init__` também passa a exportar `SpriteGroup` e (no Task 7) `ShapeBatch`.

- [ ] **Step 1: Escrever os testes (falhando)**

`tests/test_input.py`:

```python
import glfw

import fastobjects as fo
from fastobjects import Window
from fastobjects.input import Keyboard, Mouse


def test_key_press_release_cycle():
    kb = Keyboard()
    assert not kb[glfw.KEY_SPACE]
    kb._on_key(None, glfw.KEY_SPACE, 0, glfw.PRESS, 0)
    assert kb[glfw.KEY_SPACE]
    kb._on_key(None, glfw.KEY_SPACE, 0, glfw.RELEASE, 0)
    assert not kb[glfw.KEY_SPACE]


def test_key_repeat_keeps_pressed():
    kb = Keyboard()
    kb._on_key(None, glfw.KEY_A, 0, glfw.PRESS, 0)
    kb._on_key(None, glfw.KEY_A, 0, glfw.REPEAT, 0)
    assert kb[glfw.KEY_A]


def test_unknown_key_is_ignored():
    kb = Keyboard()
    kb._on_key(None, glfw.KEY_UNKNOWN, 0, glfw.PRESS, 0)  # -1: não pode explodir
    assert not kb[glfw.KEY_SPACE]


def test_mouse_move_and_buttons():
    m = Mouse()
    m._on_move(None, 100.5, 200.25)
    assert m.x == 100.5
    assert m.y == 200.25
    m._on_button(None, glfw.MOUSE_BUTTON_LEFT, glfw.PRESS, 0)
    assert m.left and not m.right and not m.middle
    m._on_button(None, glfw.MOUSE_BUTTON_RIGHT, glfw.PRESS, 0)
    m._on_button(None, glfw.MOUSE_BUTTON_MIDDLE, glfw.PRESS, 0)
    assert m.left and m.right and m.middle
    m._on_button(None, glfw.MOUSE_BUTTON_LEFT, glfw.RELEASE, 0)
    assert not m.left and m.right


def test_constants_reexported():
    assert fo.KEY_SPACE == glfw.KEY_SPACE
    assert fo.KEY_ESCAPE == glfw.KEY_ESCAPE
    assert fo.MOUSE_BUTTON_LEFT == glfw.MOUSE_BUTTON_LEFT


def test_window_wires_input():
    win = Window(320, 240, "input", visible=False)
    assert not win.keys[fo.KEY_SPACE]
    assert win.mouse.x == 0.0
    assert not win.mouse.left
    win.close()
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_input.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'fastobjects.input'`

- [ ] **Step 3: Implementar `fastobjects/input.py`**

```python
"""Estado de input por polling (teclado/mouse), alimentado por callbacks glfw."""

from __future__ import annotations

import glfw
import numpy as np


class Keyboard:
    """Estado do teclado: keys[fo.KEY_SPACE] -> bool (True enquanto pressionada)."""

    def __init__(self) -> None:
        self._state = np.zeros(glfw.KEY_LAST + 1, dtype=bool)

    def __getitem__(self, key: int) -> bool:
        return bool(self._state[key])

    def _on_key(self, window, key: int, scancode: int, action: int, mods: int) -> None:
        if key < 0:  # glfw.KEY_UNKNOWN
            return
        if action == glfw.PRESS:
            self._state[key] = True
        elif action == glfw.RELEASE:
            self._state[key] = False
        # glfw.REPEAT não muda o estado: a tecla já está pressionada.


class Mouse:
    """Posição do cursor (pixels, y para baixo — igual ao renderer) e botões."""

    def __init__(self) -> None:
        self.x = 0.0
        self.y = 0.0
        self.left = False
        self.right = False
        self.middle = False

    def _on_move(self, window, x: float, y: float) -> None:
        self.x = x
        self.y = y

    def _on_button(self, window, button: int, action: int, mods: int) -> None:
        pressed = action == glfw.PRESS
        if button == glfw.MOUSE_BUTTON_LEFT:
            self.left = pressed
        elif button == glfw.MOUSE_BUTTON_RIGHT:
            self.right = pressed
        elif button == glfw.MOUSE_BUTTON_MIDDLE:
            self.middle = pressed
```

- [ ] **Step 4: Ligar na Window**

Em `fastobjects/window.py`, adicionar o import:

```python
from fastobjects.input import Keyboard, Mouse
```

No final de `Window.__init__` (antes de `_context.set_current(self)`):

```python
        self.keys = Keyboard()
        self.mouse = Mouse()
        glfw.set_key_callback(self._win, self.keys._on_key)
        glfw.set_cursor_pos_callback(self._win, self.mouse._on_move)
        glfw.set_mouse_button_callback(self._win, self.mouse._on_button)
```

- [ ] **Step 5: Re-exportar constantes no `__init__.py`**

Substituir `fastobjects/__init__.py` inteiro por:

```python
"""FastObjects: the fastest 2D object rendering library for Python."""

import glfw as _glfw

from fastobjects.batch import SpriteBatch
from fastobjects.errors import CapacityError
from fastobjects.group import SpriteGroup
from fastobjects.window import Window

__version__ = "0.1.0"
__all__ = ["CapacityError", "SpriteBatch", "SpriteGroup", "Window", "__version__"]

# Constantes de input (fo.KEY_SPACE, fo.MOUSE_BUTTON_LEFT, ...): re-export
# direto do glfw — zero manutenção própria.
for _name in dir(_glfw):
    if _name.startswith(("KEY_", "MOUSE_BUTTON_")):
        globals()[_name] = getattr(_glfw, _name)
        __all__.append(_name)
del _glfw, _name
```

- [ ] **Step 6: Rodar os testes**

Run: `.venv\Scripts\python -m pytest -v`
Expected: todos passam (45 + 6 = 51).

- [ ] **Step 7: Commit**

```powershell
git add fastobjects/input.py fastobjects/window.py fastobjects/__init__.py tests/test_input.py
git commit -m "feat: polling keyboard/mouse input with re-exported glfw constants"
```

---

### Task 6: Shaders de formas + `_ShapeRenderer` (pixel-verificado)

**Files:**
- Modify: `fastobjects/core/shaders.py` (adicionar `SHAPE_VS`, `SHAPE_FS`)
- Create: `fastobjects/shapes.py` (por enquanto só `_ShapeRenderer`; `ShapeBatch` chega no Task 7)
- Test: `tests/test_shapes.py`

**Interfaces:**
- Consumes: técnica `gl_VertexID` + `u_view` de `SPRITE_VS` (mesma convenção y-para-baixo).
- Produces (usado pelo Task 7):
  - `SHAPE_VS: str`, `SHAPE_FS: str` em `core/shaders.py`
  - `SHAPE_FLOATS = 10` (layout `x, y, w, h, rot, r, g, b, a, kind`), `SHAPE_STRIDE = 40`
  - `KIND_RECT = 0.0`, `KIND_CIRCLE = 1.0`
  - `class _ShapeRenderer(ctx, capacity: int, view_size: tuple[int, int])` com `.render(data: np.ndarray, count: int) -> None` (`data` é `(capacity, 10) f4`)

- [ ] **Step 1: Escrever os testes de pixel (falhando)**

`tests/test_shapes.py`:

```python
import moderngl
import numpy as np
import pytest

from fastobjects.shapes import KIND_CIRCLE, KIND_RECT, _ShapeRenderer


@pytest.fixture(scope="module")
def gl():
    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.BLEND)
    fbo = ctx.framebuffer(color_attachments=[ctx.texture((64, 64), 4)])
    fbo.use()
    yield ctx, fbo
    ctx.release()


def read_pixels(fbo) -> np.ndarray:
    """(64, 64, 4) uint8, indexado [linha_do_topo, coluna]."""
    raw = np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(64, 64, 4)
    return raw[::-1]


def shape_row(x, y, w, h, rot, color, kind) -> np.ndarray:
    row = np.zeros((1, 10), dtype="f4")
    row[0] = [x, y, w, h, rot, *color, kind]
    return row


def test_rect_fills_pixels(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    r = _ShapeRenderer(ctx, capacity=16, view_size=(64, 64))
    r.render(shape_row(32, 32, 20, 20, 0.0, (1.0, 0.0, 0.0, 1.0), KIND_RECT), 1)
    px = read_pixels(fbo)
    assert px[32, 32][0] > 200  # centro vermelho
    assert px[32, 24][0] > 200  # dentro da borda esquerda (22 < 24)
    assert px[2, 2][0] < 10  # fundo intacto


def test_circle_sdf_cuts_corners(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    r = _ShapeRenderer(ctx, capacity=16, view_size=(64, 64))
    # bounding box 24x24 -> raio 12, centrado em (32, 32)
    r.render(shape_row(32, 32, 24, 24, 0.0, (0.0, 1.0, 0.0, 1.0), KIND_CIRCLE), 1)
    px = read_pixels(fbo)
    assert px[32, 32][1] > 200  # centro verde
    assert px[22, 32][1] > 200  # 10px acima do centro: dentro do raio 12
    assert px[21, 21][1] < 30  # canto do bounding box: dist ~15.6 > 12, fora


def test_render_zero_count_is_noop(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    r = _ShapeRenderer(ctx, capacity=4, view_size=(64, 64))
    r.render(np.zeros((4, 10), dtype="f4"), 0)
    px = read_pixels(fbo)
    assert px[:, :, :3].max() < 10
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_shapes.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'fastobjects.shapes'`

- [ ] **Step 3: Adicionar os shaders em `fastobjects/core/shaders.py`**

Anexar ao final do arquivo:

```python
SHAPE_VS = """
#version 330
uniform vec2 u_view;  // (2/width, -2/height): pixels -> NDC com y para baixo

in vec2 in_pos;    // centro da forma, em pixels (por instância)
in vec2 in_size;   // bounding box em pixels (por instância)
in float in_rot;   // radianos (por instância)
in vec4 in_color;  // RGBA (por instância)
in float in_kind;  // 0 = retângulo, 1 = círculo (por instância)

out vec4 v_color;
out vec2 v_uv;
flat out float v_kind;

const vec2 CORNERS[4] = vec2[4](
    vec2(-0.5, -0.5), vec2(0.5, -0.5), vec2(-0.5, 0.5), vec2(0.5, 0.5)
);

void main() {
    vec2 corner = CORNERS[gl_VertexID] * in_size;
    float c = cos(in_rot);
    float s = sin(in_rot);
    vec2 world = in_pos + vec2(corner.x * c - corner.y * s,
                               corner.x * s + corner.y * c);
    gl_Position = vec4(world * u_view + vec2(-1.0, 1.0), 0.0, 1.0);
    v_uv = CORNERS[gl_VertexID] + 0.5;
    v_color = in_color;
    v_kind = in_kind;
}
"""

SHAPE_FS = """
#version 330
in vec4 v_color;
in vec2 v_uv;
flat in float v_kind;
out vec4 f_color;

void main() {
    float alpha = 1.0;
    if (v_kind > 0.5) {  // círculo: SDF de elipse normalizada no espaço UV
        float d = length(v_uv * 2.0 - 1.0) - 1.0;
        float aa = fwidth(d);  // banda de anti-alias de ~1px
        alpha = 1.0 - smoothstep(0.0, aa, d);
        if (alpha <= 0.0) {
            discard;
        }
    }
    f_color = vec4(v_color.rgb, v_color.a * alpha);
}
"""
```

- [ ] **Step 4: Implementar `fastobjects/shapes.py` (renderer)**

```python
"""ShapeBatch: primitivas 2D instanciadas — forma resolvida no fragment shader."""

from __future__ import annotations

import moderngl
import numpy as np

from fastobjects.core.shaders import SHAPE_FS, SHAPE_VS

SHAPE_FLOATS = 10  # x, y, w, h, rot, r, g, b, a, kind
SHAPE_STRIDE = SHAPE_FLOATS * 4
KIND_RECT = 0.0
KIND_CIRCLE = 1.0


class _ShapeRenderer:
    """Desenha até `capacity` formas com um único draw call instanciado.

    Args:
        ctx: contexto moderngl ativo.
        capacity: número máximo de instâncias.
        view_size: (largura, altura) do alvo de render, em pixels.
    """

    def __init__(
        self,
        ctx: moderngl.Context,
        capacity: int,
        view_size: tuple[int, int],
    ) -> None:
        self.ctx = ctx
        self.capacity = capacity
        self.prog = ctx.program(vertex_shader=SHAPE_VS, fragment_shader=SHAPE_FS)
        self.prog["u_view"].value = (2.0 / view_size[0], -2.0 / view_size[1])
        self.buffer = ctx.buffer(reserve=capacity * SHAPE_STRIDE)
        self.vao = ctx.vertex_array(
            self.prog,
            [
                (
                    self.buffer,
                    "2f 2f 1f 4f 1f/i",
                    "in_pos",
                    "in_size",
                    "in_rot",
                    "in_color",
                    "in_kind",
                )
            ],
        )

    def render(self, data: np.ndarray, count: int) -> None:
        """Sobe `data[:count]` e desenha `count` instâncias (estratégia A do lab)."""
        if count == 0:
            return
        self.buffer.write(data[:count])
        self.vao.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=count)
```

- [ ] **Step 5: Rodar os testes**

Run: `.venv\Scripts\python -m pytest -v`
Expected: todos passam (51 + 3 = 54).

- [ ] **Step 6: Commit**

```powershell
git add fastobjects/core/shaders.py fastobjects/shapes.py tests/test_shapes.py
git commit -m "feat: instanced shape renderer with SDF circle, pixel-verified"
```

---

### Task 7: ShapeBatch (rects/circles/lines) + export

**Files:**
- Modify: `fastobjects/shapes.py` (adicionar `ShapeBatch`)
- Modify: `fastobjects/__init__.py` (exportar `ShapeBatch`)
- Test: `tests/test_shapes.py` (adicionar testes de API)

**Interfaces:**
- Consumes: `_ShapeRenderer` (Task 6), `SpriteGroup` (Task 3), `_context.resolve` (Task 1), `CapacityError`.
- Produces (usado pelo aceite):
  - `ShapeBatch(capacity: int, *, ctx=None, view_size=None)`
  - `.rects(n, x=0.0, y=0.0, w=10.0, h=10.0, rot=0.0, color=(1,1,1,1)) -> SpriteGroup`
  - `.circles(n, x=0.0, y=0.0, radius=5.0, color=(1,1,1,1)) -> SpriteGroup` — armazena `w = h = 2*radius`
  - `.lines(n, x1, y1, x2, y2, width=1.0, color=(1,1,1,1)) -> SpriteGroup` — converte vetorizado para retângulo (centro/comprimento/rotação); o shader não tem kind "linha"
  - `.count: int`, `.data: (capacity, 10) f4`, `.clear()`, `.draw()`
  - Todos os parâmetros aceitam escalares ou arrays de tamanho n; guards de `capacity`/`n` com as mesmas mensagens acionáveis do SpriteBatch.
  - Exportado como `fastobjects.ShapeBatch`.

- [ ] **Step 1: Escrever os testes de API (falhando)**

Adicionar ao final de `tests/test_shapes.py`:

```python
def test_rects_fill_rows_and_return_group(gl):
    from fastobjects.group import SpriteGroup
    from fastobjects.shapes import ShapeBatch

    ctx, _ = gl
    batch = ShapeBatch(capacity=100, ctx=ctx, view_size=(64, 64))
    g = batch.rects(5, x=10.0, y=20.0, w=4.0, h=6.0)
    assert isinstance(g, SpriteGroup)
    assert batch.count == 5
    np.testing.assert_allclose(g.x, 10.0)
    np.testing.assert_allclose(batch.data[:5, 9], KIND_RECT)


def test_circles_store_diameter(gl):
    from fastobjects.shapes import ShapeBatch

    ctx, _ = gl
    batch = ShapeBatch(capacity=10, ctx=ctx, view_size=(64, 64))
    g = batch.circles(3, x=1.0, y=2.0, radius=5.0)
    np.testing.assert_allclose(g.size, [[10.0, 10.0]] * 3)  # 2 * radius
    np.testing.assert_allclose(batch.data[:3, 9], KIND_CIRCLE)


def test_lines_convert_to_rotated_rects(gl):
    from fastobjects.shapes import ShapeBatch

    ctx, _ = gl
    batch = ShapeBatch(capacity=10, ctx=ctx, view_size=(64, 64))
    g = batch.lines(1, x1=0.0, y1=0.0, x2=30.0, y2=40.0, width=2.0)
    np.testing.assert_allclose(g.x, 15.0)
    np.testing.assert_allclose(g.y, 20.0)
    np.testing.assert_allclose(g.w, 50.0)  # hypot(30, 40)
    np.testing.assert_allclose(g.h, 2.0)
    np.testing.assert_allclose(g.rot, np.arctan2(40.0, 30.0))
    assert batch.data[0, 9] == KIND_RECT  # linha é retângulo para o shader


def test_line_paints_along_segment(gl):
    from fastobjects.shapes import ShapeBatch

    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    batch = ShapeBatch(capacity=10, ctx=ctx, view_size=(64, 64))
    batch.lines(1, x1=12.0, y1=48.0, x2=52.0, y2=48.0, width=3.0,
                color=(0.0, 0.0, 1.0, 1.0))
    batch.draw()
    px = read_pixels(fbo)
    assert px[48, 32][2] > 200  # meio do segmento azul
    assert px[48, 6][2] < 10  # antes do início (x=6 < 12)
    assert px[20, 32][2] < 10  # longe da linha


def test_mixed_shapes_one_draw_call(gl):
    from fastobjects.shapes import ShapeBatch

    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    batch = ShapeBatch(capacity=10, ctx=ctx, view_size=(64, 64))
    batch.rects(1, x=16.0, y=16.0, w=10.0, h=10.0, color=(1.0, 0.0, 0.0, 1.0))
    batch.circles(1, x=48.0, y=48.0, radius=8.0, color=(0.0, 1.0, 0.0, 1.0))
    batch.draw()
    px = read_pixels(fbo)
    assert px[16, 16][0] > 200  # retângulo vermelho
    assert px[48, 48][1] > 200  # círculo verde


def test_shape_capacity_and_negative_guards(gl):
    from fastobjects.errors import CapacityError
    from fastobjects.shapes import ShapeBatch

    ctx, _ = gl
    with pytest.raises(ValueError, match="capacity=0"):
        ShapeBatch(capacity=0, ctx=ctx, view_size=(64, 64))
    batch = ShapeBatch(capacity=10, ctx=ctx, view_size=(64, 64))
    batch.rects(8)
    with pytest.raises(CapacityError, match="capacity=13"):
        batch.rects(5)
    with pytest.raises(ValueError, match="negativo"):
        batch.circles(-1)


def test_shape_clear_resets(gl):
    from fastobjects.shapes import ShapeBatch

    ctx, _ = gl
    batch = ShapeBatch(capacity=5, ctx=ctx, view_size=(64, 64))
    batch.rects(5)
    batch.clear()
    assert batch.count == 0
    batch.circles(5)  # não deve levantar


def test_shapebatch_exported():
    import fastobjects as fo

    assert fo.ShapeBatch is not None
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_shapes.py -v`
Expected: FAIL com `ImportError: cannot import name 'ShapeBatch'`

- [ ] **Step 3: Implementar ShapeBatch**

Em `fastobjects/shapes.py`, adicionar imports:

```python
from fastobjects import _context
from fastobjects.errors import CapacityError
from fastobjects.group import SpriteGroup
```

Adicionar ao final do arquivo:

```python
class ShapeBatch:
    """Lote de primitivas 2D (retângulo, círculo, linha) em um draw call.

    O estado vive em `data` (capacity, 10): x, y, w, h, rot, r, g, b, a, kind.
    Formas diferentes convivem no mesmo lote; os métodos retornam SpriteGroup
    com views que escrevem direto no array.

    Args:
        capacity: número máximo de formas do lote.
        ctx: contexto moderngl; se None, usa o da janela atual.
        view_size: (largura, altura) do alvo de render em pixels;
            se None, usa o tamanho da janela atual.
    """

    def __init__(
        self,
        capacity: int,
        *,
        ctx: moderngl.Context | None = None,
        view_size: tuple[int, int] | None = None,
    ) -> None:
        if capacity <= 0:
            raise ValueError(
                f"capacity={capacity} inválida: use um valor > 0 "
                "(quantidade máxima de formas do lote)."
            )
        ctx, view_size = _context.resolve(ctx, view_size)
        self.capacity = capacity
        self.count = 0
        self.data = np.zeros((capacity, SHAPE_FLOATS), dtype="f4")
        self._renderer = _ShapeRenderer(ctx, capacity, view_size)

    def _alloc(self, n: int, method: str) -> slice:
        """Reserva n linhas contíguas; guards idênticos aos do SpriteBatch."""
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

    def rects(
        self,
        n: int,
        x: float | np.ndarray = 0.0,
        y: float | np.ndarray = 0.0,
        w: float | np.ndarray = 10.0,
        h: float | np.ndarray = 10.0,
        rot: float | np.ndarray = 0.0,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    ) -> SpriteGroup:
        """Adiciona n retângulos. Aceita escalares ou arrays de tamanho n."""
        s = self._alloc(n, "rects")
        d = self.data
        d[s, 0] = x
        d[s, 1] = y
        d[s, 2] = w
        d[s, 3] = h
        d[s, 4] = rot
        d[s, 5:9] = color
        d[s, 9] = KIND_RECT
        return SpriteGroup(self, s)

    def circles(
        self,
        n: int,
        x: float | np.ndarray = 0.0,
        y: float | np.ndarray = 0.0,
        radius: float | np.ndarray = 5.0,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    ) -> SpriteGroup:
        """Adiciona n círculos; o layout guarda o bounding box (w = h = 2*radius)."""
        s = self._alloc(n, "circles")
        d = self.data
        diameter = np.multiply(radius, 2.0, dtype="f4")
        d[s, 0] = x
        d[s, 1] = y
        d[s, 2] = diameter
        d[s, 3] = diameter
        d[s, 4] = 0.0
        d[s, 5:9] = color
        d[s, 9] = KIND_CIRCLE
        return SpriteGroup(self, s)

    def lines(
        self,
        n: int,
        x1: float | np.ndarray,
        y1: float | np.ndarray,
        x2: float | np.ndarray,
        y2: float | np.ndarray,
        width: float | np.ndarray = 1.0,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    ) -> SpriteGroup:
        """Adiciona n linhas como retângulos rotacionados (conversão vetorizada).

        O shader não conhece "linha": endpoints viram centro, comprimento e
        rotação de um retângulo com altura `width`.
        """
        s = self._alloc(n, "lines")
        x1 = np.asarray(x1, dtype="f4")
        y1 = np.asarray(y1, dtype="f4")
        x2 = np.asarray(x2, dtype="f4")
        y2 = np.asarray(y2, dtype="f4")
        dx = x2 - x1
        dy = y2 - y1
        d = self.data
        d[s, 0] = (x1 + x2) * 0.5
        d[s, 1] = (y1 + y2) * 0.5
        d[s, 2] = np.hypot(dx, dy)
        d[s, 3] = width
        d[s, 4] = np.arctan2(dy, dx)
        d[s, 5:9] = color
        d[s, 9] = KIND_RECT
        return SpriteGroup(self, s)

    def clear(self) -> None:
        """Remove todas as formas (O(1): só reseta o contador)."""
        self.count = 0

    def draw(self) -> None:
        """Sobe o estado atual e desenha o lote inteiro em um draw call."""
        self._renderer.render(self.data, self.count)
```

- [ ] **Step 4: Exportar no `__init__.py`**

Em `fastobjects/__init__.py`, adicionar o import (em ordem alfabética, após `group`):

```python
from fastobjects.shapes import ShapeBatch
```

e atualizar `__all__` para:

```python
__all__ = ["CapacityError", "ShapeBatch", "SpriteBatch", "SpriteGroup", "Window", "__version__"]
```

- [ ] **Step 5: Rodar os testes**

Run: `.venv\Scripts\python -m pytest -v`
Expected: todos passam (54 + 8 = 62).

- [ ] **Step 6: Commit**

```powershell
git add fastobjects/shapes.py fastobjects/__init__.py tests/test_shapes.py
git commit -m "feat: ShapeBatch with rects, SDF circles and vectorized lines"
```

---

### Task 8: Aceite do exemplo do spec + lint + arena sem regressão

**Files:**
- Modify: `benchmarks/RESULTS.md` (nova seção da arena, via `run_all.py --save`)
- (script de aceite roda de um diretório temporário e NÃO é commitado)

**Interfaces:**
- Consumes: toda a API pública da fase (`Window`, `SpriteBatch`, `ShapeBatch`, `SpriteGroup`, frame loop, input implícito de janela).
- Produces: evidência do critério de aceite do spec (exemplo roda copiado-e-colado) e arena re-executada registrada em `RESULTS.md`.

- [ ] **Step 1: Rodar o script de aceite (exemplo do spec, janela visível)**

Salvar FORA do repositório (ex.: diretório temporário) como `aceite_fase4.py` e executar da raiz do projeto:

```python
"""Aceite da Fase 4: o exemplo do spec, executável copiado-e-colado."""

import numpy as np

import fastobjects as fo

rng = np.random.default_rng(42)
N = 5_000
xs = rng.uniform(0, 1280, N).astype(np.float32)
ys = rng.uniform(0, 360, N).astype(np.float32)
velocity = rng.uniform(20.0, 80.0, N).astype(np.float32)

win = fo.Window(1280, 720, "demo")
batch = fo.SpriteBatch("benchmarks/arena/assets/bunny.png", capacity=200_000)
bunnies = batch.spawn(N, x=xs, y=ys)

shapes = fo.ShapeBatch(capacity=100)
shapes.rects(1, x=640.0, y=20.0, w=1200.0, h=8.0, color=(0.3, 0.3, 0.9, 1.0))
shapes.circles(3, x=np.array([100.0, 640.0, 1180.0], dtype=np.float32),
               y=60.0, radius=15.0, color=(1.0, 0.5, 0.0, 1.0))
shapes.lines(1, x1=0.0, y1=700.0, x2=1280.0, y2=700.0, width=2.0,
             color=(0.0, 1.0, 0.0, 1.0))

frames = [0]


@win.frame
def update(dt):
    bunnies.y += velocity * dt
    win.clear(0.1, 0.1, 0.1)
    win.draw(batch, shapes)
    frames[0] += 1
    if frames[0] >= 300 or win.keys[fo.KEY_ESCAPE]:
        win.request_close()


win.run()
win.close()
print(f"aceite ok: {frames[0]} frames")
```

Run (da raiz do repo): `.venv\Scripts\python <caminho>\aceite_fase4.py`
Expected: janela abre ~5s com coelhos caindo, barra/círculos/linha desenhados, e imprime `aceite ok: 300 frames` (ou menos, se ESC for pressionado). Qualquer exceção = aceite falhou; investigar antes de prosseguir.

- [ ] **Step 2: Lint**

Run: `.venv\Scripts\python -m ruff check fastobjects tests`
Expected: sem erros (corrigir o que aparecer; `ruff format` não faz parte do gate).

- [ ] **Step 3: Rodar a arena completa e salvar**

Run: `.venv\Scripts\python benchmarks/arena/run_all.py --save` (timeout generoso: os 5 benches levam minutos e abrem janelas)
Expected: tabela com 5 frameworks, fastobjects em 1º com a mesma ordem de grandeza do baseline (~219k sprites; variação de um passo de ramp é normal — ver RESULTS.md). Regressão real (fastobjects fora do 1º lugar ou queda de ordem de grandeza) = parar e investigar com systematic-debugging antes de commitar.

- [ ] **Step 4: Rodar a suíte completa**

Run: `.venv\Scripts\python -m pytest -v`
Expected: 62 testes passando.

- [ ] **Step 5: Commit**

```powershell
git add benchmarks/RESULTS.md
git commit -m "bench: arena re-run after phase 4 API layer - no regression"
```

---

### Task 9: Release pré-1.0 no GitHub (PÓS-MERGE, executa em `main`)

**Files:**
- Nenhum arquivo novo — tag + release no GitHub.

**Interfaces:**
- Consumes: branch da fase já merged em `main` (via superpowers:finishing-a-development-branch), suíte verde em `main`.
- Produces: tag `v0.1.0` e GitHub Release marcada como **pre-release**.

**ATENÇÃO:** este task só roda DEPOIS do merge em `main`. E o push da tag dispara `.github/workflows/publish.yml` (gatilho `tags: v*`), que tenta publicar no PyPI via trusted publishing (environment `pypi`). Se o environment/trusted publisher não estiver configurado no PyPI, o job `publish` falha sem efeitos colaterais (o build continua ok). Reportar o resultado do workflow ao usuário em qualquer caso.

- [ ] **Step 1: Confirmar estado de main**

```powershell
git checkout main; git pull; git log --oneline -3
.venv\Scripts\python -m pytest
```

Expected: merge da fase presente, 62 testes passando.

- [ ] **Step 2: Criar e enviar a tag**

```powershell
git tag -a v0.1.0 -m "FastObjects 0.1.0 - core instanciado + API publica (pre-1.0)"
git push origin v0.1.0
```

- [ ] **Step 3: Criar a release (pre-release)**

Escrever as notas em um arquivo temporário `notes.md` (fora do repo):

```markdown
# FastObjects v0.1.0 (pré-1.0)

Primeira release pública — **API pré-1.0, sujeita a mudanças**.

## Destaques

- **218.809 sprites @ 60fps** no bunnymark — ~38x o melhor concorrente
  (raylib/arcade) no mesmo hardware. Números completos em `benchmarks/RESULTS.md`.
- Sprites como linhas de arrays NumPy: zero objetos Python por sprite,
  1 upload de buffer + 1 draw call instanciado por batch.
- API ergonômica: `@win.frame`, `win.run()`, `SpriteGroup` vetorizado,
  `ShapeBatch` (retângulo/círculo/linha), input por polling.

## Exemplo

    import fastobjects as fo

    win = fo.Window(1280, 720, "demo")
    batch = fo.SpriteBatch("bunny.png", capacity=200_000)
    bunnies = batch.spawn(100_000, x=xs, y=ys)

    @win.frame
    def update(dt):
        bunnies.y += velocity * dt
        win.clear(0.1, 0.1, 0.1)
        win.draw(batch)

    win.run()

Requisitos: Python >= 3.11, OpenGL 3.3 core.
```

```powershell
gh release create v0.1.0 --verify-tag --prerelease --title "FastObjects v0.1.0 (pré-1.0)" --notes-file <caminho>\notes.md
```

Expected: URL da release impressa; release marcada como "Pre-release" no GitHub.

- [ ] **Step 4: Verificar o workflow disparado**

```powershell
gh run list --workflow publish.yml --limit 1
```

Expected: run do publish.yml associado à tag. Reportar ao usuário se `publish` teve sucesso (pacote no PyPI) ou falhou por environment não configurado (esperado se o PyPI trusted publisher ainda não existe — não é erro da fase).

---

## Fora deste plano (Fase 5)

- mkdocs-material, `examples/` versionados, README com tabela da arena no topo, publicação PyPI garantida (configuração de trusted publisher), renderização de texto, callbacks de input, polígonos.
