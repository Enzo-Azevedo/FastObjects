# FastObjects 0.6.1 — Fontes customizadas + charset Unicode — Design Spec

**Data:** 2026-07-13
**Status:** Aprovado pelo usuário (abordagem A validada em conversa; gate freetype-py
adicionado a pedido)
**Base:** v0.6.0 lançada (texto via atlas de glifos; 127 testes; 145.873 strings@60fps)

## Objetivo

Permitir usar **fontes próprias** (`.ttf`/`.otf`) e **charsets Unicode amplos**
(presets nomeados: grego, cirílico, etc.) no `fo.Font`, mantendo o pipeline de
atlas/render intacto. Escopo definido pelo usuário para a 0.6.1 na conversa da 0.6.0.

**Critério de aceite da fase (gate):** FastObjects com fonte `.ttf` deve **vencer a
técnica freetype-py + OpenGL** (renderizador canônico do tutorial learnopengl: textura
por glifo, quad por glifo, draw call por glifo) em strings @ 60fps, no protocolo padrão
de benchmark do projeto. Tempo de construção do atlas também é medido e reportado
honestamente, vença ou não. E a suíte inteira passa.

## Escopo

1. **`Font(source, size)`** — fonte de arquivo `.ttf`/`.otf` ou do sistema; `None`
   mantém a embutida do Pillow.
2. **`charset=`** — presets Unicode nomeados e combináveis.
3. **Benchmark vs freetype-py + PyOpenGL** — throughput (gate) + tempo de atlas.
4. **Docs bilíngues + release 0.6.1** — tag + pre-release GitHub (PyPI via workflow).

**Fora de escopo:** encoding de bytes em `write()` (strings Python já são Unicode —
descartado pelo usuário); alinhamento/word-wrap multi-linha (fase futura); fontes
coloridas (emoji COLR/CBDT — FreeType via Pillow rasteriza como coverage monocromático);
kerning entre pares (o `getlength` do Pillow já dá o avanço correto por caractere;
kerning por par é refinamento futuro); dynamic atlas.

## Decisões de design (com alternativas rejeitadas)

- **Assinatura estilo pygame:** `Font("fonte.ttf", 24)` — primeiro argumento é a fonte,
  segundo o tamanho, igual `pygame.font.Font(filename, size)` (memória muscular do
  público-alvo). `Font(size=24)` por keyword continua funcionando. Quebra apenas
  `Font(24)` posicional — aceitável pré-1.0, nada no repo usa assim.
  Rejeitados: classe `TrueTypeFont` separada (duplica pipeline, dois tipos para o
  `TextBatch`) e factory `Font.from_file()` (cerimônia extra no caso de uso nº 1).
- **Presets de charset como ranges Unicode fixos**, sem dependência nova (nada de
  fontTools para ler cmap). Caractere que a fonte não cobre rasteriza o tofu da própria
  fonte — comportamento padrão de qualquer renderizador; documentado. Caractere fora do
  charset do atlas continua pulado no layout (comportamento atual).
- **`chars=` vence `charset=`** — controle total continua existindo e é a rota para
  qualquer caractere fora dos presets (box-drawing, símbolos, etc.).
- **Testes com fonte do sistema + `skipif`**, sem asset `.ttf` novo no repo.
  Rejeitado baixar/embutir fonte OFL: peso no repo sem ganho — a máquina de
  desenvolvimento (Windows) tem `arial.ttf` garantido.

## Componentes

### 1. `Font` — `fastobjects/font.py` (modificado)

```python
Font(source: str | Path | None = None, size: int = 24, *,
     chars: str | None = None, charset: str | tuple[str, ...] = "latin")
```

- `source=None` → `ImageFont.load_default(size=size)` (comportamento 0.6.0 intacto).
- `source` str/Path → `ImageFont.truetype(str(source), size=size)` — aceita caminho
  `.ttf`/`.otf` e nomes de fonte do sistema (o Pillow procura em `C:\Windows\Fonts`,
  etc.). `OSError` do Pillow → re-levantada como erro acionável: qual arquivo/nome foi
  tentado e a dica de passar um caminho completo.
- O restante do pipeline (`getmask` → coverage u8 → RGBA branco → `Atlas` → `layout`)
  não muda: `FreeTypeFont` expõe as mesmas APIs (`getmask`, `getlength`, `getbbox`,
  `getmetrics`) que a fonte embutida.
- Novo atributo `Font.source` (o que foi pedido, para repr/debug).

### 2. Charsets — `fastobjects/font.py`

```python
_CHARSETS: dict[str, str] = {
    "ascii":     0x20–0x7E,
    "latin":     ascii + 0xA1–0xFF,        # padrão — o _DEFAULT_CHARS atual
    "latin-ext": latin + 0x100–0x17F,
    "greek":     0x386–0x3CE (imprimíveis),
    "cyrillic":  0x400–0x45F + 0x490–0x491 (Ѐ–џ + Ґґ),
}
```

- `charset=` aceita um nome ou tupla de nomes; a união (sem duplicatas, ordem estável)
  vira o conjunto rasterizado. Nome desconhecido → `ValueError` listando os válidos.
- `chars=` não-None ignora `charset` por completo.
- Guard existente de atlas (`AtlasOverflowError` em 8192px) cobre charsets grandes.

### 3. Benchmark — `benchmarks/text/bench_freetype_gl.py` (novo)

- Implementação canônica freetype-py + PyOpenGL (learnopengl "Text Rendering"):
  `freetype.Face` carrega a `.ttf`, uma textura GL por glifo, um quad + draw call por
  glifo, shader próprio. É a técnica publicada de referência — sem otimizações nossas.
- Mesmo protocolo dos benchmarks de texto existentes: 1280x720, vsync off, seed 42,
  warmup 30 + 120 frames medidos, ramp ×1.5, subprocess próprio, **foreground**
  (Windows limita GL de janelas em background).
- `run_all.py` ganha a coluna; `bench_fastobjects.py` ganha variante com a mesma `.ttf`
  (comparação justa: mesma fonte dos dois lados — ex.: `C:/Windows/Fonts/arial.ttf`).
- Medição extra de load-time: construir o atlas do charset "latin" com `Font(ttf)` vs
  rasterizar os mesmos caracteres com freetype-py puro — tabela em `RESULTS.md`.
- `freetype-py` e `PyOpenGL` entram apenas no extra `[bench]` do `pyproject.toml`.
- Resultados datados em `benchmarks/RESULTS.md`.

### 4. Testes — `tests/test_font.py` (ampliado)

- `.ttf`: `Font("C:/Windows/Fonts/arial.ttf", 24)` com
  `pytest.mark.skipif(not Path(...).exists())` — glifos existem, layout funciona,
  acentos presentes; `Font("nao-existe.ttf")` → erro acionável.
- Charsets: presets são independentes — `charset="cyrillic"` sozinho inclui "Д" e
  **não** inclui "A" (para texto misto usa-se `charset=("latin", "cyrillic")`;
  documentado). Testes: preset sozinho, tupla combinada, nome inválido →
  `ValueError`, e `chars=` vencendo `charset=`.
- Pixel-test em `tests/test_text.py`: `TextBatch` com fonte `.ttf` desenha (skipif).
- Comportamento 0.6.0 permanece: todos os testes atuais passam sem mudança.

### 5. Docs + release

- `docs/site/guide/text.md` + `.pt.md`: seção "Custom fonts / Fontes customizadas"
  (assinatura pygame-like, presets de charset, nota do tofu e do texto misto).
- `docs/site/api.md` + `.pt.md`: assinatura nova de `Font`.
- `docs/site/performance.md` + `.pt.md`: resultado vs freetype-py + OpenGL.
- Bump `0.6.1` (pyproject, `__init__`, smoke test), merge em main, tag `v0.6.1`,
  pre-release GitHub via REST API (token de `git credential fill`, sem gh CLI),
  acompanhar `publish.yml`/docs até success, confirmar PyPI.

## Riscos

- **Gate de throughput:** a técnica quad-por-glifo faz um draw call por caractere —
  a expectativa é vitória larga do batch instanciado; se não vencer, a fase para e
  repensa (regra do usuário).
- **Load-time:** o Pillow também usa FreeType por baixo; diferença esperada pequena.
  Se freetype-py puro for mais rápido para construir o atlas, reportar número e causa.
- **Cobertura de fonte:** arial.ttf cobre latin/greek/cyrillic — bom para testes;
  fontes menores renderizam tofu (documentado, não é erro).
