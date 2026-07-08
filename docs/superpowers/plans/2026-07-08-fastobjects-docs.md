# FastObjects Fase 5 (Docs bilíngue + higiene) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** README EN/PT com a tabela da arena no topo, site mkdocs-material bilíngue publicado no GitHub Pages, dois exemplos novos, os itens de higiene do ledger fechados e release 0.3.1.

**Architecture:** Conteúdo do site em `docs/site/` (sufixos `.pt.md` via `mkdocs-static-i18n`; EN default), `mkdocs.yml` na raiz, deploy por workflow (`mkdocs build --strict` → `actions/deploy-pages`) com Pages habilitado via REST API. Referência de API escrita à mão (docstrings do código são PT). Spec: `docs/superpowers/specs/2026-07-08-fastobjects-docs-design.md`.

**Tech Stack:** mkdocs-material ≥9, mkdocs-static-i18n ≥1 (extra `[docs]`; core intocado), GitHub Actions Pages.

## Global Constraints

- Todo bloco de código dos docs/README roda copiado-e-colado (convenção do projeto) — exemplos completos verificados com `--frames 120` em foreground.
- Números citados: arena 328.213 sprites@60fps / 86x (RESULTS.md, "Arena 2026-07-07 (pós-SoA)"); benchmark_2d 384 FPS @100k (109% do teto).
- Core deps intocadas; mkdocs só em `[docs]`.
- Mensagens de erro novas seguem o padrão acionável; commits sem `Co-Authored-By`.
- Suíte verde em todo commit (baseline 94; termina com 98).
- Branch: `phase-5-docs`. Cuidado com encoding: escrever arquivos com Write/Edit (nunca `Set-Content -Encoding utf8` do PS5.1 — escreve BOM).

---

### Task 1: Higiene (itens do ledger, um commit)

**Files:**
- Create: `tests/conftest.py`
- Modify: `fastobjects/window.py`, `fastobjects/_context.py`, `fastobjects/external.py`, `fastobjects/layer.py`, `benchmarks/arena/run_all.py`
- Test: `tests/test_renderer.py`, `tests/test_context.py`, `tests/test_layer.py`, `tests/test_run_all.py`, e caminho `BUNNY` em `tests/test_batch.py`, `tests/test_group.py`, `tests/test_despawn.py`, `tests/test_dirty.py`

**Interfaces:**
- Produces: suíte independente de cwd e de ordem; `run_all.py --label "texto"`; guards/typing novos. Nada que os tasks seguintes consumam além da suíte verde.

- [ ] **Step 1: conftest.py (restaura a janela atual entre testes)**

```python
import pytest

from fastobjects import _context


@pytest.fixture(autouse=True)
def restore_current_window():
    previous = _context.get_current()
    yield
    _context.set_current(previous)
```

- [ ] **Step 2: caminho absoluto do asset nos 4 arquivos de teste**

Em test_batch/test_group/test_despawn/test_dirty, trocar
`BUNNY = "benchmarks/arena/assets/bunny.png"` por:

```python
from pathlib import Path

BUNNY = str(Path(__file__).resolve().parent.parent / "benchmarks" / "arena" / "assets" / "bunny.png")
```

(ajustando imports; `from pathlib import Path` no topo.)

- [ ] **Step 3: teste de rotação de sprite (test_renderer.py)**

```python
def test_sprite_rotation_quarter_turn(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    renderer = SpriteRenderer(ctx, white_texture(ctx), capacity=16, view_size=(64, 64))
    # sprite alto e fino (4x20) rotacionado 90°: a pegada vira horizontal
    cols = make_sprite_cols(32, 32, 4, 20, np.pi / 2, (1.0, 0.0, 0.0, 1.0))
    renderer.render(cols, 1, {"size", "rot", "color"})
    px = read_pixels(fbo)
    assert px[32, 24][0] > 200  # 8px à esquerda do centro: dentro dos 20 de largura
    assert px[24, 32][0] < 10  # 8px acima do centro: fora dos 4 de altura
```

- [ ] **Step 4: teste de resolve parcial (test_context.py)**

```python
def test_resolve_partial_overrides():
    win = Window(320, 240, "partial", visible=False)
    ctx, view_size = _context.resolve(None, (10, 20))
    assert ctx is win.ctx
    assert view_size == (10, 20)
    sentinel = object()
    ctx2, view_size2 = _context.resolve(sentinel, None)
    assert ctx2 is sentinel
    assert view_size2 == (320, 240)
    win.close()
```

- [ ] **Step 5: guard de surface vazia (layer.py + test_layer.py)**

Em `SurfaceLayer.__init__`, após `w, h = surface.get_size()`:

```python
        if w <= 0 or h <= 0:
            raise ValueError(
                f"Surface de tamanho inválido {surface.get_size()} — use uma "
                "surface com largura e altura > 0."
            )
```

Teste (test_layer.py):

```python
def test_zero_size_surface_raises(gl):
    ctx, _ = gl
    surf = pygame.Surface((0, 0), pygame.SRCALPHA)
    with pytest.raises(ValueError, match="tamanho inválido"):
        SurfaceLayer(surf, ctx=ctx, view_size=(64, 64))
```

- [ ] **Step 6: run_all.py — `--label` e timeout**

- `parser.add_argument("--label", default="", help="rótulo anexado ao heading do RESULTS.md")`.
- Função pura `def make_heading(stamp: str, label: str) -> str: return f"## Arena {stamp} ({label})" if label else f"## Arena {stamp}"`; usar no `--save`.
- `subprocess.run(..., timeout=600)` com `except subprocess.TimeoutExpired: print(f"TIMEOUT: {bench}", file=sys.stderr); continue`.
- Teste (test_run_all.py):

```python
def test_make_heading_with_and_without_label():
    from run_all import make_heading

    assert make_heading("2026-07-08", "") == "## Arena 2026-07-08"
    assert make_heading("2026-07-08", "pós-X") == "## Arena 2026-07-08 (pós-X)"
```

- [ ] **Step 7: typing e docstrings**

- `window.py`: `class Drawable(Protocol): def draw(self) -> None: ...` (import
  `Protocol` de typing) e `def draw(self, *batches: Drawable) -> None:`.
- `_context.py`: docstring do módulo ganha "Estado global de thread única —
  todo uso de GL do FastObjects assume a main thread"; anotações de
  `set_current/get_current/require_current` viram `Window | ExternalWindow`
  (import de `ExternalWindow` só em TYPE_CHECKING).
- `external.py`: docstring de `attach` ganha "Chame uma vez por janela do
  host — attaches repetidos criam wrappers moderngl independentes sobre o
  mesmo contexto GL e podem dessincronizar estado."

- [ ] **Step 8: suíte + lint + commit**

Run: `.venv\Scripts\python -m pytest -q` → `98 passed` (94 + 4).
Run: `.venv\Scripts\python -m ruff check fastobjects tests benchmarks/arena/run_all.py` → limpo.

```powershell
git add tests fastobjects benchmarks/arena/run_all.py
git commit -m "chore: hygiene - cwd-free tests, context fixture, rotation test, run_all label/timeout, typing"
```

---

### Task 2: Exemplos novos

**Files:**
- Create: `examples/bunnymark.py`, `examples/shapes_input.py`

**Interfaces:**
- Produces: dois exemplos referenciados pelos docs (Tasks 3–5); mesmo padrão do pygame_interop (`--frames N` para auto-teste, docstring com instruções).

- [ ] **Step 1: bunnymark.py** — modo nativo: `--n` (default 100_000) coelhos com física vetorizada (gravidade + quique, direto nas views do grupo), FPS no título da janela (atualizado 2x/s via `glfw.set_window_title`? NÃO — usar `pygame`? NÃO: API pública. Solução: `Window` não expõe set_title; imprimir FPS no stdout 1x/s e mostrar contagem no print final), ESC sai, `--frames N` auto-teste imprimindo `bunnymark ok: <frames> frames, <n> sprites, <fps média> fps`. Asset `benchmarks/arena/assets/bunny.png` resolvido via `Path(__file__)`.
- [ ] **Step 2: shapes_input.py** — círculo segue `win.mouse`, retângulo movido pelas setas (`fo.KEY_LEFT/...`), 3 linhas decorativas fixas, HUD nenhum (sem texto no core); ESC sai; `--frames N` imprime `shapes ok: <frames> frames`.
- [ ] **Step 3: Verificar** — `.venv\Scripts\python examples/bunnymark.py --frames 120 --n 50000` e `.venv\Scripts\python examples/shapes_input.py --frames 120` (foreground, janelas abrem). Ambos imprimem a linha final sem exceção.
- [ ] **Step 4: Commit** — `git add examples; git commit -m "feat: native bunnymark and shapes+input examples"`.

---

### Task 3: READMEs EN + PT-BR

**Files:**
- Modify: `README.md`
- Create: `README.pt-BR.md`

**Interfaces:**
- Consumes: números do RESULTS.md (328.213/86x; 384 FPS/109%); quick start atual do usuário (preservar).
- Produces: README que o Task 6 (release) leva ao PyPI; links para o site (URL final `https://enzo-azevedo.github.io/FastObjects/`).

- [ ] **Step 1: README.md (EN)** — estrutura exata:
  1. `# FastObjects` + tagline + linha de links: `[Docs](https://enzo-azevedo.github.io/FastObjects/) · [Documentação em português](README.pt-BR.md)`.
  2. **Tabela da arena imediatamente após** (convenção: benchmark no topo): fastobjects 328,213 / arcade 3,795 / raylib 3,795 / pygame-ce 2,530 / pyglet 2,530, com data/hardware e link RESULTS.md; nota de um parágrafo sobre variação entre runs.
  3. Installation + Quick start ATUAIS (preservar o código do usuário; acrescentar nota de que `player.png` é qualquer imagem).
  4. "Why it's fast" reescrito: SoA por coluna, 1 draw call instanciado, dirty tracking ("you pay for change, not existence" — positions upload every frame, cold columns only when touched), decisões por benchmark (link RESULTS.md), 384 FPS @100k vs 353 do renderer moderngl mínimo.
  5. "Use it inside pygame": snippet curto (set_mode OPENGL|DOUBLEBUF → fo.attach → batch/spawn/despawn → SurfaceLayer p/ HUD) + link examples/pygame_interop.py.
  6. Examples (lista dos 3) + Development (atual).
- [ ] **Step 2: README.pt-BR.md** — espelho fiel em PT com `[English → README.md]` no topo.
- [ ] **Step 3: Commit** — `git add README.md README.pt-BR.md; git commit -m "docs: benchmark-first bilingual README with interop and dirty-tracking sections"`.

---

### Task 4: Site mkdocs — scaffold + Home + Getting Started

**Files:**
- Modify: `pyproject.toml` (extra `docs`), `.gitignore` (+`site/`)
- Create: `mkdocs.yml`, `docs/site/index.md`, `docs/site/index.pt.md`, `docs/site/getting-started.md`, `docs/site/getting-started.pt.md`

**Interfaces:**
- Produces: `mkdocs build --strict` verde; estrutura/nav que os Tasks 5 usam (nav já lista TODAS as páginas — as ausentes entram nos tasks seguintes, então o build --strict só passa ao final do Task 5; até lá validar com `mkdocs build` sem --strict OU criar stubs). **Decisão: criar todas as 16 páginas como stubs de 1 linha neste task** (título + "em construção" temporário) para o --strict passar desde já; Tasks 5 preenchem.

- [ ] **Step 1: pyproject** — `docs = ["mkdocs-material>=9", "mkdocs-static-i18n>=1"]` em optional-dependencies; `pip install mkdocs-material mkdocs-static-i18n` no venv. `.gitignore` += `site/`.
- [ ] **Step 2: mkdocs.yml**

```yaml
site_name: FastObjects
site_description: The fastest 2D object rendering library for Python
site_url: https://enzo-azevedo.github.io/FastObjects/
repo_url: https://github.com/Enzo-Azevedo/FastObjects
repo_name: Enzo-Azevedo/FastObjects
docs_dir: docs/site
theme:
  name: material
  features:
    - navigation.sections
    - navigation.top
    - content.code.copy
  palette:
    - media: "(prefers-color-scheme: light)"
      scheme: default
      primary: deep orange
      toggle: {icon: material/weather-night, name: Dark mode}
    - media: "(prefers-color-scheme: dark)"
      scheme: slate
      primary: deep orange
      toggle: {icon: material/weather-sunny, name: Light mode}
markdown_extensions:
  - admonition
  - pymdownx.superfences
  - pymdownx.details
plugins:
  - search
  - i18n:
      docs_structure: suffix
      languages:
        - locale: en
          default: true
          name: English
          build: true
        - locale: pt
          name: Português
          build: true
nav:
  - Home: index.md
  - Getting Started: getting-started.md
  - Guide:
      - Sprites & Groups: guide/sprites.md
      - Shapes: guide/shapes.md
      - Window & Input: guide/window-input.md
      - Using inside pygame: guide/interop.md
  - Performance: performance.md
  - API Reference: api.md
```

- [ ] **Step 3: index (EN/PT)** — hero (tagline + o que é), tabela da arena (mesma do README), mapa de seções com links, install de uma linha. PT = tradução fiel.
- [ ] **Step 4: getting-started (EN/PT)** — install (+extras dev/bench), primeiro programa completo (janela + spawn vetorizado de 1.000 sprites + física simples + ESC), execução esperada, próximos passos (links).
- [ ] **Step 5: stubs das páginas restantes** — guide/sprites, guide/shapes, guide/window-input, guide/interop, performance, api (EN+PT cada) com apenas o H1 correto.
- [ ] **Step 6: Build** — `.venv\Scripts\python -m mkdocs build --strict` → sem erros/warnings.
- [ ] **Step 7: Commit** — `git add mkdocs.yml docs/site pyproject.toml .gitignore; git commit -m "docs: mkdocs-material bilingual site scaffold with home and getting started"`.

---

### Task 5: Site — guias, performance e referência de API (EN/PT)

**Files:**
- Modify: as 12 páginas stub de `docs/site/`

**Interfaces:**
- Consumes: exemplos do Task 2 (referenciados), números do RESULTS.md.
- Produces: site completo; `mkdocs build --strict` verde.

Contratos por página (EN; PT é tradução fiel):

- [ ] **guide/sprites** — SpriteBatch (criação, capacity, textura), spawn vetorizado (escalares e arrays), SpriteGroup (views x/y/pos/size/rot/color, slicing, len), despawn (handles sobreviventes + regras de invalidação em admonition), clear, o modelo de custos (admonition "How uploads work": pos sempre / frias quando tocadas / caveat de views guardadas), snippet completo executável.
- [ ] **guide/shapes** — rects/circles (SDF, guarda diâmetro)/lines (viram retângulos rotacionados), mistura em um draw, mesmo SpriteGroup, snippet executável.
- [ ] **guide/window-input** — Window(args), frame loop (@win.frame/run/request_close/dt), clear/draw, keys (fo.KEY_*), mouse, caveat de janela fechada, snippet executável (o shapes_input.py resumido).
- [ ] **guide/interop** — por que OPENGL|DOUBLEBUF, attach (uma vez por janela), quem é dono do quê (tabela host×fastobjects), SurfaceLayer (update/draw, HUD com pygame.font), despawn em jogos, link pygame_interop.py, snippet executável mínimo.
- [ ] **performance** — tabela da arena + benchmark_2d (384 vs 353 @100k), como reproduzir (comandos run_all/benchmark_2d, aviso de foreground), filosofia "nenhuma decisão sem benchmark" (labs write/orphan e SoA/quantização como exemplos, link RESULTS.md), dicas práticas (um batch por textura, vetorize com arrays, prefira despawn a clear+respawn parcial).
- [ ] **api** — para cada símbolo público: assinatura exata, parâmetros, retorno, erros levantados (Window, Window.frame/run/draw/clear/poll/swap/request_close/should_close/keys/mouse, SpriteBatch(+spawn/despawn/clear/draw/pos/size/rot/color), ShapeBatch(+rects/circles/lines), SpriteGroup (propriedades/slicing/invalidação), SurfaceLayer(+update/draw), attach/ExternalWindow, CapacityError, constantes KEY_*/MOUSE_*).
- [ ] **Validação** — `mkdocs build --strict`; extrair e rodar cada snippet "executável completo" das páginas EN (com `--frames`-style guarda ou janela invisível onde couber; validação manual mínima: rodar os 4 snippets de guia salvos no scratchpad).
- [ ] **Commit** — `git add docs/site; git commit -m "docs: full bilingual guides, performance and API reference"`.

---

### Task 6: Workflow GitHub Pages + habilitação + deploy

**Files:**
- Create: `.github/workflows/docs.yml`

- [ ] **Step 1: workflow**

```yaml
name: Docs

on:
  push:
    branches: [main]
    paths: ["docs/site/**", "mkdocs.yml", ".github/workflows/docs.yml"]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.x"
      - run: python -m pip install mkdocs-material mkdocs-static-i18n
      - run: mkdocs build --strict
      - uses: actions/upload-pages-artifact@v3
        with:
          path: site
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: habilitar Pages via API** — script no scratchpad (padrão das releases): `POST /repos/Enzo-Azevedo/FastObjects/pages` body `{"build_type": "workflow"}` (token de `git credential fill`; 409 = já habilitado, ok). Se 403/404 por escopo do token: reportar ao usuário o passo manual e seguir.
- [ ] **Step 3: Commit + merge + deploy** — commit do workflow; **merge da branch em main** (finishing: suíte → merge → suíte → push); o push dispara o workflow; acompanhar via API `/actions/runs` até `success`; verificar `https://enzo-azevedo.github.io/FastObjects/` e a página PT respondendo (GET 200 com urllib).

---

### Task 7: Release 0.3.1 (PÓS-MERGE, em main)

- [ ] Bump 0.3.0 → 0.3.1 (pyproject, `__init__`, test_smoke — SEM BOM: usar Edit); suíte 98 verde; commit `"chore: bump to 0.3.1 - docs release"`; push.
- [ ] Tag `v0.3.1` + push; pre-release GitHub via REST API (notas: docs site EN/PT + link, README novo, exemplos, higiene); verificar publish.yml `success` e PyPI 0.3.1.

---

## Fora deste plano

Hosts pyglet/arcade/raylib (fase seguinte) e texture atlas (depois) — ordem acordada com o usuário.
