# FastObjects — Texture Atlas (estático) — Design Spec

**Data:** 2026-07-09
**Status:** Aprovado pelo usuário
**Base:** v0.4.0 no PyPI (interop com pyglet/arcade; 98 testes; arena 328.213 sprites@60fps).
**Última fase planejada do roadmap original** (docs → hosts → **atlas**).

## Objetivo

Permitir que um único `SpriteBatch` desenhe **várias imagens** (spritesheet ou
conjunto de arte de tamanhos diferentes) em **um único draw call**, via texture
atlas: as imagens são empacotadas numa textura, e cada sprite guarda o
retângulo UV da sua sub-imagem. Feature aditiva — nada do uso atual quebra.

O usuário pediu ênfase em (1) testes e (2) comparação com bibliotecas públicas
que já têm a feature (arcade, pyglet).

**Critérios de aceite:**
- Atlas estático de N imagens funcionando: `spawn(image=i)` e `group.image = i`
  desenham a sub-imagem correta (pixel tests de ponta a ponta).
- Compatibilidade retro total: `SpriteBatch("x.png", capacity)` e a suíte atual
  inalterados; arena re-executada sem regressão.
- `docs/RESEARCH.md` com a comparação lida do código de arcade e pyglet.
- Benchmark multi-imagem comparativo (FastObjects vs arcade vs pyglet) no
  `RESULTS.md`.
- Suíte verde com os novos testes; release **0.5.0**.

## Decisões (com alternativas rejeitadas)

- **Texture atlas, não texture array.** Atlas cobre imagens de tamanhos
  variados e é o que arcade/pyglet usam (comparação direta). Texture array
  (uniforme) rejeitado para a v1: menos geral e não comparável.
- **Estático, não dinâmico.** Atlas montado uma vez na criação do batch, a
  partir de uma lista fixa. Add/remove/resize em runtime rejeitado (YAGNI; o
  atlas do arcade tem centenas de linhas para isso) — fase futura.
- **Shelf packing + borda extrudada de 1px.** Algoritmo simples, determinístico
  e testável; a extrusão da borda evita bleeding sob filtragem linear.
  Alocadores mais complexos (arcade/pyglet, feitos para resize dinâmico) são
  desnecessários no caso estático.
- **`uv` como coluna fria do SoA.** Reusa o dirty tracking: setada no spawn,
  só re-sobe se a imagem mudar. Caminho quente inalterado.

## Componentes

### 1. `fastobjects/atlas.py` (novo) — empacotamento, sem GL

Classe interna `Atlas` (lógica pura de packing/UV — testável sem contexto GL):

```python
class Atlas:
    def __init__(self, images: list[PIL.Image.Image], *, max_size: int, padding: int = 1)
    # atributos:
    #   .size: tuple[int, int]        # dimensão da textura empacotada
    #   .pixels: bytes                # RGBA da textura (com bordas extrudadas)
    #   .uvs: np.ndarray (n, 4) f4    # (u0, v0, u1, v1) por imagem de entrada
    #   .sizes: np.ndarray (n, 2) f4  # (w, h) em pixels por imagem
```

- **Shelf packing**: ordena as imagens por altura desc; preenche prateleiras da
  esquerda p/ direita; nova prateleira quando a largura estoura. Largura do
  atlas escolhida como a menor potência de 2 que comporte a imagem mais larga e
  dê uma proporção razoável; altura cresce por prateleiras.
- **Padding**: 1px de borda extrudada (duplica a linha/coluna de borda de cada
  imagem) entre as sub-imagens; as UVs apontam para o interior exato da imagem
  → linear filtering nas bordas não puxa cor do vizinho.
- **Overflow**: se o atlas exceder `max_size` (= `GL_MAX_TEXTURE_SIZE`, tipicamente
  ≥ 8192) → `CapacityError`-like acionável: "As imagens não cabem num atlas de
  {max}x{max}: some {w}x{h}. Reduza as imagens ou divida em vários batches."
- Convenção y: a textura é montada top-down (como o PIL/`tobytes`), coerente com
  o renderer y-para-baixo — sem flip.

### 2. `fastobjects/batch.py` — SpriteBatch multi-imagem

Assinatura estendida (aditiva):

```python
SpriteBatch(images: str | list[str] | dict[str, str], capacity, *, ctx=None, view_size=None)
```

- `str` → atlas de 1 imagem (UV full; comportamento atual, byte a byte).
- `list[str]` → imagens indexadas por posição (`image=0..n-1`).
- `dict[str, str]` → imagens nomeadas (`image="coin"`); resolve nome→índice.
- Constrói o `Atlas` na criação; cria a textura moderngl a partir de
  `atlas.pixels`. Guarda `self._uvs` (n,4) e `self._img_sizes` (n,2) e, se dict,
  o mapa nome→índice.
- `spawn(n, ..., image=0)`:
  - `image` aceita escalar (int/str) ou array de tamanho n (índices) — vetorizado.
  - a coluna `uv` das linhas novas recebe `self._uvs[image]`.
  - `w`/`h` default (None) passam a usar `self._img_sizes[image]` (o tamanho da
    sub-imagem escolhida), não mais um único `texture_size`.
- `set_group_image(s: slice, image) -> None` (usado por `SpriteGroup.image`):
  resolve `image` (escalar/array, int/str) → UVs e escreve na coluna `uv` do
  slice, marcando-a suja.
- `image_index(name: str) -> int` para nomes (erro acionável se o nome não existe).
- Textura filtrada como hoje (sem mipmaps).

### 3. `fastobjects/_batchcore.py` + `group.py` — coluna `uv`

- `BatchCore.__init__` ganha `uv=False` (SpriteBatch passa `uv=True`); se ativo,
  adiciona a coluna `_cols["uv"] = zeros((capacity, 4), f4)`. ShapeBatch não a tem.
- `SpriteGroup.image` (setter): delega a `self._batch.set_group_image(self._slice, value)`.
  Se o batch não implementa (ShapeBatch) → `AttributeError` acionável ("formas
  não têm imagem — use um SpriteBatch"). Getter não é necessário (write-oriented;
  YAGNI).
- `_make_group`/despawn/clear já tratam colunas genéricas — a `uv` entra sem
  mudança nessas rotinas (compactação coluna a coluna já itera `_cols`).

### 4. `fastobjects/core/renderer.py` + shaders

- `SpriteRenderer` ganha o 5º atributo `uv` (VBO próprio, formato `"4f/i"`,
  bytes=16); `COLUMN_*` no renderer incluem `uv`.
- `SPRITE_VS`: novo `in vec4 in_uv;` e `v_uv = mix(in_uv.xy, in_uv.zw, corner + 0.5)`
  (em vez de `corner + 0.5`). `SPRITE_FS` inalterado.
- Dirty tracking: `uv` é fria; o upload respeita o set `dirty` como as demais.
- `_ShapeRenderer` inalterado (formas não têm uv/atlas).

### 5. Pesquisa comparativa — `docs/RESEARCH.md`

Nova seção lendo o código instalado:
- `arcade` — `arcade/texture_atlas/` (atlas dinâmico com alocador e resize;
  region allocation; UV textures via buffer). Registrar: dinâmico vs nosso
  estático, custo de resize, como faz UV.
- `pyglet` — `pyglet/image/atlas.py` (`Allocator`/`TextureAtlas`/`TextureBin`;
  cresce criando novos atlas quando cheio). Registrar a abordagem.
- Conclusão: por que o estático + shelf basta para o caso do FastObjects (arte
  conhecida na criação), e o que ganharíamos/perderíamos indo dinâmico.

### 6. Benchmark multi-imagem — `benchmarks/multi_image/`

- Gera M imagens distintas (cores/formas diferentes, determinístico).
- `bench_fastobjects.py`: um `SpriteBatch(list_of_M_images, capacity=N)`,
  `spawn(N, image=<array ciclando 0..M-1>)`, física vetorizada, mede FPS/frame
  time no protocolo da casa.
- `bench_arcade.py`: `arcade.SpriteList` com M texturas diferentes (o atlas do
  arcade é usado internamente), N sprites.
- `bench_pyglet.py`: N `pyglet.sprite.Sprite` com M imagens.
- `run_all.py`: roda os três em subprocessos (padrão da arena), tabela no
  `RESULTS.md`. Foreground.

### 7. Docs + exemplo

- Guia: seção "Multiple images (atlas)" (EN/PT) — criar batch com lista/dict,
  `image=` no spawn (escalar e array), `group.image` para animação, limites
  (estático, max texture size). API reference atualizada (`images`, `image`,
  `group.image`).
- `examples/atlas_animation.py`: spritesheet gerado, animação por
  `group.image = frame` a cada N frames; `--frames` auto-teste.

### 8. Release 0.5.0

Bump + tag + pre-release via REST API + PyPI + docs (padrão). Nota: a tag
dispara Publish e o push em main dispara Docs; ambos usam OIDC — se um 503 do
OIDC do GitHub reincidir (como no 0.4.0), re-executar os jobs falhos.

## Tratamento de erros

- Atlas overflow: mensagem acionável com o tamanho que estourou.
- `image` índice fora de faixa / nome inexistente: erro acionável listando o
  intervalo válido / os nomes disponíveis.
- `group.image` em ShapeBatch: erro acionável.
- Guards atuais (capacity, n<0, textura inexistente) preservados.

## Testes (ênfase do usuário)

**Unitários sem GL (packing):**
- imagens empacotadas sem sobreposição; UVs dentro de [0,1] e correspondendo ao
  retângulo de cada imagem; padding presente; determinismo.
- overflow → erro acionável.

**Pixel tests (FBO offscreen):**
- atlas de 2 imagens geradas no teste (quadrado vermelho + quadrado verde);
  spawn de 1 sprite de cada em posições distintas; render; o vermelho lê
  vermelho e o verde lê verde (prova packing→UV→shader ponta a ponta).
- `group.image = idx` re-textura (vermelho→verde no mesmo sprite).
- anti-bleeding: duas imagens contrastantes adjacentes no atlas; a borda de uma
  não mostra a cor da vizinha.
- spawn vetorizado com array de índices: sprites alternam as imagens corretas.
- size default = tamanho em pixels da imagem escolhida.
- dict nomeado: `image="verde"` seleciona a imagem certa; nome inválido levanta.

**Compat retro:**
- `SpriteBatch("bunny.png", capacity)` e todos os testes/benches atuais
  inalterados; a coluna `uv` de imagem única é full e sobe uma vez.

**Integração:**
- arena re-executada (`run_all.py --save`) sem regressão.
- benchmark multi-imagem executado e registrado.

## Fora de escopo

- Atlas dinâmico (add/remove/resize em runtime) — fase futura.
- Texture array; mipmaps; rotação de sub-imagens no packing.
- Empacotamento ótimo (MaxRects etc.) — shelf basta para o estático.
