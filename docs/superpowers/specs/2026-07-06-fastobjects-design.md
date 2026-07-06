# FastObjects — Design Spec

**Data:** 2026-07-06
**Status:** Aprovado pelo usuário

## Objetivo

Biblioteca Python de renderização 2D (primitivas e sprites) em janela interativa em tempo real, com o objetivo declarado de ser **a mais rápida do ecossistema Python**.

**Critério de sucesso mensurável:** vencer pygame-ce, arcade, pyglet e raylib-python no bunnymark (número máximo de sprites em movimento mantendo 60 FPS) no mesmo hardware, com resultados reproduzíveis versionados no repositório.

## Filosofia de projeto

**Nenhuma decisão técnica é tomada por opinião — tudo é decidido por benchmark.** Qualquer técnica candidata (estratégia de upload de buffer, layout de dados, backend alternativo, futuro núcleo Rust) só entra na implementação se vencer nos números, medidos por experimentos reproduzíveis. Os resultados — vencedores e perdedores — ficam documentados com data e hardware.

## Insight central

Nas bibliotecas Python existentes, o gargalo não é o desenho — é o **overhead de Python por objeto** (um objeto Python por sprite, uma chamada de método por desenho). A FastObjects elimina esse custo: sprites não são objetos Python, são linhas em arrays NumPy contíguos (structure-of-arrays). Por frame: atualização vetorizada → um upload de buffer → **um único draw call instanciado** para o lote inteiro.

## Arquitetura em camadas

```
┌─────────────────────────────────────────┐
│  API pública (fastobjects)              │  ergonômica, estilo moderno
├─────────────────────────────────────────┤
│  Scene/Batch: estado em arrays NumPy    │  zero objetos Python por sprite
│  (structure-of-arrays: pos, rot, cor…)  │
├─────────────────────────────────────────┤
│  Core renderer (moderngl)               │  1 draw call instanciado p/ lote
│  ← fronteira substituível (Rust futuro) │
├─────────────────────────────────────────┤
│  Janela/input (glfw)                    │  leve, sem overhead de framework
└─────────────────────────────────────────┘
```

### Componentes

- **Janela/input (glfw):** criação de janela, loop de frames, eventos de teclado/mouse. Escolhido por ser o binding mais fino disponível (sem framework por cima).
- **Core renderer (moderngl):** compilação de shaders, gestão de VBOs/texturas, execução de draw calls instanciados. Expõe uma **interface estreita** (upload de arrays + draw) para que um backend Rust/wgpu possa substituí-lo no futuro sem tocar nas camadas superiores.
- **Scene/Batch:** dono do estado. `SpriteBatch` e `ShapeBatch` mantêm arrays NumPy contíguos com os atributos por instância (posição, rotação, escala, cor, frame de textura). Handles públicos escrevem direto nos arrays via índice.
- **API pública:** camada ergonômica; `sprite.x = 10` é açúcar sobre escrita no array. Operações em massa são vetorizadas por padrão.

### Fluxo de dados por frame

1. Código do usuário atualiza arrays (vetorizado ou via handles).
2. Batch marca regiões sujas e faz upload para a GPU (estratégia exata decidida no lab: write total vs. parcial vs. buffer persistente vs. orphaning).
3. Core executa um draw call instanciado por batch.
4. Swap de buffers via glfw.

## Laboratório de benchmarks

Diretório `benchmarks/` com duas partes:

- **`benchmarks/arena/`** — bunnymark idêntico implementado em fastobjects, pygame-ce, arcade, pyglet e raylib-python. Um runner executa todos e gera tabela comparativa (sprites @ 60fps, frame time médio e p99).
- **`benchmarks/lab/`** — experimentos A/B internos: redraw total vs. atualização parcial, `buffer.write` vs. buffers persistentes/orphaning, 1 VBO vs. double-buffering, geometria no shader vs. instancing, float32 vs. float16 nos atributos, etc. Cada experimento é um script autocontido que imprime números.
- **`benchmarks/RESULTS.md`** — registro histórico: cada experimento com data, hardware, números e decisão tomada. É o "por que fazemos assim" da biblioteca.

## API pública (esboço)

```python
import fastobjects as fo

win = fo.Window(1280, 720, "demo")
batch = fo.SpriteBatch("bunny.png", capacity=200_000)
bunnies = batch.spawn(100_000, x=..., y=...)   # vetorizado

@win.frame
def update(dt):
    bunnies.y += velocity * dt   # opera direto nos arrays NumPy
    win.draw(batch)

win.run()
```

- **Primitivas 2D** (retângulo, círculo, linha, polígono): mesmo modelo via `ShapeBatch`, com geometria gerada no shader — sem tesselação em Python.
- **Ergonomia:** inspirada no arcade (clareza de API de jogos); documentação no estilo FastAPI/rich.

## Estrutura do projeto

```
fastobjects/          # pacote (core/, window/, batch/, api de topo)
benchmarks/           # arena/ + lab/ + RESULTS.md
tests/                # pytest; contexto OpenGL offscreen (sem janela)
examples/             # exemplos curtos e executáveis (estilo rich)
docs/                 # mkdocs-material (padrão FastAPI/pydantic)
pyproject.toml        # hatchling, ruff, type hints completos
README.md             # tabela de benchmark no topo
```

## Tratamento de erros

Mensagens claras e acionáveis no estilo rich/FastAPI. Exemplos: exceder `capacity` de um batch sugere o valor necessário; contexto OpenGL indisponível explica requisitos de driver; textura não encontrada mostra o caminho resolvido.

## Testes

- **pytest** com contexto OpenGL offscreen (moderngl standalone) — roda sem janela, inclusive em CI.
- Corretude de render por comparação de pixels (render para FBO → leitura → comparação com referência).
- Testes de API (handles, spawn vetorizado, limites de capacity).
- Benchmarks ficam fora da suíte de testes (são executados explicitamente).

## Fases de execução

1. **Pesquisa** — estudar os repositórios de referência: técnicas de renderização de arcade/pyglet/moderngl e estilo de documentação/organização de FastAPI/rich/pydantic. Registrar as convenções adotadas em `docs/CONVENTIONS.md`.
2. **Arena primeiro** — implementar o bunnymark nos 4 concorrentes e o runner comparativo. Estabelece a régua antes de existir código nosso.
3. **Protótipo core** — moderngl + glfw + instancing; entrar na arena e iterar no lab até vencer com folga.
4. **API + primitivas** — camada pública ergonômica sobre o core validado, com testes offscreen.
5. **Docs + exemplos + release** — mkdocs, README com tabela de benchmarks, empacotamento para PyPI.

## Fora de escopo (v1)

- Malhas 3D, iluminação, câmera 3D (a arquitetura não deve impedi-los no futuro).
- Renderização de texto (v2 provável).
- Áudio, física, colisão — FastObjects é renderização, não game engine.
- Núcleo Rust — só entra se/quando um experimento do lab provar ganho relevante.

## Decisões em aberto (a resolver por benchmark, não por discussão)

- Estratégia de upload de buffer (write total / parcial / persistente / orphaning).
- Layout dos atributos por instância (AoS interleaved vs. SoA em VBOs separados).
- Precisão dos atributos (float32 vs. float16 vs. normalized int).
