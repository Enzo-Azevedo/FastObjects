# FastObjects 0.6.2 — Shaping de texto complexo (RTL, kerning, ligaturas) — Design Spec

**Data:** 2026-07-13
**Status:** Aprovado pelo usuário (sequência 0.6.2=shaping / 0.6.3=SDF decidida em
conversa; ativação automática com fallback escolhida)
**Base:** v0.6.1 lançada (fontes .ttf/.otf + charsets; 136 testes; gate freetype-gl
aprovado 145.873 vs 55)

## Objetivo

Texto **correto** para escritas complexas: RTL (árabe, hebraico), kerning avançado e
ligaturas/formas contextuais, via HarfBuzz + freetype-py como **extra opcional** —
`pip install fastobjects[shaping]` — com ativação automática e fallback silencioso
para o layout simples atual quando o extra não está instalado. O core mantém as 4
dependências.

Hoje o layout avança caractere a caractere (`getlength`): árabe sai desconectado e na
ordem errada, hebraico sai invertido, "AV" não tem kerning. Isso é texto ERRADO, não
apenas feio — corretude antes de estética (SDF/MSDF fica para a 0.6.3).

**Critério de aceite da fase:** com o extra instalado, árabe e hebraico renderizam na
ordem/forma corretas (validado contra Pillow+Raqm como referência publicada), kerning
aplicado em pares latinos; sem o extra, comportamento 0.6.1 intacto; throughput de
draw inalterado (o frame não muda); suíte inteira passa, **incluindo os novos testes
de edge cases** (regra permanente a partir desta fase: capacity zero, despawn em
massa, resize de janela).

## Escopo

1. **`fastobjects/shaping.py`** (novo) — backend shaped isolado: `uharfbuzz` shapeia,
   `freetype-py` rasteriza por glyph-ID, atlas com **todos os glifos da fonte**.
2. **`Font`** — usa o backend shaped automaticamente quando `source` é `.ttf`/`.otf`
   e o extra está instalado; `Font.shaped: bool` informa o caminho ativo.
3. **Extra `shaping`** no pyproject (`uharfbuzz`, `freetype-py`).
4. **Testes** — shaping (kerning/árabe/hebraico/fallback) + edge cases permanentes.
5. **Benchmark** — custo de shaping no `write()` vs Pillow+Raqm; draw inalterado.
6. **Docs bilíngues + release 0.6.2** (tag → PyPI via workflow, REST API p/ release).

**Fora de escopo:** SDF/MSDF (0.6.3); bidi completo para linhas mistas LTR+RTL (a
linha usa a direção dominante detectada pelo HarfBuzz; documentado como limite —
python-bidi/fribidi ficam para quando houver demanda); atlas dinâmico (rejeitado —
ver decisões); features OpenType configuráveis (`liga`/`kern` ficam nos defaults do
HarfBuzz); quebra automática de linha.

## Decisões de design (com alternativas rejeitadas)

- **Atlas por glyph-ID com a fonte inteira (abordagem A).** Ligaturas e formas
  contextuais produzem glyph-IDs que não correspondem a caractere nenhum do charset;
  com todos os glifos da fonte no atlas, qualquer saída do shaper existe. Arial
  (~3.400 glifos, 24px) ≈ atlas ~1500px — folga no guard de 8192; fontes gigantes
  estouram em `AtlasOverflowError` acionável (o hint sugere fonte menor ou o caminho
  não-shaped via desinstalar/`chars=`). Rejeitado atlas dinâmico (B): quebra a
  invariante de atlas estático e exige re-upload de textura em runtime — risco alto
  para ganho só em CJK gigante. Rejeitado Pillow+Raqm rasterizando strings inteiras
  (C): uma textura por string destrói a performance; vira referência de corretude nos
  testes.
- **Automático com fallback.** `Font("x.ttf")` shapeia se `uharfbuzz`+`freetype-py`
  importarem; senão cai no caminho 0.6.1 sem erro. Zero fricção; `Font.shaped`
  remove a ambiguidade. Rejeitados: flag `shape=True` (mais um parâmetro para
  descobrir) e shaping obrigatório (quebraria quem usa `.ttf` só com o core).
- **No caminho shaped, `charset`/`chars` definem só a visão pública `Font.glyphs`
  (char → Glyph, via cmap), não o atlas nem o layout** — o atlas tem a fonte
  inteira e o layout aceita qualquer caractere. Isso preserva o contrato público
  de `glyphs` da 0.6.1 (testes e docs acessam `f.glyphs["A"]`). Caractere sem
  glifo na fonte rasteriza o `.notdef` (tofu) da fonte. O caminho não-shaped
  continua exatamente como na 0.6.1, incluindo a validação de `chars` vazio.
- **Shaping por linha, direção automática.** `\n` divide; cada linha vira um buffer
  HarfBuzz com `guess_segment_properties()` (direção/script pela primeira letra
  forte). Linha mista usa a direção dominante — documentado.
- **Fonte embutida do Pillow nunca shapeia** — não há arquivo para o HarfBuzz abrir.

## Componentes

### 1. `fastobjects/shaping.py` (novo)

```python
def available() -> bool            # uharfbuzz e freetype importam?
class ShapedBackend:
    def __init__(self, source: str, size: int) -> None
    line_height: float             # métricas da face (ascender - descender) escaladas
    glyphs: dict[int, Glyph]       # glyph-ID -> Glyph (uv/size/offset; advance do shaper)
    atlas_pixels: bytes
    atlas_size: tuple[int, int]
    def shape_line(self, line: str) -> list[tuple[int, float, float]]
        # [(glyph_id, x_advance, x_offset/y_offset aplicados)] na ordem VISUAL
```

- Carrega a face 2x: `freetype.Face(source)` (rasterização) e `uharfbuzz`
  (`hb.Face(blob)` → `hb.Font`, escala = size em unidades 26.6/64 coerentes).
- Rasteriza `face.num_glyphs` glifos (`load_glyph(i, FT_LOAD_RENDER)`): coverage u8 →
  RGBA branco (mesmo pipeline do `Font` atual) → `Atlas` existente. Glifo vazio
  (espaço) → `Glyph(uv=None, ...)`.
- `shape_line`: `hb.Buffer()`, `add_str`, `guess_segment_properties`,
  `hb.shape(font, buf)` → infos/positions; converte para px (escala/64) e devolve na
  ordem visual que o HarfBuzz já produz (RTL sai invertido pronto para desenhar
  esquerda→direita).

### 2. `Font` — `fastobjects/font.py` (modificado)

- No `__init__`, após resolver `source`: se `source is not None and
  shaping.available()` → monta via `ShapedBackend`, `self.shaped = True`; senão o
  caminho atual, `self.shaped = False`. Falha do backend shaped em abrir a fonte →
  mesmo `ValueError` acionável de fonte não encontrada.
- `layout(text)`/`measure(text)` mantêm assinatura e retorno idênticos
  (`centers/sizes/uvs/block`): no caminho shaped, cada linha vem de `shape_line` e o
  pen anda pelos advances do shaper (kerning incluído). `TextBatch` não muda uma
  linha.
- Docstring documenta `shaped`, o extra e o limite de linha mista.

### 3. Extra — `pyproject.toml`

```toml
shaping = ["uharfbuzz>=0.39", "freetype-py>=2.5"]
```

### 4. Testes

`tests/test_shaping.py` (novo, `skipif` sem extra ou sem arial.ttf; arial cobre
árabe/hebraico no Windows):

- `Font("arial.ttf", 24).shaped is True` com extra; monkeypatch em
  `shaping.available` → `False` e `shaped is False` (fallback).
- Kerning: largura de `layout("AV")` < soma dos advances isolados de "A" e "V".
- Árabe: `layout("لا")` (lam-alef) produz **1** glifo; `layout("بب")` produz formas
  inicial/final com UVs **diferentes** entre si (formas contextuais).
- Hebraico RTL: em `layout("אב")`, o glifo de "א" tem center.x **maior** que o de
  "ב" (primeiro caractere lógico desenhado à direita).
- Corretude vs referência publicada: renderizar "سلام" via Pillow+Raqm
  (`ImageDraw.text`, se `ImageFont.core.HAVE_RAQM`) e via TextBatch offscreen —
  proporção largura/altura dos pixels acesos compatível (tolerância larga; valida
  ordem/conexão, não anti-aliasing).
- Pixel-test: TextBatch com fonte shaped desenha árabe sem exception e acende pixels.

`tests/test_edge_cases.py` (novo — regra permanente do usuário):

- **Capacity zero e alocação vazia**: `capacity=0` levanta o `ValueError`
  acionável que o `BatchCore` já define (contrato existente, pinado por teste);
  `spawn(0)`/`write("")` num batch normal devolve grupo vazio válido; lote cheio
  exato funciona e o objeto seguinte → `CapacityError`.
- **Despawn em massa**: 50 grupos, despawn de todos em ordem aleatória (seed fixa) —
  count volta a 0, handles restantes válidos a cada passo, redesenho não quebra;
  despawn de grupo já removido → `RuntimeError`.
- **Resize de janela**: comportamento atual do `view_size` documentado por teste —
  desenhar num FBO 128x64, "redimensionar" recriando renderer com view_size novo e
  verificar que as posições em px continuam ancoradas no topo-esquerda (o que existir
  hoje vira contrato; se resize quebrar o renderer, consertar o mínimo).

### 5. Benchmark — `benchmarks/text/bench_shaping.py` (novo)

- Load/`write()`: strings/s de `write()` shaped vs não-shaped (mesma `.ttf`), e vs
  Pillow+Raqm rasterizando as mesmas strings árabes (código publicado equivalente).
- Draw: reusar `bench_fastobjects.py --font` com extra instalado — o número de
  145.873 não deve regredir (o frame não muda; qualquer regressão é bug).
- Resultados datados em `benchmarks/RESULTS.md`.

### 6. Docs + release

- Guia de texto EN/PT: seção "Complex text (shaping)" — extra, `Font.shaped`,
  exemplo árabe/hebraico, limite de linha mista.
- API EN/PT: `Font.shaped` + nota do extra. Performance EN/PT: custo de shaping.
- Bump 0.6.2 (3 arquivos), branch `shaping` → merge ff em main, tag `v0.6.2`,
  pre-release via REST API (token `git credential fill`), acompanhar publish/docs,
  confirmar PyPI.

## Riscos

- **uharfbuzz no Windows/Python 3.13:** wheels existem (projeto ativo do fonttools);
  se a instalação falhar, PARAR e reportar antes de qualquer workaround.
- **Métricas hb vs freetype:** advances do HarfBuzz em unidades de fonte escaladas
  precisam bater com os bitmaps do FreeType no mesmo px size — testes de kerning e
  medida pegam desalinhamento cedo.
- **Atlas maior** (fonte inteira): arial 24px ≈ ~1500px² — ok; fontes CJK podem
  estourar o guard → erro acionável já existente (`AtlasOverflowError`).
- **Fallback silencioso** pode mascarar extra quebrado: `Font.shaped` + docs mitigam.
