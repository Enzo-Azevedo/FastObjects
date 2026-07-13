# Referência da API

Tudo que é importável de `fastobjects` (importado como `fo`). As coordenadas
são pixels, y para baixo.

## `Window`

```python
Window(width, height, title="fastobjects", vsync=False, visible=True)
```

Janela GLFW nativa com contexto OpenGL 3.3 core. Registra-se como janela
atual na criação. Levanta `RuntimeError` se o GLFW ou o contexto GL não
puderem ser criados.

| Membro | Descrição |
|---|---|
| `frame(fn)` | Decorator; registra `fn(dt: float)` como update por frame. Registrar de novo substitui. |
| `run()` | Roda o loop até fechar: poll → `dt` → update → swap. Levanta `RuntimeError` se nenhum frame foi registrado. |
| `draw(*batches)` | Chama `.draw()` em cada desenhável, na ordem. |
| `clear(r, g, b)` | Limpa o framebuffer (valores 0–1). |
| `request_close()` | Encerra `run()` de dentro do update. |
| `should_close` | Propriedade `bool` — fechamento solicitado. |
| `poll()` / `swap()` | Poll de eventos / troca de buffer manuais (loops à mão). |
| `close()` | Destrói a janela; desregistra se for a atual. |
| `keys` | `Keyboard`: `keys[fo.KEY_X] -> bool`. |
| `mouse` | `Mouse`: `.x`, `.y`, `.left`, `.right`, `.middle`. |
| `ctx`, `width`, `height` | Contexto moderngl e tamanho. |

Usar `run`/`swap`/`request_close`/`should_close` após `close()` levanta
`RuntimeError`.

## `SpriteBatch`

```python
SpriteBatch(images, capacity, *, ctx=None, view_size=None)
```

Pool de capacidade fixa de sprites texturizados desenhado em uma chamada
instanciada. `images` é um caminho (`str`), uma lista de caminhos (por índice)
ou um `dict` nome→caminho (por nome) — empacotados num texture atlas na
criação. `ctx`/`view_size` usam a janela atual por padrão. Levanta `ValueError`
se `capacity <= 0`, `FileNotFoundError` (caminho resolvido) para imagem
inexistente, ou `AtlasOverflowError` se as imagens não couberem numa textura.

| Membro | Descrição |
|---|---|
| `spawn(n, x=0, y=0, w=None, h=None, rot=0, color=(1,1,1,1), image=0)` | Cria `n` sprites, retorna um `SpriteGroup`. Cada arg é escalar ou array de tamanho `n`; `image` (índice ou nome) escolhe a sub-imagem; `w`/`h` usam o tamanho dela por padrão. Levanta `ValueError` (n<0, image inválido) ou `CapacityError`. |
| `despawn(group)` | Remove o grupo, compacta o armazenamento, devolve capacity, realoca handles sobreviventes. Levanta `ValueError` (batch alheio) / `RuntimeError` (já removido). |
| `clear()` | Remove todos os sprites; invalida todos os handles. |
| `draw()` | Sobe as colunas mudadas + posições, um draw call instanciado. |
| `count` | Contagem de sprites vivos. |
| `pos`, `size`, `rot`, `color` | Views NumPy do batch inteiro (capacity linhas). Acessar as frias marca-as para upload. |

## `ShapeBatch`

```python
ShapeBatch(capacity, *, ctx=None, view_size=None)
```

Como `SpriteBatch` mas para primitivas sem textura; formas misturadas
compartilham um draw call. Mesmos `despawn`/`clear`/`draw`/`count`/`pos`/
`size`/`rot`/`color`.

| Fábrica | Descrição |
|---|---|
| `rects(n, x=0, y=0, w=10, h=10, rot=0, color=(1,1,1,1))` | Retângulos (posição = centro). Retorna `SpriteGroup`. |
| `circles(n, x=0, y=0, radius=5, color=(1,1,1,1))` | Círculos SDF; guarda `w=h=2*radius`. Retorna `SpriteGroup`. |
| `lines(n, x1, y1, x2, y2, width=1, color=(1,1,1,1))` | Linhas como retângulos rotacionados. Retorna `SpriteGroup`. |

Todos os args são escalares ou arrays de tamanho `n`; mesmos guards
`ValueError`/`CapacityError`.

## `SpriteGroup`

Um handle sobre uma fatia contígua de um batch — um objeto por grupo, nunca
por sprite. Retornado por `spawn`/`rects`/`circles`/`lines`. As propriedades
são views NumPy do batch.

| Membro | Descrição |
|---|---|
| `x`, `y`, `w`, `h`, `rot` | Views 1D (comprimento = tamanho do grupo). |
| `pos` (n,2), `size` (n,2), `color` (n,4) | Views em bloco. |
| `image` (setter) | `group.image = i` re-textura o grupo para a imagem `i` do atlas (índice ou nome). Só em grupos de sprite; levanta em grupos de forma. |
| `slice` | Slice absoluto no batch. |
| `len(grupo)` | Contagem de sprites. |
| `grupo[a:b]` | Sub-grupo sobre o mesmo armazenamento (passo deve ser 1). |

Ler ou escrever size/rot/color marca aquela coluna para upload (conservador
— nunca um sumiço silencioso). Após `despawn`/`clear`, qualquer acesso
levanta `RuntimeError`. Não guarde uma view de propriedade entre frames;
reacesse-a.

## `Font`

```python
Font(source=None, size=24, *, chars=None, charset="latin")
```

Rasteriza um conjunto de caracteres num atlas de glifos (sem OpenGL —
usável/testável sem contexto). Assinatura estilo pygame: fonte primeiro,
tamanho depois.

- `source` — caminho `.ttf`/`.otf` ou nome de fonte instalada no sistema
  (ex.: `"arial.ttf"`); `None` usa a fonte embutida escalável do Pillow.
  Levanta `ValueError` se a fonte não for encontrada.
- `charset` — nome de preset ou tupla de presets: `"ascii"`, `"latin"`
  (padrão: ASCII + Latin-1, cobre acentos), `"latin-ext"`, `"greek"`,
  `"cyrillic"`. Presets são independentes; combine para texto misto.
- `chars` — string explícita de caracteres; vence `charset`. Levanta
  `ValueError` se vazio.

Com o extra opcional `fastobjects[shaping]` instalado (uharfbuzz +
freetype-py), fontes `.ttf`/`.otf` são shapeadas automaticamente — RTL,
kerning e ligaturas corretos (`shaped=True`); o atlas então contém a fonte
inteira e `charset`/`chars` definem apenas a visão pública `glyphs`. Sem o
extra, o `Font` cai silenciosamente no layout simples por caractere.

| Membro | Descrição |
|---|---|
| `measure(text) -> (w, h)` | Tamanho do bloco de `text` (com `\n`), sem desenhar. |
| `line_height` | Altura de uma linha, em pixels. |
| `shaped` | `True` quando o shaping (HarfBuzz) está ativo nesta fonte. |
| `size`, `source`, `glyphs` | O size pedido; o source pedido (`None` = embutida); dict char → info do glifo. |

## `TextBatch`

```python
TextBatch(font, capacity, *, ctx=None, view_size=None)
```

Desenha texto como sprites do atlas de glifos em um draw call. `capacity` é o
máximo de glifos somando todos os writes vivos. `ctx`/`view_size` usam a janela
atual por padrão.

| Membro | Descrição |
|---|---|
| `write(text, x, y, color=(1,1,1,1), anchor="topleft") -> SpriteGroup` | Faz o layout de `text` e retorna um grupo sobre os quads (mova/recolore). `\n` quebra linha; `anchor` é `"topleft"` ou `"center"`. Levanta `ValueError` (anchor inválido) ou `CapacityError`. |
| `clear()` | Remove todos os glifos (para texto dinâmico por frame). |
| `draw()`, `count` | Um draw call instanciado; contagem de glifos vivos. |

## `SurfaceLayer`

```python
SurfaceLayer(surface, *, ctx=None, view_size=None)
```

Compõe uma `pygame.Surface` (desenho clássico por CPU) como quad
texturizado. Tamanho fixo na criação; levanta `ValueError` para surface de
tamanho zero.

| Membro | Descrição |
|---|---|
| `update()` | Sobe a surface para a GPU (um upload). Levanta `ImportError` se o pygame faltar, `ValueError` se a surface mudou de tamanho. |
| `draw()` | Compõe (um draw call). |

## `attach` / `ExternalWindow`

```python
attach(view_size) -> ExternalWindow
```

Conecta o FastObjects ao contexto OpenGL corrente do host e registra um
`ExternalWindow` como atual. Chame uma vez por janela do host. Levanta
`RuntimeError` se não houver contexto GL ativo.

`ExternalWindow` expõe apenas `.ctx`, `.width`, `.height`, `.clear(r, g, b)`
e `.close()` — o host é dono do loop, do input e da troca de buffer.

## Constantes & erros

- `fo.KEY_*` — códigos de tecla do glfw (`KEY_SPACE`, `KEY_ESCAPE`,
  `KEY_A`, setas, etc.).
- `fo.MOUSE_BUTTON_*` — códigos de botão do mouse do glfw.
- `CapacityError` — levantado quando um spawn excede a capacity do batch; a
  mensagem diz a capacity de que você precisa.
