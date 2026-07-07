# FastObjects SoA + Dirty Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Esta fase executa INLINE (executing-plans), a pedido do usuário.**

**Goal:** Fechar o gap de upload para ≥80% do teto do moderngl cru em 100k objetos (hoje 41%) via layout SoA com um VBO por atributo, quantização das colunas frias no upload e dirty tracking conservador por coluna.

**Architecture:** `BatchCore` troca o array `data (cap, N)` por colunas separadas (`pos/size/rot/color[/kind]`, todas f4 na CPU) num dict `_cols` + flags `_dirty`; grupos e propriedades de batch marcam a coluna suja ao acessar; os renderers ganham um VBO por atributo e sobem `pos` sempre + frias sujas (quantizando no upload). Lab decide A/B/C antes de tocar o renderer. Spec: `docs/superpowers/specs/2026-07-07-fastobjects-soa-upload-design.md`.

**Tech Stack:** Python 3.13, moderngl (formatos de atributo `f1`=u8 normalizado, `f2`=half float), numpy, pytest.

## Global Constraints

- Dependências do core: **apenas** numpy, moderngl, glfw, pillow.
- API pública dos grupos INALTERADA (x/y/w/h/rot/pos/size/color, dtype f4 nas views); `batch.data` é REMOVIDO (pré-1.0) — todo consumidor no repo é adaptado no mesmo task; suíte verde em todo commit.
- Mensagens de erro atuais preservadas byte a byte.
- Pixel tests existentes passam SEM afrouxar asserts.
- Benchmarks GL nesta máquina rodam em FOREGROUND (lição do RESULTS.md).
- Toda medição vai para `benchmarks/RESULTS.md` com data/hardware; decisão A/B/C só por benchmark (5 execuções — lição do lab da Fase 1–3).
- Commits **sem** trailer `Co-Authored-By`. Baseline: 87 testes.
- Branch: `soa-upload` a partir de `main`.

---

### Task 1: Lab — exp_soa_layout.py (decide A/B/C e orphan-vs-write)

**Files:**
- Create: `benchmarks/lab/exp_soa_layout.py`
- Modify: `benchmarks/RESULTS.md` (seção com a decisão)

**Interfaces:**
- Consumes: nada do pacote (standalone, como exp_buffer_upload.py).
- Produces: decisão de layout (esperado: C — SoA quantizado) que fixa os formatos de VBO dos Tasks 2–3.

- [ ] **Step 1: Escrever o experimento**

```python
"""Lab: quanto custa o upload por layout? AoS total vs SoA vs SoA quantizado.

Cenário 1 (frame típico): só posições mudam por frame.
Cenário 2 (pior caso): todas as colunas mudam todo frame.
Estratégias:
  A) AoS atual: 1 buffer interleaved de 36 B/inst, write total por frame.
  B) SoA f4: pos (8 B) write por frame; frias só quando mudam.
  C) SoA quantizado: pos f4; frias em u8-norm/f16 (cor 4 B, size 4 B, rot 2 B).
  B-orphan) B com orphan() no buffer de pos antes do write.

Contexto standalone + FBO; ctx.finish() por frame; N=100k; 300 frames; 5 runs.
"""

from __future__ import annotations

import time

import moderngl
import numpy as np

N = 100_000
FRAMES = 300
RUNS = 5
SIZE = (800, 600)

VS = """
#version 330
uniform vec2 u_view;
in vec2 in_pos;
in vec2 in_size;
in float in_rot;
in vec4 in_color;
out vec4 v_color;
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
    v_color = in_color;
}
"""
FS = """
#version 330
in vec4 v_color;
out vec4 f_color;
void main() { f_color = v_color; }
"""


def make_ctx():
    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.BLEND)
    fbo = ctx.framebuffer(color_attachments=[ctx.texture(SIZE, 4)])
    fbo.use()
    return ctx


def make_data(rng):
    pos = np.empty((N, 2), dtype="f4")
    pos[:, 0] = rng.uniform(0, SIZE[0], N)
    pos[:, 1] = rng.uniform(0, SIZE[1], N)
    size = np.full((N, 2), 6.0, dtype="f4")
    rot = np.zeros(N, dtype="f4")
    color = rng.uniform(0.2, 1.0, (N, 4)).astype("f4")
    color[:, 3] = 1.0
    return pos, size, rot, color


def measure(name, frame_fn, ctx):
    best = []
    for _ in range(RUNS):
        t0 = time.perf_counter_ns()
        for _ in range(FRAMES):
            frame_fn()
            ctx.finish()
        best.append((time.perf_counter_ns() - t0) / 1e6 / FRAMES)
    ms = min(best)  # melhor de 5: isola o custo intrínseco do ruído do SO
    print(f"{name}: {ms:.3f} ms/frame (runs: {[f'{b:.3f}' for b in best]})")
    return ms


def main() -> None:
    ctx = make_ctx()
    rng = np.random.default_rng(42)
    pos, size, rot, color = make_data(rng)
    prog = ctx.program(vertex_shader=VS, fragment_shader=FS)
    prog["u_view"].value = (2.0 / SIZE[0], -2.0 / SIZE[1])

    # --- A: AoS interleaved (layout atual do ShapeBatch sem kind) ---
    aos = np.zeros((N, 9), dtype="f4")
    aos[:, 0:2] = pos
    aos[:, 2:4] = size
    aos[:, 4] = rot
    aos[:, 5:9] = color
    buf_a = ctx.buffer(reserve=N * 36)
    vao_a = ctx.vertex_array(
        prog, [(buf_a, "2f 2f 1f 4f/i", "in_pos", "in_size", "in_rot", "in_color")]
    )

    def frame_a_tipico():
        aos[:, 0] += 0.01
        buf_a.write(aos)
        vao_a.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=N)

    # --- B: SoA f4 ---
    b_pos = ctx.buffer(reserve=N * 8)
    b_size = ctx.buffer(size.tobytes())
    b_rot = ctx.buffer(rot.tobytes())
    b_color = ctx.buffer(color.tobytes())
    vao_b = ctx.vertex_array(prog, [
        (b_pos, "2f/i", "in_pos"),
        (b_size, "2f/i", "in_size"),
        (b_rot, "1f/i", "in_rot"),
        (b_color, "4f/i", "in_color"),
    ])

    def frame_b_tipico():
        pos[:, 0] += 0.01
        b_pos.write(pos)
        vao_b.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=N)

    def frame_b_orphan():
        pos[:, 0] += 0.01
        b_pos.orphan()
        b_pos.write(pos)
        vao_b.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=N)

    def frame_b_pior():
        pos[:, 0] += 0.01
        b_pos.write(pos)
        b_size.write(size)
        b_rot.write(rot)
        b_color.write(color)
        vao_b.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=N)

    # --- C: SoA quantizado (frias em f2/u8-norm) ---
    c_pos = ctx.buffer(reserve=N * 8)
    c_size = ctx.buffer(size.astype("f2").tobytes())
    c_rot = ctx.buffer(rot.astype("f2").tobytes())
    c_color = ctx.buffer((color * 255.0 + 0.5).astype("u1").tobytes())
    vao_c = ctx.vertex_array(prog, [
        (c_pos, "2f/i", "in_pos"),
        (c_size, "2f2/i", "in_size"),
        (c_rot, "1f2/i", "in_rot"),
        (c_color, "4f1/i", "in_color"),
    ])

    def frame_c_tipico():
        pos[:, 0] += 0.01
        c_pos.write(pos)
        vao_c.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=N)

    def frame_c_pior():
        pos[:, 0] += 0.01
        c_pos.write(pos)
        c_size.write(size.astype("f2"))
        c_rot.write(rot.astype("f2"))
        c_color.write((color * 255.0 + 0.5).astype("u1"))
        vao_c.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=N)

    print(f"N={N}, {FRAMES} frames, {RUNS} runs, GPU={ctx.info['GL_RENDERER']}")
    print("--- Cenário 1: frame típico (só posições mudam) ---")
    measure("A  AoS write total (36B/inst)", frame_a_tipico, ctx)
    measure("B  SoA f4, só pos (8B/inst)", frame_b_tipico, ctx)
    measure("B' SoA f4, pos com orphan", frame_b_orphan, ctx)
    measure("C  SoA quant, só pos (8B/inst)", frame_c_tipico, ctx)
    print("--- Cenário 2: pior caso (todas as colunas mudam) ---")
    measure("A  AoS write total (36B/inst)", frame_a_tipico, ctx)
    measure("B  SoA f4 tudo (36B/inst)", frame_b_pior, ctx)
    measure("C  SoA quant tudo (18B/inst)", frame_c_pior, ctx)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Executar (FOREGROUND) e decidir**

Run: `.venv\Scripts\python benchmarks/lab/exp_soa_layout.py` (timeout generoso)
Expected: tabela de ms/frame. Critérios de decisão:
- Se B/C < A no cenário 1 com folga (>1.5x) → adotar SoA; entre B e C, C ganha se
  o cenário 2 mostrar vantagem e o típico empatar (a quantização não pode custar
  no caminho quente, pois pos segue f4 nos dois).
- orphan só entra se B' < B reproduzivelmente.
- Se A vencer os dois cenários: PARAR e reavaliar com o usuário (contradiz a
  aritmética de bytes — investigar antes de prosseguir).

- [ ] **Step 3: Registrar em RESULTS.md e commitar**

Anexar seção `## Lab 2026-07-07: layout SoA + quantização` com hardware, tabela
(todas as estratégias × cenários, min de 5 runs), e o parágrafo de decisão.

```powershell
git add benchmarks/lab/exp_soa_layout.py benchmarks/RESULTS.md
git commit -m "lab: SoA layout and quantization upload experiment"
```

---

### Task 2: Cutover SoA (storage + grupos + batches + renderers + layer)

**Files:**
- Modify: `fastobjects/_batchcore.py` (colunas `_cols` no lugar de `data`)
- Modify: `fastobjects/group.py` (propriedades indexam `_cols`)
- Modify: `fastobjects/batch.py`, `fastobjects/shapes.py` (spawn/fábricas escrevem nas colunas; `pos/size/rot/color` viram properties)
- Modify: `fastobjects/core/renderer.py` (`SpriteRenderer` com 1 VBO/atributo)
- Modify: `fastobjects/layer.py` (SurfaceLayer monta `_cols` de 1 instância)
- Modify: `tests/test_batch.py`, `tests/test_group.py`, `tests/test_despawn.py` (adaptar usos de `batch.data`)

**Interfaces:**
- Consumes: decisão do Task 1 (formatos: pos `"2f/i"`; size `"2f2/i"`; rot `"1f2/i"`; color `"4f1/i"`; kind `"1f2/i"` — se B vencer sem quantização, frias ficam f4 e a conversão `_convert` vira identidade).
- Produces (Task 3 depende):
  - `BatchCore.__init__(capacity: int, unit: str, *, kind: bool = False)` cria `self._cols: dict[str, np.ndarray]` com `pos (cap,2)`, `size (cap,2)`, `rot (cap,)`, `color (cap,4)` (+ `kind (cap,)` se `kind=True`), todas f4; `self._dirty: set[str]`; `self._mark_all()` (= todas menos "pos").
  - `despawn`/`clear` compactam/limpam coluna a coluna e chamam `_mark_all()`.
  - `BatchCore.draw()` → `self._renderer.render(self._cols, self.count, self._dirty)`; limpa `_dirty` depois.
  - `SpriteRenderer(ctx, texture, capacity, view_size)` e `_ShapeRenderer(ctx, capacity, view_size)` com `.render(cols: dict, count: int, dirty: set) -> None` e `.uploads: int` (contador de writes, para testes). **Neste task**, `render` ignora `dirty` e sobe todas as colunas (dirty real chega no Task 3).
  - `SpriteGroup` — mapa coluna→(array, índice): x=(pos,0), y=(pos,1), w=(size,0), h=(size,1), rot=(rot,None), pos/size/color=blocos; getters/setters de size/w/h/rot/color chamam `self._batch._dirty.add(<coluna>)`.
  - `SpriteBatch.pos/size/rot/color` e `ShapeBatch` idem: properties devolvendo `self._cols[...]`; as de size/rot/color marcam sujo. `batch.data` deixa de existir.

- [ ] **Step 1: Reescrever `_batchcore.py`** — `__init__` cria `_cols`/`_dirty`; `_mark_all()`; `despawn` troca a cópia única por `for arr in self._cols.values(): arr[start:new] = arr[stop:count]` (mesmas regras de grupos, mesmo guard); `clear` chama `_mark_all()`; `draw` passa `_cols/count/_dirty` e limpa o set. Docstrings atualizados (o modelo "paga pela mudança" + caveat de não guardar views entre frames).

- [ ] **Step 2: Reescrever `group.py`** — mesmas assinaturas/erros/`_check_alive`; corpos passam a indexar `self._batch._cols["pos"][self._slice, 0]` etc.; setters e getters de w/h/rot/size/color adicionam a coluna em `self._batch._dirty`. Docstring ganha o caveat.

- [ ] **Step 3: Adaptar `batch.py` e `shapes.py`** — `super().__init__(capacity, "sprites")` / `(capacity, "formas", kind=True)`; spawn/rects/circles/lines escrevem em `self._cols[...]` (vetorizado como hoje) — `_alloc` continua; propriedades públicas conforme Interfaces; `FLOATS_PER_SPRITE`/`SHAPE_FLOATS`/`STRIDE` morrem com o layout.

- [ ] **Step 4: Reescrever `core/renderer.py` e `_ShapeRenderer`** — buffers por atributo (reserve = capacity × bytes do formato), VAO multi-VBO, `render(cols, count, dirty)` sobe TODAS as colunas (pos f4 direto; frias via `_convert`: color→`(c*255+0.5).astype("u1")`, size/rot/kind→`.astype("f2")`), `uploads += 1` por write. Shaders inalterados.

- [ ] **Step 5: Adaptar `layer.py`** — `self._cols` com os 4 arrays de 1 instância; `draw()` → `render(self._cols, 1, set())` (o renderer deste task sobe tudo; o Task 3 ajusta para `self._dirty` próprio).

- [ ] **Step 6: Adaptar os testes** — substituir todo uso de `batch.data` por colunas públicas: `batch.data[:n, 0]`→`batch.pos[:n, 0]`; `batch.data[:5, 5:9]`→`batch.color[:5]`; `batch.data[:4, 4]`→`batch.rot[:4]`; `batch.data[:3, 9]`→asserts de kind trocados por leitura via `batch._cols["kind"][:3]` (interno é aceitável em teste de shapes); `test_views_write_through_to_data` renomeia para `test_views_write_through_to_columns`.

- [ ] **Step 7: Suíte completa**

Run: `.venv\Scripts\python -m pytest -v`
Expected: **87 passed** — pixel tests intactos (mesma imagem com atributos quantizados). Falha de pixel = investigar formato/conversão antes de prosseguir (systematic-debugging).

- [ ] **Step 8: Commit**

```powershell
git add fastobjects tests
git commit -m "feat!: SoA column storage with per-attribute VBOs and quantized cold uploads"
```

---

### Task 3: Dirty tracking real (subir só o que mudou)

**Files:**
- Modify: `fastobjects/core/renderer.py`, `fastobjects/shapes.py` (render respeita `dirty`)
- Modify: `fastobjects/layer.py` (dirty próprio: sobe frias uma vez)
- Test: `tests/test_dirty.py`

**Interfaces:**
- Consumes: Task 2 (`_cols`, `_dirty`, `uploads`, marcação nas properties).
- Produces: `render` sobe `pos` sempre + apenas colunas em `dirty`; `batch.draw()` continua limpando o set. Contador `uploads` permite asserts exatos.

- [ ] **Step 1: Testes (falhando)** — `tests/test_dirty.py` (fixture `gl` padrão dos outros arquivos; `make_batch` como em test_despawn):

```python
def test_first_draw_uploads_everything(gl): ...
    # spawn(10); draw(); uploads == 4 (pos + size + rot + color)  [5 no ShapeBatch]

def test_untouched_frame_uploads_only_pos(gl): ...
    # segundo draw() sem tocar nada: uploads cresce só +1 (pos)

def test_touching_color_reuploads_color(gl): ...
    # g.color = (0,1,0,1); draw(); uploads cresce +2 (pos + color)
    # e pixel test: a cor NOVA aparece no FBO (prova que o valor chegou à GPU)

def test_reading_marks_dirty_conservatively(gl): ...
    # _ = g.rot (só leitura); draw(); uploads cresce +2 (pos + rot)

def test_spawn_despawn_clear_mark_all(gl): ...
    # após cada um, draw() sobe todas as colunas de novo

def test_batch_level_properties_mark_dirty(gl): ...
    # batch.color[:1] = ...; draw(); +2
```

(código completo dos testes escrito na execução seguindo exatamente estes
contratos de contagem; pixel test de cor usa o padrão read_pixels dos outros
arquivos.)

- [ ] **Step 2: Ver falhar** — `pytest tests/test_dirty.py -v` → FAIL (uploads sobe sempre 4/5).

- [ ] **Step 3: Implementar** — `render` sobe frias somente se `name in dirty`; `layer.py` mantém `self._dirty = {"size", "rot", "color"}` inicial e `draw()` passa/limpa.

- [ ] **Step 4: Suíte completa** — Expected: **93 passed** (87 + 6).

- [ ] **Step 5: Commit**

```powershell
git add fastobjects tests/test_dirty.py
git commit -m "feat: conservative per-column dirty tracking - upload only what changed"
```

---

### Task 4: Aceite — benchmark_2d + arena + RESULTS.md

**Files:**
- Modify: `benchmarks/RESULTS.md`

- [ ] **Step 1: benchmark_2d (FOREGROUND)** — `.venv\Scripts\python benchmarks/benchmark_2d.py --libs moderngl fastobjects`
Expected: fastobjects ≥ 80% do teto em 100k (≥ ~344 FPS se o teto repetir ~430).
Abaixo de 80% → perfilar o que sobrou (upload? física? draw?) com systematic-debugging antes de seguir.

- [ ] **Step 2: Arena** — `.venv\Scripts\python benchmarks/arena/run_all.py --save`; renomear o heading novo para `## Arena 2026-07-07 (pós-SoA)`. Expected: fastobjects 1º, ≥ 218.809 (esperado subir — upload de sprite caiu de 36 para 8 B/inst no frame típico).

- [ ] **Step 3: Registrar + lint + commit** — seção no RESULTS.md com as duas tabelas e o antes/depois do gap; `ruff check fastobjects tests benchmarks/lab/exp_soa_layout.py`; commit `"bench: SoA closes upload gap - <X>% of raw moderngl ceiling at 100k"`.

---

### Task 5: Release 0.3.0 (PÓS-MERGE em main)

- [ ] **Step 1:** Bump `0.2.0` → `0.3.0` em pyproject.toml, `fastobjects/__init__.py`, tests/test_smoke.py; suíte verde; commit `"chore: bump to 0.3.0 after SoA upload optimization"`. (Ainda na branch.)
- [ ] **Step 2:** Merge em main (finishing-a-development-branch: testes → merge → testes → delete branch → push).
- [ ] **Step 3:** Tag `v0.3.0` + push; release pre-release via REST API (padrão da memória do projeto — sem gh CLI; token de `git credential fill`); notas destacando o modelo "paga pela mudança, não pela existência" + números antes/depois; verificar publish.yml e PyPI (0.3.0).

---

## Fora deste plano

- `opaque=True`, texture atlas, hosts extras, docs — fases próprias.
