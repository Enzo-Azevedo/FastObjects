# FastObjects Interop (hosts externos) + despawn — Design Spec

**Data:** 2026-07-07
**Status:** Aprovado pelo usuário (seções validadas em conversa; SurfaceLayer incluído a pedido)
**Base:** v0.1.0 lançada (core instanciado + API pública; 64 testes; arena 218.809 sprites@60fps)

## Objetivo

Permitir usar o FastObjects **dentro de janelas criadas por outras bibliotecas**: o host
(ex.: pygame) é dono da janela, do loop, dos eventos, do input e do som; o FastObjects é
dono da inserção, atualização, **remoção** e desenho dos objetos. Adicionalmente, o
desenho clássico do host (ex.: `pygame.draw`/`pygame.font` em Surfaces) convive na mesma
janela via camada de composição.

**Critério de aceite da fase:** `examples/pygame_interop.py` roda copiado-e-colado —
janela pygame `OPENGL|DOUBLEBUF`, eventos/input/loop do pygame, sprites e shapes do
fastobjects, HUD desenhado com `pygame.draw`/`pygame.font` composto por cima, spawn no
clique e despawn por tecla — e a suíte inteira passa.

## Escopo

1. **`fo.attach()`** — conectar o FastObjects ao contexto GL atual de qualquer host.
2. **`despawn()` real** — remoção seletiva de grupos com compactação vetorizada e
   handles sobreviventes (SpriteBatch e ShapeBatch).
3. **`fo.SurfaceLayer`** — Surfaces do pygame (desenho clássico por CPU) compostas
   pela GPU na janela do fastobjects/host.
4. **`examples/pygame_interop.py`** — exemplo executável completo (inaugura `examples/`).
5. **Release 0.2.0** — tag + pre-release GitHub ao final (PyPI publica via workflow).

**Fora de escopo:** hosts pyglet/arcade/raylib (fase seguinte, um exemplo validado por
host); backend Vulkan (não resolve o problema — qualquer API de GPU exclui a
apresentação por software do SDL; a resposta é a composição via SurfaceLayer);
docs mkdocs.

## Decisões de design (com alternativas rejeitadas)

- **`fo.attach()` genérico, não módulo por host.** Attach ao contexto GL corrente
  funciona para qualquer host GL; pygame é exemplo documentado, não caso especial no
  código. Rejeitado `fo.interop.pygame.init()`: acoplaria o core a cada concorrente.
- **despawn real com compactação, não hide.** `visible=False`/alpha 0 não devolve
  capacity — jogos com spawn/despawn contínuo esgotariam o batch. Rejeitado swap-remove
  (troca com o fim): quebraria a contiguidade dos grupos; compactação estável preserva.
- **Handles sobrevivem ao despawn.** O batch mantém registro (weakrefs) dos grupos e os
  realoca após compactar. Alternativa rejeitada (todos os handles inválidos após
  qualquer despawn): inviabiliza o uso real em jogos.
- **SurfaceLayer com lazy import de pygame.** O core não ganha dependência de pygame
  (`pyproject` inalterado); `pygame.image.tobytes` é importado dentro de `update()`,
  onde uma Surface já implica pygame instalado. Rejeitado exigir que o usuário converta
  bytes manualmente: ergonomia ruim para o caso de uso número 1.
- **Refatoração dirigida: `_BatchCore`.** SpriteBatch e ShapeBatch já duplicam
  alocação/guards; despawn + registro de grupos triplicaria a duplicação. A lógica comum
  (count, capacity, _alloc, despawn, clear, registro de grupos) sobe para uma base
  interna comum. Sem mudança de API pública.

## Componentes

### 1. `fo.attach` — `fastobjects/external.py` (novo)

```python
def attach(view_size: tuple[int, int]) -> ExternalWindow
```

- Chama `moderngl.create_context()` — o moderngl **conecta-se ao contexto GL corrente**
  do host (pygame com `OPENGL|DOUBLEBUF`, pyglet, etc.). Habilita `BLEND`.
- Cria `ExternalWindow(ctx, width, height)` e o registra como janela atual
  (`_context.set_current`) — a partir daí batches implícitos funcionam idênticos ao
  modo nativo.
- `ExternalWindow` expõe **apenas**: `.ctx`, `.width`, `.height`, `.clear(r, g, b)`
  (via `ctx.clear`) e `.close()` (desregistra se for a atual). **Sem** `run/frame/
  keys/mouse/swap` — loop, eventos, input e flip são do host, por design.
- Falha do moderngl (host sem contexto GL corrente) → `RuntimeError` acionável:
  "Nenhum contexto OpenGL ativo. Crie a janela do host com OpenGL antes de fo.attach()
  — ex.: pygame.display.set_mode((w, h), pygame.OPENGL | pygame.DOUBLEBUF)."
- `_context.py` não muda de interface: `ExternalWindow` satisfaz o mesmo protocolo
  informal (`ctx/width/height`) que `Window`.

### 2. despawn — `fastobjects/_batchcore.py` (novo), `batch.py`, `shapes.py`, `group.py`

**`_BatchCore`** (base interna, sem API pública própria): possui `data`, `count`,
`capacity`, `_renderer`, o registro de grupos (`weakref.WeakSet[SpriteGroup]`),
`_alloc(n, method)` (guards atuais), `clear()`, `despawn(group)` e `draw()`.
`SpriteBatch` e `ShapeBatch` herdam; suas fábricas (`spawn`, `rects`, `circles`,
`lines`) registram cada grupo criado. `SpriteGroup.__getitem__` também registra o
sub-grupo no batch.

**`despawn(group)`**:

1. Valida: grupo pertence a este batch e está vivo; senão `ValueError`/`RuntimeError`
   acionável.
2. Compacta com uma cópia vetorizada: `data[start:count-n] = data[stop:count]`
   (n = len(group)); `count -= n`.
3. Realoca os grupos vivos do registro comparando com o trecho removido `[start, stop)`:
   - termina antes (`g.stop <= start`): intacto;
   - começa depois (`g.start >= stop`): desloca `n` à esquerda;
   - contém o trecho (`g.start <= start and g.stop >= stop`, ex.: pai de sub-grupo):
     encolhe `n` (stop -= n);
   - é o próprio grupo ou está contido nele: **invalidado**.
   - sobreposição parcial não-aninhada (sub-grupos irmãos como g[3:6] e g[4:7]):
     **invalidado** conservadoramente — realocação segura é impossível.
4. Grupo invalidado: qualquer acesso a propriedade/len/getitem levanta `RuntimeError`
   acionável ("grupo removido do batch — spawn() de novo para criar objetos").

**`clear()`** passa a invalidar todos os grupos do registro (corrige o bug latente de
handles antigos apontando para linhas recicladas após clear+respawn).

Custo no caminho quente: zero — `draw()` e as views não mudam; o registro só é tocado
em spawn/despawn/clear.

### 3. `fo.SurfaceLayer` — `fastobjects/layer.py` (novo)

```python
SurfaceLayer(surface, *, ctx=None, view_size=None)
```

- `surface`: uma `pygame.Surface` (duck-typed: precisa de `get_size()`); tamanho fixo
  na criação.
- Internamente: uma textura RGBA do tamanho da surface + um quad texturizado cobrindo
  o retângulo da surface (reusa `SPRITE_VS`/`SPRITE_FS` com um buffer de 1 instância),
  mesmo blending dos sprites (alpha reto).
- `.update()` — sobe a surface para a GPU: `pygame.image.tobytes(surface, "RGBA")`
  (import de pygame **dentro** do método; ausência de pygame → `ImportError` acionável)
  seguido de `texture.write(...)`. Ordem de linhas do pygame é top-down, igual à
  convenção y-para-baixo do renderer — sem flip.
- `.draw()` — desenha o quad (1 draw call). Ordem de composição é do usuário
  (chamar antes/depois dos batches).
- `ctx`/`view_size` implícitos da janela atual, como os batches.
- Posição fixa em (0,0) cobrindo o tamanho da surface (caso HUD tela-cheia); posição/
  tamanho custom ficam para quando houver demanda (YAGNI).

### 4. Exemplo — `examples/pygame_interop.py` (novo diretório)

- Janela: `pygame.display.set_mode((1280, 720), pygame.OPENGL | pygame.DOUBLEBUF)`;
  `pygame.display.flip()` no fim de cada frame.
- fastobjects: `fo.attach(view_size=(1280, 720))`, um `SpriteBatch` de coelhos
  (asset `benchmarks/arena/assets/bunny.png`) e um `ShapeBatch` decorativo.
- Interação (input 100% pygame): clique esquerdo → `spawn(100)` na posição do mouse
  (guarda o grupo numa pilha); tecla **D** → `despawn` do último grupo da pilha;
  **ESC**/fechar → sai.
- HUD (desenho clássico pygame): `pygame.font` com contagem de sprites + instruções,
  `pygame.draw.circle` no cursor, numa Surface `SRCALPHA` composta via `SurfaceLayer`
  por cima dos batches.
- `--frames N`: roda N frames e imprime `interop ok: <N> frames, <count> sprites` —
  modo não-interativo para verificação automatizada.
- Física dos coelhos vetorizada nas views dos grupos (padrão da casa).

### 5. Release 0.2.0

Ao final da fase (pós-merge em main): `__version__`/`pyproject` → `0.2.0`, tag
`v0.2.0`, GitHub pre-release; o push da tag dispara `publish.yml` → PyPI (trusted
publishing, como no 0.1.0; criação de release via REST API — não há gh CLI na máquina).

## Tratamento de erros

Acionáveis, padrão do projeto: attach sem contexto GL diz como criar a janela do host;
grupo inválido diz que foi removido e o que fazer; despawn de grupo de outro batch diz
isso; SurfaceLayer sem pygame instala; update() com surface de tamanho diferente do
inicial diz os dois tamanhos.

## Testes (pytest; offscreen onde possível)

- **despawn (offscreen, a maior bateria):** compactação correta (dados dos vizinhos
  preservados byte a byte), realocação (antes/depois/pai/contido), invalidação (acesso
  levanta), capacity devolvida (spawn após despawn cabe), clear invalida todos,
  despawn de grupo alheio/repetido levanta, pixel test: desenha 2 grupos, despawn de 1,
  só o outro aparece. Igual para ShapeBatch (herda da base).
- **attach:** com `Window(visible=False)` como host GL (contexto corrente do glfw),
  `fo.attach` conecta, registra como atual, batch implícito desenha (pixel test em FBO);
  `close()` desregistra; erro sem contexto testado com monkeypatch de
  `moderngl.create_context`.
- **SurfaceLayer:** requer pygame (está no venv via extra bench) — cria surface,
  desenha um retângulo com pygame.draw, update+draw, lê pixels do FBO e verifica cor e
  posição; erro de tamanho divergente; teste pula (`pytest.importorskip`) se pygame
  ausente.
- **Exemplo:** `.venv\Scripts\python examples/pygame_interop.py --frames 120` roda sem
  exceção e imprime a linha final (verificação do task; janela real abre).
- Suíte inteira + ruff verdes; arena re-executada ao final por higiene (nada do caminho
  medido muda).

## Estrutura resultante

```
fastobjects/
  external.py     # NOVO: attach() + ExternalWindow
  layer.py        # NOVO: SurfaceLayer
  _batchcore.py   # NOVO: base interna comum (alloc/despawn/clear/registro)
  batch.py        # SpriteBatch herda da base; spawn registra grupos
  shapes.py       # ShapeBatch herda da base
  group.py        # invalidação + registro de sub-grupos
  __init__.py     # + attach, ExternalWindow, SurfaceLayer
examples/
  pygame_interop.py  # NOVO (inaugura o diretório)
```
