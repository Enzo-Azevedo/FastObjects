# FastObjects Core (Fases 1–3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir a arena de benchmarks (bunnymark vs. pygame-ce/arcade/pyglet/raylib) e o protótipo do core da FastObjects (moderngl + glfw + NumPy, um draw call instanciado) que vence todos os concorrentes.

**Architecture:** Sprites vivem em um array NumPy contíguo (sem objetos Python por sprite); a cada frame há uma atualização vetorizada, um upload de buffer e um único draw call instanciado. A arena mede todos os frameworks com o mesmo protocolo (harness comum com física idêntica e controlador de ramp), e o lab decide empiricamente a estratégia de upload.

**Tech Stack:** Python 3.13, moderngl, glfw, numpy, pillow (core); pygame-ce, arcade, pyglet, raylib (bench); pytest, ruff (dev).

## Global Constraints

- Python: `py -3.13` para o venv (wheels binários dos concorrentes; 3.14t anotado como experimento futuro).
- Dependências do core: **apenas** `numpy`, `moderngl`, `glfw`, `pillow`. Nada de frameworks de jogos no core.
- Benchmarks: janela **1280x720**, **vsync OFF**, seed **42**, física com dt fixo `1/60` (determinística), warmup 30 frames, medição 120 frames.
- Critério de 60 FPS: `avg_ms <= 16.667` e `p99_ms <= 25.0`.
- Todo resultado de benchmark vai para `benchmarks/RESULTS.md` com data e hardware.
- Commits **sem** trailer `Co-Authored-By` (preferência do usuário).
- Cada bench roda em processo próprio (estado de GL/janela isolado).
- Mensagens de erro devem ser acionáveis (ex.: capacity excedida diz o valor necessário).

---

### Task 1: Scaffolding do projeto

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `fastobjects/__init__.py`
- Create: `tests/test_smoke.py`

**Interfaces:**
- Consumes: nada (primeiro task).
- Produces: pacote `fastobjects` importável com `fastobjects.__version__: str`; venv `.venv` com extras `[dev,bench]` instalados; `pytest` funcionando.

- [ ] **Step 1: Criar pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "fastobjects"
version = "0.1.0"
description = "The fastest 2D object rendering library for Python"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
authors = [{ name = "Enzo-Azevedo", email = "enzoteste3.g@gmail.com" }]
dependencies = [
    "numpy>=1.26",
    "moderngl>=5.10",
    "glfw>=2.7",
    "pillow>=10.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.6"]
bench = [
    "pygame-ce>=2.5",
    "arcade>=3.0",
    "raylib>=5.5",
]

[tool.hatch.build.targets.wheel]
packages = ["fastobjects"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Nota: `pyglet` não está listado porque `arcade>=3.0` já o traz como dependência (e fixa a versão compatível).

- [ ] **Step 2: Criar .gitignore**

```gitignore
.venv/
__pycache__/
*.pyc
dist/
build/
*.egg-info/
.pytest_cache/
.ruff_cache/
```

- [ ] **Step 3: Criar o pacote e o teste smoke**

`fastobjects/__init__.py`:

```python
"""FastObjects: the fastest 2D object rendering library for Python."""

__version__ = "0.1.0"
```

`tests/test_smoke.py`:

```python
import fastobjects


def test_version():
    assert fastobjects.__version__ == "0.1.0"
```

- [ ] **Step 4: Criar venv e instalar**

Run (PowerShell, na raiz do projeto):

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e ".[dev,bench]"
```

Expected: instalação sem erros (aviso de resolver é aceitável; erro de wheel não é).

- [ ] **Step 5: Rodar o teste smoke**

Run: `.venv\Scripts\python -m pytest tests/test_smoke.py -v`
Expected: `1 passed`

- [ ] **Step 6: Commit**

```powershell
git add pyproject.toml .gitignore fastobjects/__init__.py tests/test_smoke.py
git commit -m "feat: scaffold fastobjects package with dev/bench extras"
```

---

### Task 2: Pesquisa — RESEARCH.md e CONVENTIONS.md

**Files:**
- Create: `docs/RESEARCH.md`
- Create: `docs/CONVENTIONS.md`

**Interfaces:**
- Consumes: pacotes `arcade` e `pyglet` instalados no venv pelo Task 1 (código-fonte local em `.venv\Lib\site-packages\`).
- Produces: documentos de pesquisa que justificam as decisões técnicas dos Tasks 9–11; convenções de código/docs usadas por todos os tasks seguintes.

Este task é de pesquisa (sem TDD). O deliverable são os dois documentos preenchidos — sem seções vazias.

- [ ] **Step 1: Ler o código dos concorrentes e responder às perguntas**

Ler estes arquivos (instalados localmente):
- `.venv\Lib\site-packages\arcade\sprite_list\sprite_list.py` — como o arcade agrupa sprites na GPU e onde está o custo por sprite (procurar: `_sprite_pos_data`, `write_sprite_buffers_to_gpu`, o que acontece quando `sprite.position` é setado).
- `.venv\Lib\site-packages\pyglet\sprite.py` — como o pyglet atualiza vértices por sprite (procurar: `_update_position`, quantas escritas Python acontecem por sprite por frame).
- Documentação local do moderngl: `.venv\Lib\site-packages\moderngl\__init__.py` (docstrings de `Buffer.write`, `Buffer.orphan`, `Context.vertex_array`) — técnicas de upload disponíveis.

Escrever `docs/RESEARCH.md` com esta estrutura (preencher cada resposta com o que foi observado no código, citando arquivo/função):

```markdown
# Pesquisa: como os concorrentes renderizam (e onde perdem tempo)

**Data:** <data>  |  **Versões:** arcade <ver>, pyglet <ver>, moderngl <ver>

## 1. arcade: onde está o custo por sprite?
<resposta: caminho do dado desde `sprite.position = ...` até a GPU;
quais estruturas Python são tocadas por sprite por frame>

## 2. pyglet: como as posições chegam à GPU?
<resposta: o que `Sprite._update_position` faz; custo por sprite>

## 3. moderngl: técnicas de upload disponíveis
<resposta: Buffer.write, Buffer.orphan, buffers/formatos por instância
em vertex_array ('.../i'), render(instances=N)>

## 4. Conclusão: hipóteses da FastObjects
- H1: estado em array NumPy único (AoS interleaved) + 1 buffer.write + 1 draw
  instanciado elimina o custo por objeto que domina arcade/pyglet.
- H2: a estratégia de upload (write total vs. orphan vs. parcial) importa em
  N alto — decidir no lab (Task 13).
```

- [ ] **Step 2: Escrever docs/CONVENTIONS.md**

Convenções extraídas dos repositórios de referência (FastAPI/rich para docs, arcade para API de jogos):

```markdown
# Convenções da FastObjects

## Código
- Type hints completos em toda a API pública; `from __future__ import annotations`.
- Docstrings estilo Google (Args/Returns/Raises) — legíveis no código e no mkdocs.
- ruff como linter/formatter único (config no pyproject).
- Arquivos focados: um módulo = uma responsabilidade (window, batch, core).

## Documentação (padrão FastAPI/rich)
- README começa com a tabela de benchmarks, depois um exemplo mínimo executável.
- Todo exemplo em docs/ deve rodar copiado-e-colado, sem edição.
- docs/ futura em mkdocs-material (Fase 5).

## Performance
- Nenhum loop Python por sprite em caminho quente — sempre NumPy vetorizado.
- Toda decisão de performance referencia um experimento em benchmarks/RESULTS.md.

## Erros
- Mensagens dizem o que fazer: valores esperados, valor necessário, causa provável.
```

- [ ] **Step 3: Commit**

```powershell
git add docs/RESEARCH.md docs/CONVENTIONS.md
git commit -m "docs: research on competitor internals and project conventions"
```

---

### Task 3: Harness comum da arena (física + timer + ramp)

**Files:**
- Create: `benchmarks/arena/common.py`
- Test: `tests/test_harness.py`

**Interfaces:**
- Consumes: nada do projeto (só numpy).
- Produces (usado por TODOS os benches, Tasks 4–8 e 12):
  - Constantes: `WIDTH=1280`, `HEIGHT=720`, `SEED=42`, `TARGET_MS`, `P99_LIMIT_MS`, `WARMUP_FRAMES=30`, `MEASURE_FRAMES=120`, `DT = 1.0/60.0`
  - `make_bunnies(n: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]` — retorna `(pos, vel)`, ambos `(n, 2) float32`
  - `step_bunnies(pos: np.ndarray, vel: np.ndarray, dt: float) -> None` — física in-place
  - `class FrameTimer` — `.begin()`, `.end()`, `.avg_ms: float`, `.p99_ms: float`
  - `class RampController(start=500, growth=1.5, target_ms=TARGET_MS, p99_limit_ms=P99_LIMIT_MS, max_trials=40)` — `.current: int`, `.best: int`, `.record(avg_ms, p99_ms) -> int | None`
  - `run_ramp(framework: str, trial_fn: Callable[[int], tuple[float, float]]) -> dict` — executa o ramp completo e retorna `{"framework", "sprites_at_60fps", "trials": [...]}`

- [ ] **Step 1: Escrever os testes (falhando)**

`tests/test_harness.py`:

```python
import numpy as np
import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "benchmarks" / "arena"))

from common import (  # noqa: E402
    HEIGHT,
    WIDTH,
    FrameTimer,
    RampController,
    make_bunnies,
    run_ramp,
    step_bunnies,
)


def test_make_bunnies_shapes_and_determinism():
    rng1 = np.random.default_rng(42)
    rng2 = np.random.default_rng(42)
    pos1, vel1 = make_bunnies(100, rng1)
    pos2, vel2 = make_bunnies(100, rng2)
    assert pos1.shape == (100, 2) and vel1.shape == (100, 2)
    assert pos1.dtype == np.float32 and vel1.dtype == np.float32
    np.testing.assert_array_equal(pos1, pos2)
    assert (pos1[:, 0] >= 0).all() and (pos1[:, 0] <= WIDTH).all()


def test_step_bunnies_bounces_off_floor():
    pos = np.array([[100.0, HEIGHT - 0.5]], dtype=np.float32)
    vel = np.array([[0.0, 300.0]], dtype=np.float32)
    step_bunnies(pos, vel, 1.0 / 60.0)
    assert pos[0, 1] == HEIGHT  # preso no chão
    assert vel[0, 1] < 0  # velocidade invertida (quicou)


def test_step_bunnies_bounces_off_walls():
    pos = np.array([[WIDTH - 0.1, 300.0]], dtype=np.float32)
    vel = np.array([[500.0, 0.0]], dtype=np.float32)
    step_bunnies(pos, vel, 1.0 / 60.0)
    assert pos[0, 0] == WIDTH
    assert vel[0, 0] < 0


def test_frame_timer_stats():
    t = FrameTimer()
    for _ in range(10):
        t.begin()
        t.end()
    assert t.avg_ms >= 0.0
    assert t.p99_ms >= t.avg_ms * 0.0  # p99 definido e não-negativo
    assert len(t.samples_ms) == 10


def test_ramp_controller_grows_then_stops():
    r = RampController(start=100, growth=2.0, target_ms=16.7, p99_limit_ms=25.0)
    assert r.current == 100
    assert r.record(10.0, 12.0) == 200  # passou -> cresce
    assert r.record(12.0, 14.0) == 400
    assert r.record(20.0, 30.0) is None  # falhou -> para
    assert r.best == 200


def test_ramp_controller_fails_first_trial():
    r = RampController(start=100, growth=2.0)
    assert r.record(50.0, 60.0) is None
    assert r.best == 0


def test_ramp_controller_respects_max_trials():
    r = RampController(start=1, growth=1.0001, max_trials=3)
    r.record(1.0, 1.0)
    r.record(1.0, 1.0)
    assert r.record(1.0, 1.0) is None  # 3o trial é o último


def test_run_ramp_returns_report():
    calls = []

    def fake_trial(n):
        calls.append(n)
        return (10.0, 12.0) if n <= 1000 else (30.0, 40.0)

    result = run_ramp("fake", fake_trial)
    assert result["framework"] == "fake"
    assert result["sprites_at_60fps"] == calls[-2]  # último que passou
    assert len(result["trials"]) == len(calls)
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_harness.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'common'`

- [ ] **Step 3: Implementar benchmarks/arena/common.py**

```python
"""Harness compartilhado da arena: física, timer e controlador de ramp.

Todos os benches usam exatamente esta física e este protocolo de medição,
para que a única variável entre eles seja a renderização.
"""

from __future__ import annotations

import time
from typing import Callable

import numpy as np

WIDTH = 1280
HEIGHT = 720
SEED = 42
DT = 1.0 / 60.0
TARGET_MS = 1000.0 / 60.0
P99_LIMIT_MS = 25.0
WARMUP_FRAMES = 30
MEASURE_FRAMES = 120
GRAVITY = 980.0


def make_bunnies(n: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Cria n coelhos com posição/velocidade determinísticas (dado o rng)."""
    pos = np.empty((n, 2), dtype=np.float32)
    pos[:, 0] = rng.uniform(0, WIDTH, n)
    pos[:, 1] = rng.uniform(0, HEIGHT / 2, n)
    vel = np.empty((n, 2), dtype=np.float32)
    vel[:, 0] = rng.uniform(-250, 250, n)
    vel[:, 1] = rng.uniform(-100, 100, n)
    return pos, vel


def step_bunnies(pos: np.ndarray, vel: np.ndarray, dt: float) -> None:
    """Um passo de física bunnymark clássica, in-place e vetorizado."""
    vel[:, 1] += GRAVITY * dt
    pos += vel * dt

    out_x = (pos[:, 0] < 0) | (pos[:, 0] > WIDTH)
    vel[out_x, 0] *= -1.0
    np.clip(pos[:, 0], 0, WIDTH, out=pos[:, 0])

    hit_floor = pos[:, 1] > HEIGHT
    vel[hit_floor, 1] *= -0.85
    pos[hit_floor, 1] = HEIGHT

    hit_top = pos[:, 1] < 0
    vel[hit_top, 1] *= -1.0
    pos[hit_top, 1] = 0.0


class FrameTimer:
    """Mede a duração de frames em ms via perf_counter_ns."""

    def __init__(self) -> None:
        self.samples_ms: list[float] = []
        self._t0 = 0

    def begin(self) -> None:
        self._t0 = time.perf_counter_ns()

    def end(self) -> None:
        self.samples_ms.append((time.perf_counter_ns() - self._t0) / 1e6)

    @property
    def avg_ms(self) -> float:
        return float(np.mean(self.samples_ms)) if self.samples_ms else 0.0

    @property
    def p99_ms(self) -> float:
        return float(np.percentile(self.samples_ms, 99)) if self.samples_ms else 0.0


class RampController:
    """Aumenta N até o frame time estourar o alvo; guarda o melhor N aprovado."""

    def __init__(
        self,
        start: int = 500,
        growth: float = 1.5,
        target_ms: float = TARGET_MS,
        p99_limit_ms: float = P99_LIMIT_MS,
        max_trials: int = 40,
    ) -> None:
        self.current = start
        self.growth = growth
        self.target_ms = target_ms
        self.p99_limit_ms = p99_limit_ms
        self.max_trials = max_trials
        self.best = 0
        self._trials = 0

    def record(self, avg_ms: float, p99_ms: float) -> int | None:
        """Registra o resultado do trial em `current`. Retorna o próximo N ou None."""
        self._trials += 1
        passed = avg_ms <= self.target_ms and p99_ms <= self.p99_limit_ms
        if not passed:
            return None
        self.best = self.current
        if self._trials >= self.max_trials:
            return None
        self.current = max(self.current + 1, int(self.current * self.growth))
        return self.current


def run_ramp(framework: str, trial_fn: Callable[[int], tuple[float, float]]) -> dict:
    """Executa o protocolo completo: trial_fn(n) -> (avg_ms, p99_ms) por trial."""
    ramp = RampController()
    trials: list[dict] = []
    n: int | None = ramp.current
    while n is not None:
        avg, p99 = trial_fn(n)
        trials.append({"n": n, "avg_ms": round(avg, 3), "p99_ms": round(p99, 3)})
        n = ramp.record(avg, p99)
    return {"framework": framework, "sprites_at_60fps": ramp.best, "trials": trials}
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv\Scripts\python -m pytest tests/test_harness.py -v`
Expected: `8 passed`

- [ ] **Step 5: Commit**

```powershell
git add benchmarks/arena/common.py tests/test_harness.py
git commit -m "feat: shared benchmark harness (physics, timer, ramp controller)"
```

---

### Task 4: Asset do coelho + bench pygame-ce

**Files:**
- Create: `benchmarks/arena/gen_assets.py`
- Create: `benchmarks/arena/assets/bunny.png` (gerado pelo script, commitado)
- Create: `benchmarks/arena/bench_pygame.py`

**Interfaces:**
- Consumes: `common.py` do Task 3 (`run_ramp`, `make_bunnies`, `step_bunnies`, `FrameTimer`, constantes).
- Produces: `assets/bunny.png` (26x37 RGBA, usado por todos os benches); `bench_pygame.py` executável que imprime uma linha JSON `{"framework": "pygame-ce", "sprites_at_60fps": int, "trials": [...]}` no stdout (última linha).

Benches não têm teste unitário (são scripts de medição com janela); a verificação é executá-los.

- [ ] **Step 1: Escrever gen_assets.py e gerar o asset**

```python
"""Gera o sprite do coelho usado por todos os benchmarks (determinístico)."""

from pathlib import Path

import pygame

OUT = Path(__file__).parent / "assets" / "bunny.png"


def main() -> None:
    pygame.init()
    surf = pygame.Surface((26, 37), pygame.SRCALPHA)
    white = (255, 255, 255, 255)
    pygame.draw.ellipse(surf, white, (3, 12, 20, 24))   # corpo
    pygame.draw.ellipse(surf, white, (6, 0, 6, 16))     # orelha esq
    pygame.draw.ellipse(surf, white, (14, 0, 6, 16))    # orelha dir
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surf, str(OUT))
    print(f"gerado: {OUT}")


if __name__ == "__main__":
    main()
```

Run: `.venv\Scripts\python benchmarks/arena/gen_assets.py`
Expected: `gerado: ...bunny.png` e o arquivo existe.

- [ ] **Step 2: Escrever bench_pygame.py**

Usa o caminho mais rápido documentado do pygame: `Surface.blits` em lote.

```python
"""Bunnymark: pygame-ce (Surface.blits, o caminho mais rápido documentado)."""

import json
from pathlib import Path

import numpy as np
import pygame

from common import (
    DT,
    MEASURE_FRAMES,
    SEED,
    WARMUP_FRAMES,
    WIDTH,
    HEIGHT,
    FrameTimer,
    make_bunnies,
    run_ramp,
    step_bunnies,
)

ASSET = Path(__file__).parent / "assets" / "bunny.png"


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT), vsync=0)
    pygame.display.set_caption("bench: pygame-ce")
    bunny = pygame.image.load(str(ASSET)).convert_alpha()

    def trial(n: int) -> tuple[float, float]:
        rng = np.random.default_rng(SEED)
        pos, vel = make_bunnies(n, rng)
        timer = FrameTimer()
        for frame in range(WARMUP_FRAMES + MEASURE_FRAMES):
            pygame.event.pump()
            if frame >= WARMUP_FRAMES:
                timer.begin()
            step_bunnies(pos, vel, DT)
            screen.fill((30, 30, 30))
            screen.blits([(bunny, p) for p in pos.tolist()], doreturn=False)
            pygame.display.flip()
            if frame >= WARMUP_FRAMES:
                timer.end()
        return timer.avg_ms, timer.p99_ms

    result = run_ramp("pygame-ce", trial)
    pygame.quit()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Executar e verificar**

Run: `.venv\Scripts\python benchmarks/arena/bench_pygame.py`
Expected: janela abre, coelhos quicando em quantidades crescentes, e ao final uma linha JSON no stdout com `"framework": "pygame-ce"` e `sprites_at_60fps > 0`.

- [ ] **Step 4: Commit**

```powershell
git add benchmarks/arena/gen_assets.py benchmarks/arena/assets/bunny.png benchmarks/arena/bench_pygame.py
git commit -m "feat: bunny asset generator and pygame-ce bunnymark"
```

---

### Task 5: Bench arcade

**Files:**
- Create: `benchmarks/arena/bench_arcade.py`

**Interfaces:**
- Consumes: `common.py` (Task 3), `assets/bunny.png` (Task 4).
- Produces: script executável que imprime linha JSON com `"framework": "arcade"`.

- [ ] **Step 1: Escrever bench_arcade.py**

Loop manual (switch_to/dispatch_events/flip) para manter a mesma estrutura de trial dos outros benches. O custo por sprite de setar `.position` é o uso real do arcade — é exatamente o que estamos medindo.

```python
"""Bunnymark: arcade (SpriteList na GPU, posições setadas por sprite)."""

import json
from pathlib import Path

import arcade
import numpy as np

from common import (
    DT,
    MEASURE_FRAMES,
    SEED,
    WARMUP_FRAMES,
    WIDTH,
    HEIGHT,
    FrameTimer,
    make_bunnies,
    run_ramp,
    step_bunnies,
)

ASSET = Path(__file__).parent / "assets" / "bunny.png"


def main() -> None:
    win = arcade.Window(WIDTH, HEIGHT, "bench: arcade", vsync=False)
    tex = arcade.load_texture(str(ASSET))

    def trial(n: int) -> tuple[float, float]:
        rng = np.random.default_rng(SEED)
        pos, vel = make_bunnies(n, rng)
        sprites = arcade.SpriteList(capacity=n)
        for i in range(n):
            s = arcade.Sprite(tex)
            s.position = (float(pos[i, 0]), float(pos[i, 1]))
            sprites.append(s)
        timer = FrameTimer()
        for frame in range(WARMUP_FRAMES + MEASURE_FRAMES):
            win.switch_to()
            win.dispatch_events()
            if frame >= WARMUP_FRAMES:
                timer.begin()
            step_bunnies(pos, vel, DT)
            xs = pos[:, 0].tolist()
            ys = pos[:, 1].tolist()
            for i, s in enumerate(sprites):
                s.position = (xs[i], ys[i])
            win.clear()
            sprites.draw()
            win.flip()
            if frame >= WARMUP_FRAMES:
                timer.end()
        sprites.clear()
        return timer.avg_ms, timer.p99_ms

    result = run_ramp("arcade", trial)
    win.close()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Executar e verificar**

Run: `.venv\Scripts\python benchmarks/arena/bench_arcade.py`
Expected: janela com coelhos, linha JSON final com `"framework": "arcade"` e `sprites_at_60fps > 0`.

- [ ] **Step 3: Commit**

```powershell
git add benchmarks/arena/bench_arcade.py
git commit -m "feat: arcade bunnymark"
```

---

### Task 6: Bench pyglet

**Files:**
- Create: `benchmarks/arena/bench_pyglet.py`

**Interfaces:**
- Consumes: `common.py` (Task 3), `assets/bunny.png` (Task 4).
- Produces: script executável que imprime linha JSON com `"framework": "pyglet"`.

- [ ] **Step 1: Escrever bench_pyglet.py**

```python
"""Bunnymark: pyglet (Batch + Sprite, posições setadas por sprite)."""

import json
from pathlib import Path

import numpy as np
import pyglet

from common import (
    DT,
    MEASURE_FRAMES,
    SEED,
    WARMUP_FRAMES,
    WIDTH,
    HEIGHT,
    FrameTimer,
    make_bunnies,
    run_ramp,
    step_bunnies,
)

ASSET = Path(__file__).parent / "assets" / "bunny.png"


def main() -> None:
    win = pyglet.window.Window(WIDTH, HEIGHT, "bench: pyglet", vsync=False)
    img = pyglet.image.load(str(ASSET))

    def trial(n: int) -> tuple[float, float]:
        rng = np.random.default_rng(SEED)
        pos, vel = make_bunnies(n, rng)
        batch = pyglet.graphics.Batch()
        sprites = [pyglet.sprite.Sprite(img, batch=batch) for _ in range(n)]
        timer = FrameTimer()
        for frame in range(WARMUP_FRAMES + MEASURE_FRAMES):
            win.switch_to()
            win.dispatch_events()
            if frame >= WARMUP_FRAMES:
                timer.begin()
            step_bunnies(pos, vel, DT)
            xs = pos[:, 0].tolist()
            ys = pos[:, 1].tolist()
            for i, s in enumerate(sprites):
                s.position = (xs[i], ys[i], 0)
            win.clear()
            batch.draw()
            win.flip()
            if frame >= WARMUP_FRAMES:
                timer.end()
        for s in sprites:
            s.delete()
        return timer.avg_ms, timer.p99_ms

    result = run_ramp("pyglet", trial)
    win.close()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
```

Nota: o pyglet desenha com y para cima; para benchmark de throughput isso não importa (mesma carga), então não convertemos coordenadas.

- [ ] **Step 2: Executar e verificar**

Run: `.venv\Scripts\python benchmarks/arena/bench_pyglet.py`
Expected: linha JSON final com `"framework": "pyglet"` e `sprites_at_60fps > 0`.

- [ ] **Step 3: Commit**

```powershell
git add benchmarks/arena/bench_pyglet.py
git commit -m "feat: pyglet bunnymark"
```

---

### Task 7: Bench raylib

**Files:**
- Create: `benchmarks/arena/bench_raylib.py`

**Interfaces:**
- Consumes: `common.py` (Task 3), `assets/bunny.png` (Task 4).
- Produces: script executável que imprime linha JSON com `"framework": "raylib"`.

- [ ] **Step 1: Escrever bench_raylib.py**

```python
"""Bunnymark: raylib (pyray, draw_texture por coelho — batching interno em C)."""

import json
from pathlib import Path

import numpy as np
import pyray as rl

from common import (
    DT,
    MEASURE_FRAMES,
    SEED,
    WARMUP_FRAMES,
    WIDTH,
    HEIGHT,
    FrameTimer,
    make_bunnies,
    run_ramp,
    step_bunnies,
)

ASSET = Path(__file__).parent / "assets" / "bunny.png"


def main() -> None:
    rl.set_config_flags(0)  # sem VSYNC_HINT: vsync off
    rl.init_window(WIDTH, HEIGHT, "bench: raylib")
    tex = rl.load_texture(str(ASSET))
    bg = rl.Color(30, 30, 30, 255)
    white = rl.WHITE

    def trial(n: int) -> tuple[float, float]:
        rng = np.random.default_rng(SEED)
        pos, vel = make_bunnies(n, rng)
        timer = FrameTimer()
        for frame in range(WARMUP_FRAMES + MEASURE_FRAMES):
            if frame >= WARMUP_FRAMES:
                timer.begin()
            step_bunnies(pos, vel, DT)
            coords = pos.astype(np.int32).tolist()
            rl.begin_drawing()
            rl.clear_background(bg)
            draw = rl.draw_texture
            for x, y in coords:
                draw(tex, x, y, white)
            rl.end_drawing()
            if frame >= WARMUP_FRAMES:
                timer.end()
        return timer.avg_ms, timer.p99_ms

    result = run_ramp("raylib", trial)
    rl.unload_texture(tex)
    rl.close_window()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Executar e verificar**

Run: `.venv\Scripts\python benchmarks/arena/bench_raylib.py`
Expected: linha JSON final com `"framework": "raylib"` e `sprites_at_60fps > 0`.

- [ ] **Step 3: Commit**

```powershell
git add benchmarks/arena/bench_raylib.py
git commit -m "feat: raylib bunnymark"
```

---

### Task 8: Runner da arena + RESULTS.md baseline

**Files:**
- Create: `benchmarks/arena/run_all.py`
- Create: `benchmarks/RESULTS.md`
- Test: `tests/test_run_all.py`

**Interfaces:**
- Consumes: os scripts `bench_*.py` (Tasks 4–7; o Task 12 adiciona o da fastobjects à lista).
- Produces:
  - `run_all.py` — executa cada bench em subprocesso, coleta o JSON da última linha do stdout, imprime tabela markdown; flag `--save` anexa a tabela em `benchmarks/RESULTS.md` com data e hardware.
  - Funções puras testáveis: `parse_bench_output(stdout: str) -> dict` e `format_table(results: list[dict]) -> str`.

- [ ] **Step 1: Escrever os testes (falhando)**

`tests/test_run_all.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "benchmarks" / "arena"))

from run_all import format_table, parse_bench_output  # noqa: E402


def test_parse_bench_output_takes_last_json_line():
    stdout = "lixo do driver\n{\"framework\": \"x\", \"sprites_at_60fps\": 100, \"trials\": []}\n"
    result = parse_bench_output(stdout)
    assert result["framework"] == "x"
    assert result["sprites_at_60fps"] == 100


def test_format_table_sorted_desc():
    results = [
        {"framework": "a", "sprites_at_60fps": 100, "trials": [{"n": 100, "avg_ms": 10.0, "p99_ms": 11.0}]},
        {"framework": "b", "sprites_at_60fps": 900, "trials": [{"n": 900, "avg_ms": 15.0, "p99_ms": 16.0}]},
    ]
    table = format_table(results)
    lines = table.splitlines()
    assert "| Framework |" in lines[0]
    assert lines[2].startswith("| b |")  # maior primeiro
    assert "900" in lines[2]
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_run_all.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'run_all'`

- [ ] **Step 3: Implementar run_all.py**

```python
"""Executa todos os benches da arena (um subprocesso cada) e gera a tabela."""

from __future__ import annotations

import argparse
import datetime
import json
import platform
import subprocess
import sys
from pathlib import Path

ARENA = Path(__file__).parent
RESULTS_MD = ARENA.parent / "RESULTS.md"

BENCHES = [
    "bench_pygame.py",
    "bench_arcade.py",
    "bench_pyglet.py",
    "bench_raylib.py",
    # "bench_fastobjects.py",  # habilitado no Task 12
]


def parse_bench_output(stdout: str) -> dict:
    """A última linha não-vazia do stdout do bench é o JSON do resultado."""
    lines = [ln for ln in stdout.strip().splitlines() if ln.strip()]
    return json.loads(lines[-1])


def format_table(results: list[dict]) -> str:
    rows = sorted(results, key=lambda r: r["sprites_at_60fps"], reverse=True)
    out = [
        "| Framework | Sprites @ 60fps | avg ms (último trial ok) | p99 ms |",
        "|---|---|---|---|",
    ]
    for r in rows:
        best = next(
            (t for t in reversed(r["trials"]) if t["n"] == r["sprites_at_60fps"]),
            {"avg_ms": "-", "p99_ms": "-"},
        )
        out.append(
            f"| {r['framework']} | {r['sprites_at_60fps']:,} | {best['avg_ms']} | {best['p99_ms']} |"
        )
    return "\n".join(out)


def gpu_name() -> str:
    try:
        import moderngl

        ctx = moderngl.create_standalone_context()
        name = ctx.info["GL_RENDERER"]
        ctx.release()
        return name
    except Exception:
        return "desconhecida"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true", help="anexa em benchmarks/RESULTS.md")
    args = parser.parse_args()

    results = []
    for bench in BENCHES:
        print(f"== rodando {bench} ==", flush=True)
        proc = subprocess.run(
            [sys.executable, str(ARENA / bench)],
            capture_output=True,
            text=True,
            cwd=str(ARENA),
        )
        if proc.returncode != 0:
            print(f"FALHOU ({proc.returncode}):\n{proc.stderr}", file=sys.stderr)
            continue
        results.append(parse_bench_output(proc.stdout))

    table = format_table(results)
    print(table)

    if args.save:
        stamp = datetime.date.today().isoformat()
        header = (
            f"\n## Arena {stamp}\n\n"
            f"- Hardware: {platform.processor()} | GPU: {gpu_name()}\n"
            f"- Python {platform.python_version()} | {platform.system()} {platform.release()}\n\n"
        )
        with open(RESULTS_MD, "a", encoding="utf-8") as f:
            f.write(header + table + "\n")
        print(f"\nsalvo em {RESULTS_MD}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv\Scripts\python -m pytest tests/test_run_all.py -v`
Expected: `2 passed`

- [ ] **Step 5: Criar RESULTS.md e rodar a arena completa**

`benchmarks/RESULTS.md`:

```markdown
# Resultados de benchmarks

Registro histórico de toda medição do projeto. Nenhuma decisão de performance
existe sem uma entrada aqui. Formato: seções datadas, hardware explícito.
```

Run: `.venv\Scripts\python benchmarks/arena/run_all.py --save`
Expected: os 4 benches rodam em sequência (janelas abrem e fecham), tabela impressa e anexada em `benchmarks/RESULTS.md`. **Esta é a régua baseline.**

- [ ] **Step 6: Commit**

```powershell
git add benchmarks/arena/run_all.py benchmarks/RESULTS.md tests/test_run_all.py
git commit -m "feat: arena runner with results table and baseline numbers"
```

---

### Task 9: Window (glfw + moderngl)

**Files:**
- Create: `fastobjects/window.py`
- Modify: `fastobjects/__init__.py`
- Test: `tests/test_window.py`

**Interfaces:**
- Consumes: nada do projeto.
- Produces (usado pelos Tasks 11–12):
  - `class Window(width: int, height: int, title: str = "fastobjects", vsync: bool = False, visible: bool = True)`
  - `.ctx: moderngl.Context` (com BLEND habilitado), `.width: int`, `.height: int`
  - `.should_close: bool` (property), `.poll() -> None`, `.clear(r: float, g: float, b: float) -> None`, `.swap() -> None`, `.close() -> None`
  - Exportado como `fastobjects.Window`.

- [ ] **Step 1: Escrever o teste (falhando)**

`tests/test_window.py`:

```python
import pytest

from fastobjects import Window


@pytest.fixture
def window():
    win = Window(320, 240, "test", visible=False)
    yield win
    win.close()


def test_window_creates_gl_context(window):
    assert window.ctx.version_code >= 330
    assert window.width == 320
    assert window.height == 240


def test_window_frame_cycle(window):
    window.poll()
    window.clear(0.1, 0.1, 0.1)
    window.swap()
    assert not window.should_close
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_window.py -v`
Expected: FAIL com `ImportError: cannot import name 'Window'`

- [ ] **Step 3: Implementar fastobjects/window.py**

```python
"""Janela glfw + contexto moderngl. A camada mais fina possível."""

from __future__ import annotations

import glfw
import moderngl


class Window:
    """Janela nativa com contexto OpenGL 3.3 core.

    Args:
        width: largura em pixels.
        height: altura em pixels.
        title: título da janela.
        vsync: sincronização vertical (OFF por padrão — benchmarks exigem).
        visible: janela visível (False para testes/offscreen).

    Raises:
        RuntimeError: se o glfw ou o contexto OpenGL não puderem ser criados.
    """

    def __init__(
        self,
        width: int,
        height: int,
        title: str = "fastobjects",
        vsync: bool = False,
        visible: bool = True,
    ) -> None:
        if not glfw.init():
            raise RuntimeError(
                "glfw.init() falhou — verifique se há um display/driver de vídeo disponível."
            )
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.VISIBLE, glfw.TRUE if visible else glfw.FALSE)
        self._win = glfw.create_window(width, height, title, None, None)
        if not self._win:
            glfw.terminate()
            raise RuntimeError(
                "Não foi possível criar a janela — driver sem suporte a OpenGL 3.3 core?"
            )
        glfw.make_context_current(self._win)
        glfw.swap_interval(1 if vsync else 0)
        self.ctx = moderngl.create_context()
        self.ctx.enable(moderngl.BLEND)
        self.width = width
        self.height = height

    @property
    def should_close(self) -> bool:
        return bool(glfw.window_should_close(self._win))

    def poll(self) -> None:
        glfw.poll_events()

    def clear(self, r: float, g: float, b: float) -> None:
        self.ctx.clear(r, g, b, 1.0)

    def swap(self) -> None:
        glfw.swap_buffers(self._win)

    def close(self) -> None:
        if self._win is not None:
            glfw.destroy_window(self._win)
            self._win = None
```

Atualizar `fastobjects/__init__.py`:

```python
"""FastObjects: the fastest 2D object rendering library for Python."""

from fastobjects.window import Window

__version__ = "0.1.0"
__all__ = ["Window", "__version__"]
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv\Scripts\python -m pytest tests/test_window.py -v`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```powershell
git add fastobjects/window.py fastobjects/__init__.py tests/test_window.py
git commit -m "feat: glfw window with moderngl context"
```

---

### Task 10: Core renderer (shaders + draw instanciado)

**Files:**
- Create: `fastobjects/core/__init__.py`
- Create: `fastobjects/core/shaders.py`
- Create: `fastobjects/core/renderer.py`
- Test: `tests/test_renderer.py`

**Interfaces:**
- Consumes: nada do projeto (só moderngl/numpy).
- Produces (usado pelo Task 11):
  - `SPRITE_VS: str`, `SPRITE_FS: str` em `shaders.py`
  - `class SpriteRenderer(ctx: moderngl.Context, texture: moderngl.Texture, capacity: int, view_size: tuple[int, int])`
  - `.render(data: np.ndarray, count: int) -> None` — `data` é `(capacity, 9) float32` com colunas `x, y, w, h, rot, r, g, b, a`; coordenadas em pixels com **y para baixo** (origem no canto superior esquerdo)
  - `STRIDE = 36` (9 floats * 4 bytes)

- [ ] **Step 1: Escrever o teste de pixels (falhando)**

`tests/test_renderer.py`:

```python
import moderngl
import numpy as np
import pytest

from fastobjects.core.renderer import SpriteRenderer


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
    return raw[::-1]  # OpenGL lê de baixo para cima; invertemos para y-baixo


def white_texture(ctx) -> moderngl.Texture:
    return ctx.texture((4, 4), 4, data=b"\xff" * (4 * 4 * 4))


def make_sprite_data(x, y, w, h, rot, color) -> np.ndarray:
    data = np.zeros((1, 9), dtype="f4")
    data[0] = [x, y, w, h, rot, *color]
    return data


def test_renders_red_sprite_at_center(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    renderer = SpriteRenderer(ctx, white_texture(ctx), capacity=16, view_size=(64, 64))
    data = make_sprite_data(32, 32, 16, 16, 0.0, (1.0, 0.0, 0.0, 1.0))
    renderer.render(data, 1)
    px = read_pixels(fbo)
    center = px[32, 32]
    assert center[0] > 200 and center[1] < 50 and center[2] < 50  # vermelho
    corner = px[2, 2]
    assert corner[0] < 10 and corner[1] < 10  # fundo intacto


def test_render_zero_count_is_noop(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    renderer = SpriteRenderer(ctx, white_texture(ctx), capacity=16, view_size=(64, 64))
    renderer.render(np.zeros((16, 9), dtype="f4"), 0)
    px = read_pixels(fbo)
    assert px[:, :, 0].max() < 10  # nada desenhado


def test_sprite_y_axis_points_down(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    renderer = SpriteRenderer(ctx, white_texture(ctx), capacity=16, view_size=(64, 64))
    data = make_sprite_data(32, 8, 10, 10, 0.0, (0.0, 1.0, 0.0, 1.0))  # y=8: perto do TOPO
    renderer.render(data, 1)
    px = read_pixels(fbo)
    assert px[8, 32][1] > 200   # verde no topo
    assert px[56, 32][1] < 10   # nada embaixo
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_renderer.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'fastobjects.core'`

- [ ] **Step 3: Implementar shaders.py**

`fastobjects/core/__init__.py` (vazio):

```python
```

`fastobjects/core/shaders.py`:

```python
"""Shaders GLSL. O quad vem de gl_VertexID — nenhum vertex buffer de geometria."""

SPRITE_VS = """
#version 330
uniform vec2 u_view;  // (2/width, -2/height): pixels -> NDC com y para baixo

in vec2 in_pos;    // centro do sprite, em pixels (por instância)
in vec2 in_size;   // largura/altura em pixels (por instância)
in float in_rot;   // radianos (por instância)
in vec4 in_color;  // multiplicador RGBA (por instância)

out vec4 v_color;
out vec2 v_uv;

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
}
"""

SPRITE_FS = """
#version 330
uniform sampler2D u_tex;

in vec4 v_color;
in vec2 v_uv;
out vec4 f_color;

void main() {
    f_color = texture(u_tex, v_uv) * v_color;
}
"""
```

- [ ] **Step 4: Implementar renderer.py**

```python
"""Renderer instanciado: um buffer de instâncias, um draw call por lote."""

from __future__ import annotations

import moderngl
import numpy as np

from fastobjects.core.shaders import SPRITE_FS, SPRITE_VS

FLOATS_PER_SPRITE = 9  # x, y, w, h, rot, r, g, b, a
STRIDE = FLOATS_PER_SPRITE * 4


class SpriteRenderer:
    """Desenha até `capacity` sprites com um único draw call instanciado.

    Args:
        ctx: contexto moderngl ativo.
        texture: textura compartilhada por todos os sprites do lote.
        capacity: número máximo de instâncias.
        view_size: (largura, altura) do alvo de render, em pixels.
    """

    def __init__(
        self,
        ctx: moderngl.Context,
        texture: moderngl.Texture,
        capacity: int,
        view_size: tuple[int, int],
    ) -> None:
        self.ctx = ctx
        self.texture = texture
        self.capacity = capacity
        self.prog = ctx.program(vertex_shader=SPRITE_VS, fragment_shader=SPRITE_FS)
        self.prog["u_view"].value = (2.0 / view_size[0], -2.0 / view_size[1])
        self.buffer = ctx.buffer(reserve=capacity * STRIDE)
        self.vao = ctx.vertex_array(
            self.prog,
            [(self.buffer, "2f 2f 1f 4f/i", "in_pos", "in_size", "in_rot", "in_color")],
        )

    def render(self, data: np.ndarray, count: int) -> None:
        """Sobe `data[:count]` e desenha `count` instâncias.

        Estratégia de upload: write total do trecho usado (hipótese H1 do
        RESEARCH.md; alternativas medidas no lab — ver benchmarks/RESULTS.md).
        """
        if count == 0:
            return
        self.texture.use(0)
        self.buffer.write(data[:count])
        self.vao.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=count)
```

- [ ] **Step 5: Rodar os testes**

Run: `.venv\Scripts\python -m pytest tests/test_renderer.py -v`
Expected: `3 passed`

- [ ] **Step 6: Commit**

```powershell
git add fastobjects/core/__init__.py fastobjects/core/shaders.py fastobjects/core/renderer.py tests/test_renderer.py
git commit -m "feat: instanced sprite renderer with pixel-verified shaders"
```

---

### Task 11: SpriteBatch (estado SoA-view sobre array contíguo)

**Files:**
- Create: `fastobjects/batch.py`
- Create: `fastobjects/errors.py`
- Modify: `fastobjects/__init__.py`
- Test: `tests/test_batch.py`

**Interfaces:**
- Consumes: `SpriteRenderer` (Task 10).
- Produces (usado pelo Task 12):
  - `class CapacityError(Exception)` em `errors.py`
  - `class SpriteBatch(ctx, texture_path: str, capacity: int, view_size: tuple[int, int])`
  - `.data: np.ndarray (capacity, 9) float32` | views: `.pos (capacity, 2)`, `.size (capacity, 2)`, `.rot (capacity,)`, `.color (capacity, 4)`
  - `.count: int`, `.spawn(n, x=0.0, y=0.0, w=None, h=None, rot=0.0, color=(1,1,1,1)) -> slice` (aceita escalares ou arrays; `w/h None` usa o tamanho da textura)
  - `.clear() -> None`, `.draw() -> None`
  - Exportado como `fastobjects.SpriteBatch`.

- [ ] **Step 1: Escrever os testes (falhando)**

`tests/test_batch.py`:

```python
import moderngl
import numpy as np
import pytest

from fastobjects.batch import SpriteBatch
from fastobjects.errors import CapacityError

BUNNY = "benchmarks/arena/assets/bunny.png"


@pytest.fixture(scope="module")
def gl():
    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.BLEND)
    fbo = ctx.framebuffer(color_attachments=[ctx.texture((64, 64), 4)])
    fbo.use()
    yield ctx, fbo
    ctx.release()


def test_spawn_scalar_fills_rows(gl):
    ctx, _ = gl
    batch = SpriteBatch(ctx, BUNNY, capacity=100, view_size=(64, 64))
    s = batch.spawn(10, x=5.0, y=7.0)
    assert batch.count == 10
    assert s == slice(0, 10)
    np.testing.assert_allclose(batch.pos[s][:, 0], 5.0)
    np.testing.assert_allclose(batch.pos[s][:, 1], 7.0)
    assert batch.size[0, 0] == 26.0  # largura da textura bunny.png
    assert batch.size[0, 1] == 37.0


def test_spawn_vectorized(gl):
    ctx, _ = gl
    batch = SpriteBatch(ctx, BUNNY, capacity=100, view_size=(64, 64))
    xs = np.arange(20, dtype=np.float32)
    batch.spawn(20, x=xs, y=0.0)
    np.testing.assert_array_equal(batch.pos[:20, 0], xs)


def test_spawn_appends_after_existing(gl):
    ctx, _ = gl
    batch = SpriteBatch(ctx, BUNNY, capacity=100, view_size=(64, 64))
    batch.spawn(10)
    s2 = batch.spawn(5, x=99.0)
    assert s2 == slice(10, 15)
    assert batch.count == 15


def test_spawn_over_capacity_raises_actionable_error(gl):
    ctx, _ = gl
    batch = SpriteBatch(ctx, BUNNY, capacity=10, view_size=(64, 64))
    batch.spawn(8)
    with pytest.raises(CapacityError, match="capacity=13"):
        batch.spawn(5)


def test_clear_resets_count(gl):
    ctx, _ = gl
    batch = SpriteBatch(ctx, BUNNY, capacity=10, view_size=(64, 64))
    batch.spawn(10)
    batch.clear()
    assert batch.count == 0
    batch.spawn(10)  # não deve levantar


def test_views_write_through_to_data(gl):
    ctx, _ = gl
    batch = SpriteBatch(ctx, BUNNY, capacity=10, view_size=(64, 64))
    batch.spawn(3)
    batch.pos[:3, 1] += 100.0
    assert batch.data[0, 1] == 100.0  # view escreve no array base


def test_draw_renders_pixels(gl):
    ctx, fbo = gl
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    batch = SpriteBatch(ctx, BUNNY, capacity=10, view_size=(64, 64))
    batch.spawn(1, x=32.0, y=32.0)
    batch.draw()
    raw = np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(64, 64, 4)
    assert raw[:, :, 0].max() > 200  # o coelho branco apareceu
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_batch.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'fastobjects.batch'`

- [ ] **Step 3: Implementar errors.py e batch.py**

`fastobjects/errors.py`:

```python
"""Exceções da FastObjects — sempre com mensagens acionáveis."""


class CapacityError(Exception):
    """Levantada quando um spawn excede a capacidade do batch."""
```

`fastobjects/batch.py`:

```python
"""SpriteBatch: sprites como linhas de um array NumPy, nunca objetos Python."""

from __future__ import annotations

import moderngl
import numpy as np
from PIL import Image

from fastobjects.core.renderer import FLOATS_PER_SPRITE, SpriteRenderer
from fastobjects.errors import CapacityError


class SpriteBatch:
    """Lote de sprites com a mesma textura, desenhado em um draw call.

    O estado vive em `data` (capacity, 9): x, y, w, h, rot, r, g, b, a.
    As views `pos`, `size`, `rot`, `color` escrevem direto em `data`.

    Args:
        ctx: contexto moderngl ativo.
        texture_path: caminho de uma imagem (qualquer formato PIL).
        capacity: número máximo de sprites do lote.
        view_size: (largura, altura) do alvo de render em pixels.
    """

    def __init__(
        self,
        ctx: moderngl.Context,
        texture_path: str,
        capacity: int,
        view_size: tuple[int, int],
    ) -> None:
        img = Image.open(texture_path).convert("RGBA")
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

    def spawn(
        self,
        n: int,
        x: float | np.ndarray = 0.0,
        y: float | np.ndarray = 0.0,
        w: float | np.ndarray | None = None,
        h: float | np.ndarray | None = None,
        rot: float | np.ndarray = 0.0,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    ) -> slice:
        """Adiciona n sprites. Aceita escalares ou arrays de tamanho n.

        Returns:
            O slice das linhas recém-criadas em `data`/views.

        Raises:
            CapacityError: se n não couber; a mensagem diz a capacity necessária.
        """
        if self.count + n > self.capacity:
            raise CapacityError(
                f"spawn({n}) excede a capacidade: {self.count} usados de "
                f"{self.capacity}. Crie o batch com capacity={self.count + n} ou mais."
            )
        s = slice(self.count, self.count + n)
        self.pos[s, 0] = x
        self.pos[s, 1] = y
        self.size[s, 0] = self.texture_size[0] if w is None else w
        self.size[s, 1] = self.texture_size[1] if h is None else h
        self.rot[s] = rot
        self.color[s] = color
        self.count += n
        return s

    def clear(self) -> None:
        """Remove todos os sprites (O(1): só reseta o contador)."""
        self.count = 0

    def draw(self) -> None:
        """Sobe o estado atual e desenha o lote inteiro em um draw call."""
        self._renderer.render(self.data, self.count)
```

Atualizar `fastobjects/__init__.py`:

```python
"""FastObjects: the fastest 2D object rendering library for Python."""

from fastobjects.batch import SpriteBatch
from fastobjects.errors import CapacityError
from fastobjects.window import Window

__version__ = "0.1.0"
__all__ = ["CapacityError", "SpriteBatch", "Window", "__version__"]
```

- [ ] **Step 4: Rodar TODOS os testes**

Run: `.venv\Scripts\python -m pytest -v`
Expected: todos passam (smoke + harness + run_all + window + renderer + batch).

- [ ] **Step 5: Commit**

```powershell
git add fastobjects/batch.py fastobjects/errors.py fastobjects/__init__.py tests/test_batch.py
git commit -m "feat: SpriteBatch with NumPy state and actionable capacity errors"
```

---

### Task 12: Bench fastobjects + arena completa

**Files:**
- Create: `benchmarks/arena/bench_fastobjects.py`
- Modify: `benchmarks/arena/run_all.py` (habilitar o bench na lista `BENCHES`)

**Interfaces:**
- Consumes: `Window`, `SpriteBatch` (Tasks 9 e 11), `common.py` (Task 3), `assets/bunny.png` (Task 4).
- Produces: linha JSON com `"framework": "fastobjects"`; tabela da arena atualizada em `RESULTS.md` — **o critério de sucesso do plano é fastobjects em 1º lugar**.

- [ ] **Step 1: Escrever bench_fastobjects.py**

A física opera **diretamente nas views do batch** — zero cópias por frame.

```python
"""Bunnymark: fastobjects (estado NumPy, 1 upload, 1 draw call instanciado)."""

import json
from pathlib import Path

import numpy as np

from common import (
    DT,
    MEASURE_FRAMES,
    SEED,
    WARMUP_FRAMES,
    WIDTH,
    HEIGHT,
    FrameTimer,
    make_bunnies,
    run_ramp,
    step_bunnies,
)
from fastobjects import SpriteBatch, Window

ASSET = Path(__file__).parent / "assets" / "bunny.png"
MAX_CAPACITY = 2_000_000


def main() -> None:
    win = Window(WIDTH, HEIGHT, "bench: fastobjects", vsync=False)
    batch = SpriteBatch(win.ctx, str(ASSET), capacity=MAX_CAPACITY, view_size=(WIDTH, HEIGHT))

    def trial(n: int) -> tuple[float, float]:
        rng = np.random.default_rng(SEED)
        pos, vel = make_bunnies(n, rng)
        batch.clear()
        batch.spawn(n, x=pos[:, 0], y=pos[:, 1])
        live_pos = batch.pos[:n]
        timer = FrameTimer()
        for frame in range(WARMUP_FRAMES + MEASURE_FRAMES):
            win.poll()
            if frame >= WARMUP_FRAMES:
                timer.begin()
            step_bunnies(live_pos, vel, DT)
            win.clear(0.12, 0.12, 0.12)
            batch.draw()
            win.swap()
            if frame >= WARMUP_FRAMES:
                timer.end()
        return timer.avg_ms, timer.p99_ms

    result = run_ramp("fastobjects", trial)
    win.close()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Habilitar na lista do runner**

Em `benchmarks/arena/run_all.py`, trocar:

```python
    # "bench_fastobjects.py",  # habilitado no Task 12
```

por:

```python
    "bench_fastobjects.py",
```

- [ ] **Step 3: Rodar o bench isolado**

Run: `.venv\Scripts\python benchmarks/arena/bench_fastobjects.py`
Expected: linha JSON com `sprites_at_60fps` **maior que o melhor concorrente do baseline** (Task 8). Se não for, investigar com o systematic-debugging skill ANTES de prosseguir — o lab (Task 13) é para otimizar um vencedor, não consertar um perdedor.

- [ ] **Step 4: Rodar a arena completa e salvar**

Run: `.venv\Scripts\python benchmarks/arena/run_all.py --save`
Expected: tabela com 5 frameworks, fastobjects em 1º, anexada em `RESULTS.md`.

- [ ] **Step 5: Commit**

```powershell
git add benchmarks/arena/bench_fastobjects.py benchmarks/arena/run_all.py benchmarks/RESULTS.md
git commit -m "feat: fastobjects bunnymark - first place in arena"
```

---

### Task 13: Lab — experimento de estratégias de upload

**Files:**
- Create: `benchmarks/lab/exp_buffer_upload.py`
- Modify: `fastobjects/core/renderer.py` (SE um vencedor diferente emergir)
- Modify: `benchmarks/RESULTS.md`

**Interfaces:**
- Consumes: `SpriteRenderer` (Task 10).
- Produces: decisão registrada em `RESULTS.md`; renderer usando a estratégia vencedora.

- [ ] **Step 1: Escrever exp_buffer_upload.py**

```python
"""Lab: qual estratégia de upload de buffer é mais rápida em N alto?

Estratégias:
  A) write total do trecho usado (implementação atual)
  B) orphan() antes do write (evita stall de sincronização GPU)
  C) write duplo-buffer (alterna entre 2 buffers, um por frame)

Contexto standalone + FBO: mede só upload+draw, sem ruído de janela/vsync.
"""

from __future__ import annotations

import time

import moderngl
import numpy as np

N = 200_000
FRAMES = 300
SIZE = (1280, 720)
FLOATS = 9
STRIDE = FLOATS * 4


def make_gl():
    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.BLEND)
    fbo = ctx.framebuffer(color_attachments=[ctx.texture(SIZE, 4)])
    fbo.use()
    return ctx, fbo


def build(ctx, n):
    from fastobjects.core.renderer import SpriteRenderer

    tex = ctx.texture((4, 4), 4, data=b"\xff" * 64)
    renderer = SpriteRenderer(ctx, tex, capacity=n, view_size=SIZE)
    rng = np.random.default_rng(42)
    data = np.zeros((n, FLOATS), dtype="f4")
    data[:, 0] = rng.uniform(0, SIZE[0], n)
    data[:, 1] = rng.uniform(0, SIZE[1], n)
    data[:, 2:4] = 26.0
    data[:, 5:9] = 1.0
    return renderer, data


def measure(name, frame_fn):
    t0 = time.perf_counter_ns()
    for _ in range(FRAMES):
        frame_fn()
    ms = (time.perf_counter_ns() - t0) / 1e6 / FRAMES
    print(f"{name}: {ms:.3f} ms/frame")
    return ms


def main() -> None:
    ctx, fbo = make_gl()
    renderer, data = build(ctx, N)

    def strategy_a():
        data[:, 0] += 0.01  # simula atualização
        renderer.buffer.write(data)
        renderer.texture.use(0)
        renderer.vao.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=N)
        ctx.finish()

    def strategy_b():
        data[:, 0] += 0.01
        renderer.buffer.orphan()
        renderer.buffer.write(data)
        renderer.texture.use(0)
        renderer.vao.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=N)
        ctx.finish()

    # C: double-buffer
    buf2 = ctx.buffer(reserve=N * STRIDE)
    vao2 = ctx.vertex_array(
        renderer.prog,
        [(buf2, "2f 2f 1f 4f/i", "in_pos", "in_size", "in_rot", "in_color")],
    )
    flip = {"i": 0}

    def strategy_c():
        data[:, 0] += 0.01
        flip["i"] ^= 1
        buf, vao = (renderer.buffer, renderer.vao) if flip["i"] else (buf2, vao2)
        buf.write(data)
        renderer.texture.use(0)
        vao.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=N)
        ctx.finish()

    print(f"N={N}, {FRAMES} frames, GPU={ctx.info['GL_RENDERER']}")
    results = {
        "A write": measure("A write total", strategy_a),
        "B orphan+write": measure("B orphan+write", strategy_b),
        "C double-buffer": measure("C double-buffer", strategy_c),
    }
    winner = min(results, key=results.get)
    print(f"vencedora: {winner}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Executar o experimento**

Run: `.venv\Scripts\python benchmarks/lab/exp_buffer_upload.py`
Expected: três tempos em ms/frame e a estratégia vencedora impressa.

- [ ] **Step 3: Registrar em RESULTS.md**

Anexar em `benchmarks/RESULTS.md` (preencher com os números reais):

```markdown
## Lab <data>: estratégia de upload de buffer

- Hardware/GPU: <do output do experimento>
- N=200.000, 300 frames, contexto standalone (sem janela/vsync)

| Estratégia | ms/frame |
|---|---|
| A write total | <x> |
| B orphan+write | <x> |
| C double-buffer | <x> |

**Decisão:** <estratégia> adotada no SpriteRenderer.render (ou mantida a A,
se vencedora). Perdedoras documentadas acima — não retestar sem mudança de
hardware ou de driver.
```

- [ ] **Step 4: Adotar a vencedora (se não for a A)**

SE a estratégia B vencer, alterar `SpriteRenderer.render` em `fastobjects/core/renderer.py`:

```python
    def render(self, data: np.ndarray, count: int) -> None:
        """Sobe `data[:count]` e desenha `count` instâncias.

        Estratégia de upload: orphan+write (vencedora do lab — ver
        benchmarks/RESULTS.md, experimento de upload de buffer).
        """
        if count == 0:
            return
        self.texture.use(0)
        self.buffer.orphan()
        self.buffer.write(data[:count])
        self.vao.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=count)
```

SE a C vencer, implementar double-buffer no renderer (dois buffers + dois VAOs, alternando por chamada, mesma interface pública). Em qualquer mudança: rodar `.venv\Scripts\python -m pytest -v` (todos os testes de pixel continuam passando) e rodar a arena de novo (`run_all.py --save`) para confirmar o ganho de ponta a ponta.

- [ ] **Step 5: Rodar todos os testes**

Run: `.venv\Scripts\python -m pytest -v`
Expected: todos passam.

- [ ] **Step 6: Commit**

```powershell
git add benchmarks/lab/exp_buffer_upload.py benchmarks/RESULTS.md fastobjects/core/renderer.py
git commit -m "perf: buffer upload strategy decided by lab experiment"
```

---

## Fora deste plano (planos futuros)

- **Fase 4:** API pública ergonômica (`fo.Window` com decorator `@win.frame`, handles de sprites, `ShapeBatch` de primitivas) — plano próprio sobre o core validado.
- **Fase 5:** mkdocs-material, README com a tabela da arena, empacotamento PyPI.
- **Lab futuro:** Python 3.14 free-threaded (3.14t está instalado nesta máquina), layout SoA vs. AoS, float16 nos atributos, núcleo Rust.
