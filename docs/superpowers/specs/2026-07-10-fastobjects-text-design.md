# FastObjects — Renderização de texto (0.6.0) — Design Spec

**Data:** 2026-07-10
**Status:** Aprovado pelo usuário
**Base:** v0.5.0 no PyPI (texture atlas; 111 testes; arena 328.213 sprites@60fps).
**Split de versões acordado:** 0.6.0 = texto com a fonte embutida; 0.6.1 (futura)
= fontes customizadas (`.ttf`/`.otf` próprios) + formatação/encoding (utf-8,
charset ampliado).

## Objetivo

Texto nativo no FastObjects, desenhado como sprites de um **atlas de glifos** —
reusando o texture atlas, o SoA/coluna `uv`, o renderer e o shader de sprite já
existentes. Um glifo é um quad texturizado; uma string vira um quad por
caractere, tudo em **um draw call**. Preenche a maior lacuna da lib (todo
concorrente tem texto; o FastObjects só tinha via interop/SurfaceLayer).

Ênfase (pedido do usuário): **testes** e **comparação** com como pygame/pyglet/
arcade fazem texto.

**Critérios de aceite:**
- `Font(size)` + `TextBatch(font, capacity).write(text, x, y, color, anchor)`
  desenham texto legível em um draw call (pixel tests de ponta a ponta).
- Acentos do PT (á, ç, ã, é, ...) funcionam por padrão (charset ASCII+Latin-1).
- Aditivo: suíte atual (111) e uso existente inalterados.
- `docs/RESEARCH.md` com a comparação lida de pygame/pyglet/arcade.
- Benchmark de texto (FastObjects vs pygame vs pyglet) no `RESULTS.md`.
- Suíte verde com os novos testes; release **0.6.0**.
- A 0.6.0 também documenta o resultado de packing vs PyTexturePacker (evidência
  já em RESULTS.md) numa nota na página de performance.

## Decisões (com alternativas rejeitadas)

- **Atlas de glifos + 1 draw call** (como pyglet), não uma Surface por string
  (como pygame). Reusa tudo do atlas: rápido, batched, texto dinâmico via clear.
- **Rasterização com Pillow** (`ImageFont`), já dependência do core — **zero
  dependência nova**. `getmask` dá o bitmap de cobertura; `getlength`/`getbbox`
  dão as métricas. Rejeitado freetype-py/bundled bitmap: Pillow já resolve.
- **Fonte embutida do Pillow na 0.6.0** (`ImageFont.load_default(size)`, escala
  bem no Pillow ≥10.1 — verificado no 11.3). Fontes `.ttf` próprias ficam para a
  0.6.1 (split pedido pelo usuário).
- **`Font` puro, sem GL.** Rasterização + packing sem contexto OpenGL → 100%
  testável offline; a textura GL vive no `TextBatch`.
- **Glifo branco × cor no shader.** Rasteriza glifos brancos com alpha =
  cobertura; o shader atual (`texture * v_color`) tinge e o anti-aliasing vem da
  cobertura → alpha. Sem shader novo.
- **Caractere fora do charset é pulado** (avança como espaço), documentado.
  Charset ampliado/encoding = 0.6.1.

## Componentes

### 1. `fastobjects/font.py` — `Font` (puro, sem GL)

```python
Font(size: int = 24, *, chars: str | None = None)
```

- Usa `ImageFont.load_default(size=size)` (fonte embutida escalável do Pillow).
- `chars`: caracteres a incluir no atlas; default = ASCII imprimível (0x20–0x7E)
  + suplemento Latin-1 imprimível (0xA1–0xFF) — cobre acentos do PT.
- Para cada char: `getmask(char)` → bitmap L (cobertura) → RGBA (branco, alpha =
  cobertura). Empacota todos com `Atlas` (padding 1). Guarda por glifo um
  `Glyph`:
  - `uv: (4,) f4` (u0,v0,u1,v1 no atlas)
  - `size: (2,) f4` (w,h em px do bitmap)
  - `advance: float` (`getlength(char)` — quanto o "pen" anda)
  - `offset: (2,) f4` (bearing: `getbbox(char)[:2]` = deslocamento do canto
    superior-esquerdo do bitmap em relação à baseline/pen).
- `line_height: float` (ascent+descent via `font.getmetrics()`).
- Espaço (' ') e chars sem bitmap (largura 0) entram no dict só com `advance`
  (sem quad).
- Atributos públicos: `.atlas_pixels: bytes`, `.atlas_size: (W,H)`,
  `.glyphs: dict[str, Glyph]`, `.line_height: float`, `.size: int`.
- **Sem OpenGL** — testável sem contexto.

### 2. `fastobjects/text.py` — `TextBatch`

```python
TextBatch(font: Font, capacity: int, *, ctx=None, view_size=None)
```

- Subclasse de `BatchCore` (`uv=True`), como `SpriteBatch`. Cria a textura
  moderngl de `font.atlas_pixels` e um `SpriteRenderer(ctx, texture, capacity,
  view_size)` — mesmo caminho quente dos sprites.
- `write(text, x, y, color=(1,1,1,1), anchor="topleft") -> SpriteGroup`:
  - **Layout:** pen em (x, y). Para cada char: se `'\n'`, `pen_y += line_height`,
    `pen_x = x`; senão, se o glifo tem quad, posiciona um quad **centrado** em
    `(pen_x + offset_x + w/2, pen_y + offset_y + h/2)` (os sprites são
    center-based), tamanho `(w,h)`, `uv = glyph.uv`, `color`; e sempre
    `pen_x += glyph.advance`. Char fora do charset → pulado (avança um espaço).
  - **anchor:** `"topleft"` (default) usa (x,y) como canto do bloco;
    `"center"` mede a largura do bloco (maior avanço de linha) e a altura
    (`n_linhas * line_height`) e desloca para (x,y) ser o centro.
  - Aloca `n_glifos` linhas via `_alloc` e preenche as colunas SoA de uma vez
    (arrays montados no layout — sem loop Python por glifo no upload; o loop de
    layout é por caractere, mas texto é baixo volume).
  - Retorna um `SpriteGroup` sobre os quads criados (mover/recolorir o texto:
    `label.color = ...`, `label.pos += ...`).
- `clear()`, `count`, `draw()` herdados. Texto dinâmico (score/FPS): `clear()`
  + `write()` por frame.
- `capacity` = máximo de glifos somando todos os writes vivos. Overflow →
  `CapacityError` (herdado), mensagem acionável.
- Helper `font.measure(text) -> (w, h)` para medir sem desenhar (útil p/ anchor
  e para o usuário posicionar).

### 3. Exports (`__init__.py`)

`Font` e `TextBatch` exportados como `fastobjects.Font` / `fastobjects.TextBatch`.

### 4. Pesquisa — `docs/RESEARCH.md`

Nova seção lendo o código instalado:
- **pygame** (`pygame/font.py` / SDL_ttf): `Font.render(text)` → uma `Surface`
  por string, re-rasterizada; sem atlas de glifos; blit por frame.
- **pyglet** (`pyglet/text/`, `pyglet/font/`): fonte → glyphs rasterizados num
  `TextureAtlas`; `Label` monta uma vertex list batched. Abordagem igual à nossa.
- **arcade**: `arcade.Text` embrulha o texto do pyglet.
- Conclusão: atlas de glifos + 1 draw call (nosso/pyglet) escala para muito texto
  e texto que muda; a Surface-por-string do pygame é simples mas cara em volume.

### 5. Benchmark — `benchmarks/text/`

- `bench_fastobjects.py`: um `TextBatch`, escreve M strings (K glifos cada) — um
  draw call; mede FPS/frame time (protocolo da casa).
- `bench_pygame.py`: `Font.render` por string + blit (uso idiomático do pygame).
- `bench_pyglet.py`: M `pyglet.text.Label` num `Batch`.
- `run_all.py`: subprocessos, tabela no `RESULTS.md`. Foreground.

### 6. Docs + exemplo

- Guia "Text" (EN/PT): criar `Font`, `TextBatch`, `write` (cor, `\n`, anchor),
  texto dinâmico (clear+write), `font.measure`, limites (fonte embutida na
  0.6.0; custom na 0.6.1). API reference (`Font`, `TextBatch`, `write`,
  `measure`).
- `examples/text_hud.py`: contador de FPS + labels; `--frames` auto-teste.
- Nota de packing na página de performance (resultado vs PyTexturePacker).

### 7. Release 0.6.0

Bump + tag `v0.6.0` + pre-release via REST API + PyPI + docs (padrão; re-executar
jobs se um 503 do OIDC reincidir, como no 0.4.0).

## Tratamento de erros

- `TextBatch` sem capacity para o texto → `CapacityError` acionável (herdado).
- `Font` com `chars` vazio → `ValueError` acionável.
- Guards atuais preservados. Sem novas classes de erro.

## Testes (ênfase do usuário)

**Font sem GL (unit):**
- constrói o atlas; cada char do charset tem `uv`/`size`/`advance`/`offset`;
  acentos presentes por padrão; `line_height > 0`; charset custom respeitado;
  `chars=""` levanta.
- `measure(text)` coerente (largura cresce com mais chars; `\n` aumenta altura).

**Pixel tests (FBO offscreen):**
- `write("A")` pinta pixels do glifo dentro do seu bounding box e não fora.
- cor: `write("A", color=(1,0,0,1))` → pixels vermelhos.
- `\n`: segunda linha aparece abaixo (y maior).
- `anchor="center"`: o bloco fica centrado em (x,y).
- espaço avança sem pintar quad; char fora do charset é pulado (sem quad).
- vários `write` desenham juntos em um `draw`.
- o `SpriteGroup` retornado por `write` move/recolore o texto.

**Integração:** benchmark de texto executado e registrado; suíte + ruff verdes.

## Fora de escopo (0.6.1+)

- Fontes customizadas (`.ttf`/`.otf` próprios) e encoding/formatação (utf-8,
  charset ampliado para outros scripts) — **0.6.1**.
- Alinhamento por linha (esquerda/centro/direita) e word-wrap por largura.
- Rich text (múltiplas cores/fontes num write), shaping complexo
  (árabe/índico/ligaduras), atlas de glifos dinâmico.
