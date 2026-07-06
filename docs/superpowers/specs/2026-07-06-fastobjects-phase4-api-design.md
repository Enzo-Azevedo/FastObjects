# FastObjects Fase 4 — API pública ergonômica: Design Spec

**Data:** 2026-07-06
**Status:** Aprovado pelo usuário
**Base:** core validado das Fases 1–3 (arena vencida: 218.809 sprites @ 60fps, ~38x o melhor concorrente — ver `benchmarks/RESULTS.md`)

## Objetivo

Camada pública ergonômica sobre o core validado, realizando o esboço de API do spec
original (`docs/superpowers/specs/2026-07-06-fastobjects-design.md`):

```python
import fastobjects as fo

win = fo.Window(1280, 720, "demo")
batch = fo.SpriteBatch("bunny.png", capacity=200_000)
bunnies = batch.spawn(100_000, x=xs, y=ys)   # vetorizado

@win.frame
def update(dt):
    bunnies.y += velocity * dt   # opera direto nos arrays NumPy
    win.clear(0.1, 0.1, 0.1)
    win.draw(batch)

win.run()
```

**Critério de aceite da fase:** este exemplo roda copiado-e-colado (com `xs`, `ys`,
`velocity` definidos), e a arena re-executada não mostra regressão.

## Escopo

1. **Frame loop** — `@win.frame`, `win.run()`, `win.draw(*batches)`.
2. **SpriteGroup** — `spawn()` retorna grupo vetorizado (views NumPy), não slice.
3. **ShapeBatch** — retângulo, círculo e linha, geometria/forma resolvida no shader.
4. **Input por polling** — `win.keys[...]` e `win.mouse`.
5. **Janela implícita** — batches criados sem `ctx` usam a janela atual.

**Fora de escopo (Fase 5+):** docs mkdocs, `examples/`, README novo, PyPI,
polígonos, callbacks de input, renderização de texto, handles individuais de sprite.

## Decisões de design (com alternativas rejeitadas)

- **Handles: só grupo vetorizado.** `spawn()` retorna `SpriteGroup`; não existe
  handle individual na v1 (quem quer um sprite faz `spawn(1)`). Handle por sprite
  reintroduziria o custo por objeto que é a razão de existir da lib.
- **Primitivas: retângulo + círculo + linha.** Polígono rejeitado na v1 (regular é
  nicho; arbitrário exige tesselação em Python — contra a filosofia).
- **Input: polling puro.** Callbacks rejeitados na v1 (dobram superfície de API);
  eventos discretos ficam para v2 se surgir demanda.
- **Contexto: janela implícita com escape explícito.** Criar `Window` a registra
  como atual; parâmetros `ctx`/`view_size` explícitos continuam existindo (caminho
  dos testes offscreen). Wrapper separado (`api/`) rejeitado: duas classes por
  conceito e indireção em caminho quente.
- **Arquitetura: evoluir as classes existentes.** Sem camada de wrapper; a classe
  que o usuário vê é a que roda. Quebras de assinatura são aceitáveis pré-1.0.

## Componentes

### 1. Frame loop — `fastobjects/window.py` (evolui)

- `win.frame(fn)` — decorator; registra `fn(dt: float)` como update da janela.
  Registrar de novo substitui. `run()` sem função registrada → erro acionável.
- `win.run()` — loop: `poll()` → `dt` real medido com `time.perf_counter()` →
  `update(dt)` → `swap()`, até `should_close`. `dt` cru, sem clamp (YAGNI).
- `win.draw(*batches)` — açúcar: chama `batch.draw()` de cada um, na ordem.
- A API de baixo nível (`poll/clear/swap/should_close`) continua pública — os
  benches da arena seguem usando o loop manual (é o protocolo de medição).

### 2. SpriteGroup — `fastobjects/group.py` (novo)

- `SpriteBatch.spawn(...)` passa a retornar `SpriteGroup` (**quebra**: retornava
  `slice`; testes e consumidores ajustados no plano da fase).
- Estado: `(batch, slice)`. Um objeto por **grupo**, nunca por sprite.
- Propriedades como views NumPy do array base: `x`, `y`, `w`, `h`, `rot`,
  `pos` (n,2), `size` (n,2), `color` (n,4). Leitura devolve a view (portanto
  `group.y += v` escreve in-place, zero cópia); atribuição (`group.x = valor`)
  escreve no array com broadcast.
- `group[a:b]` devolve sub-`SpriteGroup` (slice relativo ao grupo);
  `len(group)` = número de sprites.
- `ShapeBatch` retorna o mesmo tipo de grupo (mesma semântica de views).

### 3. ShapeBatch — `fastobjects/shapes.py` + shader em `fastobjects/core/shaders.py` (novo)

- Mesmo padrão instanciado do core: um buffer de instâncias, um draw call por
  batch, formas misturadas no mesmo lote.
- Layout por instância: **10 floats** — `x, y, w, h, rot, r, g, b, a, kind`
  (kind: 0=retângulo, 1=círculo). Renderer de shapes próprio (não reusa a
  textura do `SpriteRenderer`); vertex shader compartilha a técnica
  `gl_VertexID` + `u_view` do sprite.
- Fragment shader: retângulo = quad sólido; círculo = SDF de elipse com borda
  anti-aliased por `smoothstep` de ~1px.
- **Linha é açúcar da API**: `lines(n, x1, y1, x2, y2, width, color)` converte
  vetorizado (NumPy) endpoints → centro/comprimento/rotação de retângulo. O
  shader não tem kind "linha".
- API (todos aceitam escalares ou arrays de tamanho n, como `spawn`):
  - `ShapeBatch(capacity, ctx=None, view_size=None)`
  - `.rects(n, x, y, w, h, rot=0.0, color=...) -> SpriteGroup`
  - `.circles(n, x, y, radius, color=...) -> SpriteGroup` — armazena
    `w = h = 2*radius` (o layout guarda o bounding box; o SDF usa w/h como
    diâmetros, então `group.size` lê/escreve diâmetro)
  - `.lines(n, x1, y1, x2, y2, width, color=...) -> SpriteGroup`
  - `.clear()`, `.draw()`, `CapacityError` com a mesma mensagem acionável.

### 4. Input — `fastobjects/input.py` (novo)

- `win.keys` — array de bools indexado por keycode glfw
  (`win.keys[fo.KEY_SPACE]`), atualizado por callback `glfw.set_key_callback`
  registrado na criação da janela (pressed=True, released=False).
- `win.mouse` — objeto com `.x`, `.y` (pixels, y para baixo, coerente com o
  renderer), `.left`, `.right`, `.middle` (bools), via callbacks de cursor/botão.
- Constantes `fo.KEY_*` e `fo.MOUSE_*`: re-export das constantes do glfw no
  `__init__.py` (zero manutenção própria).

### 5. Janela implícita — `fastobjects/_context.py` (novo)

- Módulo interno com a janela "atual": `Window.__init__` registra `self`;
  `Window.close()` desregistra se for a atual.
- `SpriteBatch(texture_path, capacity, *, ctx=None, view_size=None)` e
  `ShapeBatch(capacity, *, ctx=None, view_size=None)`: sem `ctx`, usam
  `ctx`/`(width, height)` da janela atual (**quebra de assinatura**: hoje é
  `SpriteBatch(ctx, path, capacity, view_size)`).
- Sem janela atual e sem `ctx` → `RuntimeError` acionável: "Crie fo.Window(...)
  antes de criar batches, ou passe ctx= e view_size= explicitamente."

## Fluxo de dados por frame (inalterado no caminho quente)

Update do usuário escreve nas views do grupo → `batch.draw()` = 1
`buffer.write` + 1 draw instanciado (estratégia A, decidida no lab — ver
`RESULTS.md`). O frame loop e os grupos não adicionam trabalho por sprite.

## Tratamento de erros

Todas as mensagens acionáveis (convenção do projeto): capacity excedida diz o
valor necessário (já existe); batch sem janela diz como resolver; `run()` sem
`@win.frame` diz o que registrar; arquivo de textura inexistente mostra o
caminho resolvido.

## Testes (pytest, offscreen — moderngl standalone, sem janela)

- **SpriteGroup:** views escrevem no array base do batch; sub-slicing; `len`;
  broadcast em atribuição; `spawn` de dois grupos não se sobrepõe.
- **ShapeBatch (pixel tests em FBO):** retângulo colorido nos pixels esperados;
  círculo pinta o centro e NÃO pinta o canto do bounding box (verifica SDF);
  linha diagonal pinta ao longo do segmento; mistura de formas em um draw.
- **Input:** injeta eventos chamando os callbacks diretamente (sem janela real)
  e verifica `keys`/`mouse`.
- **Frame loop:** janela `visible=False`; update conta frames e fecha via
  `glfw.set_window_should_close` após N; verifica que `run()` retorna e que
  `dt > 0`.
- **Janela implícita:** com janela invisível criada, batch sem `ctx` funciona;
  sem janela, erro acionável.
- Arena re-executada ao final da fase (`run_all.py --save`) para confirmar
  ausência de regressão — resultado registrado em `RESULTS.md`.

## Estrutura resultante

```
fastobjects/
  __init__.py    # exporta Window, SpriteBatch, ShapeBatch, SpriteGroup,
                 # CapacityError, KEY_*/MOUSE_*
  window.py      # + frame/run/draw/keys/mouse
  input.py       # NOVO: Keyboard/Mouse (estado de polling)
  batch.py       # spawn() -> SpriteGroup; assinatura com ctx opcional
  group.py       # NOVO: SpriteGroup
  shapes.py      # NOVO: ShapeBatch (+ conversão vetorizada de linhas)
  _context.py    # NOVO: janela atual
  core/
    renderer.py  # intocado
    shaders.py   # + SHAPE_VS/SHAPE_FS
  errors.py      # intocado
```
