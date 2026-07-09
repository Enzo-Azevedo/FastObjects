# FastObjects Hosts Extras (pyglet/arcade/raylib) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task (execução INLINE, a pedido do usuário). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Validar empiricamente quais hosts (pyglet, arcade, raylib) funcionam com `fo.attach`, entregar exemplo + doc para cada um que funciona, documentar honestamente os que não funcionam, e lançar 0.4.0.

**Architecture:** Fase exploratória guiada por um spike. Task 1 mede cada host (verde/amarelo/vermelho) e o resultado ROTEIA os tasks seguintes: exemplos só para hosts verde/amarelo; o helper `ExternalWindow.isolated()` só nasce se um host amarelo exigir. `fo.attach` já é genérico — nenhuma mudança no core exceto o helper condicional. Spec: `docs/superpowers/specs/2026-07-09-fastobjects-extra-hosts-design.md`.

**Tech Stack:** moderngl, pyglet 2.1.15, arcade 3.3.3, pyray (raylib 6.0.1.0) — todos já no extra `[bench]`.

## Global Constraints

- Nenhuma API nova exceto `ExternalWindow.isolated()`, e SÓ se o spike provar necessário (YAGNI).
- Benchmarks/spikes GL rodam em FOREGROUND (lição do RESULTS.md); cada host num subprocesso próprio (isolamento de contexto GL).
- Exemplos seguem o padrão atual: docstring com instruções, `--frames N` para auto-teste, ESC/fechar sai, asset via `Path(__file__)`.
- Mensagens/erros acionáveis; commits sem `Co-Authored-By`; suíte verde antes de cada commit (baseline 98).
- Toda medição do spike vai para `benchmarks/RESULTS.md` com data/hardware.
- Branch: `extra-hosts`. Escrever arquivos com Write/Edit (não `Set-Content -Encoding utf8` do PS5.1 — BOM).

---

### Task 1: Spike — validar cada host (DECIDE o resto da fase)

**Files:**
- Create: `benchmarks/lab/spike_hosts.py`
- Modify: `benchmarks/RESULTS.md`

**Interfaces:**
- Produces: para cada host, um status `verde|amarelo|vermelho` + nota, registrado no RESULTS.md. Esse resultado decide: quais exemplos criar (Task 3), se `isolated()` é necessário (Task 2), e a tabela de docs (Task 4).

- [ ] **Step 1: Escrever `benchmarks/lab/spike_hosts.py`**

Cada host tem uma função `probe_<host>()` que: cria a janela do host com GL,
`fo.attach`, desenha um `ShapeBatch` com um retângulo vermelho no centro sobre
fundo escuro, lê o pixel central via `ext.ctx.screen.read`, e classifica. Roda
via `--host <nome>` (um subprocesso por host, chamado pelo `main`).

```python
"""Spike: quais hosts (pyglet/arcade/raylib) funcionam com fo.attach?

Cada host roda em subprocesso próprio (isolamento de contexto GL). Para cada
um: cria a janela do host com OpenGL, fo.attach, desenha um retângulo vermelho
no centro, lê o pixel central e classifica:
  verde     = attach cru basta (pixel vermelho sem intervenção)
  amarelo   = só funciona salvando/restaurando estado GL em volta do draw
  vermelho  = attach falha ou o estado do host corrompe o render

Rode: python benchmarks/lab/spike_hosts.py   (orquestra os 3 subprocessos)
"""

from __future__ import annotations

import subprocess
import sys

W, H = 320, 240
CX, CY = W // 2, H // 2
HOSTS = ["pyglet", "arcade", "raylib"]


def _draw_and_read(ext):
    """Desenha um retângulo vermelho no centro e lê o pixel central (RGB 0-255)."""
    import fastobjects as fo

    batch = fo.ShapeBatch(capacity=4, view_size=(W, H))
    batch.rects(1, x=float(CX), y=float(CY), w=60.0, h=60.0, color=(1.0, 0.0, 0.0, 1.0))
    ext.clear(0.0, 0.0, 0.1)
    batch.draw()
    import numpy as np
    # ctx.screen: framebuffer padrão do host. Lê 1px no centro (origem GL: baixo).
    raw = ext.ctx.screen.read(viewport=(CX, H - CY, 1, 1), components=3)
    return np.frombuffer(raw, dtype="u1")


def _classify(px) -> str:
    r, g, b = int(px[0]), int(px[1]), int(px[2])
    return "verde" if (r > 200 and g < 60 and b < 60) else "?"


def probe_pyglet() -> None:
    import pyglet

    import fastobjects as fo

    win = pyglet.window.Window(W, H, "spike pyglet", visible=True)
    win.switch_to()
    ext = fo.attach(view_size=(W, H))
    px = _draw_and_read(ext)
    res = _classify(px)
    if res != "verde":
        # tenta amarelo: salva/restaura estado GL em volta do draw
        res = _try_isolated(ext)
    print(f"pyglet {res}: pixel={tuple(int(v) for v in px)}")
    win.close()


def probe_arcade() -> None:
    import arcade

    import fastobjects as fo

    win = arcade.Window(W, H, "spike arcade")
    win.switch_to()
    ext = fo.attach(view_size=(W, H))
    px = _draw_and_read(ext)
    res = _classify(px)
    if res != "verde":
        res = _try_isolated(ext)
    # rota alternativa: reusar o próprio ctx do arcade em vez de attach
    alt = _try_arcade_own_ctx(win)
    print(f"arcade {res} (attach) / {alt} (ctx próprio): pixel={tuple(int(v) for v in px)}")
    win.close()


def probe_raylib() -> None:
    import pyray as rl

    import fastobjects as fo

    rl.set_config_flags(0)
    rl.init_window(W, H, "spike raylib")
    try:
        ext = fo.attach(view_size=(W, H))
    except Exception as e:  # noqa: BLE001
        print(f"raylib vermelho: attach falhou ({type(e).__name__}: {e})")
        rl.close_window()
        return
    rl.begin_drawing()
    rl.clear_background(rl.Color(0, 0, 25, 255))
    try:
        px = _draw_and_read(ext)
        res = _classify(px)
        if res != "verde":
            res = _try_isolated(ext)
    except Exception as e:  # noqa: BLE001
        res = f"vermelho (draw/read falhou: {type(e).__name__})"
        px = (0, 0, 0)
    rl.end_drawing()
    print(f"raylib {res}: pixel={tuple(int(v) for v in px)}")
    rl.close_window()


def _try_isolated(ext) -> str:
    """Salva/restaura blend+program+VAO+textura ativa em volta do draw; reclassifica."""
    import moderngl  # noqa: F401

    from OpenGL import GL

    blend = GL.glIsEnabled(GL.GL_BLEND)
    prog = GL.glGetIntegerv(GL.GL_CURRENT_PROGRAM)
    vao = GL.glGetIntegerv(GL.GL_VERTEX_ARRAY_BINDING)
    tex = GL.glGetIntegerv(GL.GL_TEXTURE_BINDING_2D)
    try:
        px = _draw_and_read(ext)
    finally:
        (GL.glEnable if blend else GL.glDisable)(GL.GL_BLEND)
        GL.glUseProgram(prog)
        GL.glBindVertexArray(vao)
        GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
    return "amarelo" if _classify(px) == "verde" else "vermelho"


def _try_arcade_own_ctx(win) -> str:
    """Rota alternativa do arcade: usar win.ctx diretamente, sem fo.attach."""
    try:
        import numpy as np

        import fastobjects as fo

        batch = fo.ShapeBatch(capacity=4, ctx=win.ctx, view_size=(W, H))
        batch.rects(1, x=float(CX), y=float(CY), w=60.0, h=60.0,
                    color=(0.0, 1.0, 0.0, 1.0))
        win.ctx.screen.use()
        win.ctx.screen.clear(0.0, 0.0, 0.1)
        batch.draw()
        raw = win.ctx.screen.read(viewport=(CX, H - CY, 1, 1), components=3)
        px = np.frombuffer(raw, dtype="u1")
        return "verde" if (int(px[1]) > 200 and int(px[0]) < 60) else "vermelho"
    except Exception as e:  # noqa: BLE001
        return f"vermelho ({type(e).__name__})"


PROBES = {"pyglet": probe_pyglet, "arcade": probe_arcade, "raylib": probe_raylib}


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "--host":
        PROBES[sys.argv[2]]()
        return
    for host in HOSTS:
        print(f"== {host} ==", flush=True)
        proc = subprocess.run(
            [sys.executable, __file__, "--host", host],
            capture_output=True, text=True, timeout=120,
        )
        out = (proc.stdout + proc.stderr).strip()
        print(out if out else f"(sem saída, returncode={proc.returncode})")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Rodar o spike (FOREGROUND)**

Run: `.venv\Scripts\python benchmarks/lab/spike_hosts.py`
Expected: uma linha de status por host. Interpretar:
- Se um host imprime algo inesperado (crash de import, contexto nulo,
  segfault), investigar com systematic-debugging ANTES de classificar — o
  spike existe para produzir um veredito confiável, não um chute. Ajustar o
  probe daquele host se a API real divergir (ex.: arcade `win.ctx.screen` vs
  `win.ctx.fbo`; pyglet `switch_to` necessário; raylib exigindo `MSAA`/flags).
- Registrar o veredito final de cada host: verde / amarelo / vermelho + a nota
  técnica (o que precisou, ou por que falhou).

- [ ] **Step 3: Registrar em RESULTS.md e commitar**

Anexar seção `## Spike hosts 2026-07-09: pyglet / arcade / raylib` com
hardware, e por host: status + a rota que funcionou (attach cru / attach +
isolated / ctx próprio do host / não suportado) + nota. Este registro é a
decisão que governa os Tasks 2–4.

```powershell
git add benchmarks/lab/spike_hosts.py benchmarks/RESULTS.md
git commit -m "lab: spike attach against pyglet, arcade and raylib hosts"
```

- [ ] **Step 4: Rotear o resto da fase (anotar as decisões)**

Com base nos vereditos, decidir e anotar (no corpo do commit ou numa nota de
execução):
- Task 2 (`isolated()`) é criado? SIM se ≥1 host ficou **amarelo**; NÃO caso
  contrário.
- Task 3: quais exemplos criar? Um por host **verde/amarelo** (ou por host que
  funcione via ctx próprio). Nenhum para host **vermelho**.
- Task 4: linha de cada host na tabela de docs.

---

### Task 2: `ExternalWindow.isolated()` — SÓ se algum host ficou amarelo

**Files:**
- Modify: `fastobjects/external.py`
- Test: `tests/test_external.py`

**Interfaces:**
- Produces: `ExternalWindow.isolated()` context manager que salva/restaura o
  estado GL que o FastObjects toca. Consumido pelos exemplos de hosts amarelos
  (Task 3) e documentado (Task 4).

> **Condicional:** pular este task inteiro se o Task 1 não produziu nenhum host
> amarelo. Se pulado, anotar "Task 2 pulado — nenhum host exigiu isolamento" e
> seguir.

- [ ] **Step 1: Escrever o teste (offscreen)**

Em `tests/test_external.py`, adicionar (usa `Window(visible=False)` como host
GL genérico, como os outros testes de external):

```python
def test_isolated_restores_gl_state():
    from OpenGL import GL

    host = Window(320, 240, "iso", visible=False)
    ext = fo.attach(view_size=(320, 240))
    GL.glDisable(GL.GL_BLEND)  # estado do "host": blend desligado
    with ext.isolated():
        ext.ctx.enable(moderngl.BLEND)  # FastObjects liga blend
        assert GL.glIsEnabled(GL.GL_BLEND)
    assert not GL.glIsEnabled(GL.GL_BLEND)  # restaurado ao estado do host
    ext.close()
    host.close()
```

(Ajustar exatamente o conjunto de estado que o spike mostrou ser necessário —
o teste verifica ao menos o blend; incluir program/VAO se o spike exigiu.)

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_external.py -k isolated -v`
Expected: FAIL — `ExternalWindow` não tem `isolated`.

- [ ] **Step 3: Implementar `isolated()` em `external.py`**

Adicionar `from contextlib import contextmanager` no topo e o método na classe
`ExternalWindow` (o conjunto exato de estado sai do spike; abaixo o esqueleto
com blend+program+VAO+textura):

```python
    @contextmanager
    def isolated(self):
        """Salva e restaura o estado GL que o FastObjects toca (blend, program,
        VAO, textura 2D ativa), para conviver com hosts que gerenciam o próprio
        estado (ex.: arcade). Envolva os draws do FastObjects com ele:

            with ext.isolated():
                batch.draw()
        """
        from OpenGL import GL

        blend = GL.glIsEnabled(GL.GL_BLEND)
        prog = GL.glGetIntegerv(GL.GL_CURRENT_PROGRAM)
        vao = GL.glGetIntegerv(GL.GL_VERTEX_ARRAY_BINDING)
        tex = GL.glGetIntegerv(GL.GL_TEXTURE_BINDING_2D)
        try:
            yield
        finally:
            (GL.glEnable if blend else GL.glDisable)(GL.GL_BLEND)
            GL.glUseProgram(prog)
            GL.glBindVertexArray(vao)
            GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
```

Nota: `PyOpenGL` (`OpenGL`) já é dependência transitiva do moderngl/pyglet no
venv; o import é lazy (dentro do método), então não vira dependência do core.

- [ ] **Step 4: Rodar os testes**

Run: `.venv\Scripts\python -m pytest -v`
Expected: 99 passed (98 + 1).

- [ ] **Step 5: Commit**

```powershell
git add fastobjects/external.py tests/test_external.py
git commit -m "feat: ExternalWindow.isolated() saves/restores GL state for stateful hosts"
```

---

### Task 3: Exemplos por host (um por host verde/amarelo)

**Files:**
- Create: `examples/pyglet_interop.py`, `examples/arcade_interop.py` e/ou
  `examples/raylib_interop.py` — **apenas os dos hosts que passaram no Task 1**.

**Interfaces:**
- Consumes: `fo.attach`, `SpriteBatch`/`ShapeBatch`, e `ext.isolated()` (Task 2)
  para hosts amarelos.
- Produces: exemplos executáveis, referenciados pela doc (Task 4).

Cada exemplo segue o molde (ajustar o loop ao idioma do host; usar
`ext.isolated()` em volta dos draws SÓ para hosts amarelos):

- [ ] **Step 1: `examples/pyglet_interop.py`** (se pyglet verde/amarelo)

Janela pyglet, `fo.attach`, um `SpriteBatch` de coelhos com física vetorizada
sobre um `pyglet.text.Label` nativo; loop via `pyglet.clock`/`on_draw` ou
manual (`switch_to`/`dispatch_events`/`flip`); `--frames N` imprime
`pyglet ok: <frames> frames`. Asset `benchmarks/arena/assets/bunny.png` via
`Path(__file__)`.

- [ ] **Step 2: `examples/arcade_interop.py`** (se arcade verde/amarelo)

`arcade.Window` com `on_draw`; desenhar algo nativo do arcade (ex.:
`arcade.draw_text` ou uma shape) e, em seguida, os batches do FastObjects
(dentro de `with ext.isolated():` se amarelo, OU usando `win.ctx` diretamente
se essa foi a rota vencedora do spike); `--frames N` via `arcade.close_window`
após N `on_draw`s.

- [ ] **Step 3: `examples/raylib_interop.py`** (SÓ se raylib não for vermelho)

`while not rl.window_should_close()`, `begin_drawing`/`end_drawing`,
FastObjects entre eles (com `isolated()` se amarelo).

- [ ] **Step 4: Verificar cada exemplo criado (FOREGROUND)**

Run (para cada um criado): `.venv\Scripts\python examples/<host>_interop.py --frames 120`
Expected: janela abre, imprime `<host> ok: 120 frames` sem exceção, e o render
do FastObjects aparece corretamente (verificação a olho na primeira execução
interativa sem `--frames`, se possível).

- [ ] **Step 5: Lint + commit**

Run: `.venv\Scripts\python -m ruff check examples`

```powershell
git add examples
git commit -m "feat: interop examples for supported extra hosts"
```

---

### Task 4: Docs — seção "Other hosts" (EN/PT)

**Files:**
- Modify: `docs/site/guide/interop.md`, `docs/site/guide/interop.pt.md`
- Modify (se Task 2 criou `isolated()`): `docs/site/api.md`, `docs/site/api.pt.md`

**Interfaces:**
- Consumes: vereditos do Task 1, exemplos do Task 3.

- [ ] **Step 1: Seção "Other hosts" na página de interop (EN)**

Adicionar ao final de `docs/site/guide/interop.md`: tabela host × status
(pygame: supported; e pyglet/arcade/raylib conforme o spike), um snippet
mínimo por host suportado, e a nota geral ("`attach` works with any current GL
context; wrap FastObjects draws in `ext.isolated()` for hosts that manage
their own GL state"). Linkar os `examples/<host>_interop.py`.

- [ ] **Step 2: Espelhar em PT** (`docs/site/guide/interop.pt.md`).

- [ ] **Step 3: Documentar `isolated()`** na página de API (EN/PT), SE criado
  no Task 2 (linha na seção `attach`/`ExternalWindow`).

- [ ] **Step 4: Build estrito + commit**

Run: `.venv\Scripts\python -m mkdocs build --strict`
Expected: sem erros/warnings.

```powershell
git add docs/site
git commit -m "docs: other-hosts interop section (pyglet/arcade/raylib status + snippets)"
```

---

### Task 5: Release 0.4.0

- [ ] **Step 1: Bump** 0.3.1 → 0.4.0 (pyproject.toml, fastobjects/__init__.py, tests/test_smoke.py — via Edit, sem BOM); suíte verde; `git commit -m "chore: bump to 0.4.0 - extra host support"`.
- [ ] **Step 2: Merge** em main via superpowers:finishing-a-development-branch (suíte → merge → suíte → delete branch → push).
- [ ] **Step 3: Release** — tag `v0.4.0` + push; pre-release GitHub via REST API (script no scratchpad, token de `git credential fill` — sem gh CLI); notas com a tabela de hosts suportados. Acompanhar `publish.yml` até success e confirmar PyPI 0.4.0; o workflow de docs republica sozinho.

---

## Fora deste plano

Texture atlas (próxima fase); hosts além dos três; qualquer solução que exija fork de host.
