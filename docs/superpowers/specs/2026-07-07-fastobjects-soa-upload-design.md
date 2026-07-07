# FastObjects — Otimização de upload: SoA + dirty tracking por coluna — Design Spec

**Data:** 2026-07-07
**Status:** Aprovado pelo usuário
**Base:** v0.2.0 (interop lançado; 87 testes; arena 218.809 sprites@60fps)
**Motivação:** `benchmarks/RESULTS.md`, seção "Benchmark externo 2026-07-07" — o
FastObjects entrega 41% do teto do moderngl cru em 100k objetos; o gap é dominado
pelo volume de upload (40 B/instância/frame no layout AoS atual vs 8 B do teto).

## Objetivo

Fechar o gap de upload sem mudar a API pública dos grupos: **você paga pela
mudança, não pela existência**. Todo sprite continua completo (posição, tamanho,
rotação, cor sempre existem, na CPU e na GPU); o que fica leve é o frame — colunas
que não mudaram desde o último draw não são re-enviadas.

**Critérios de aceite:**
- `benchmarks/benchmark_2d.py`: fastobjects ≥ **80% do teto** do moderngl cru em
  100k objetos (hoje 41%: 175,7 vs 429,9 FPS).
- Arena (`run_all.py --save`) sem regressão — esperado melhorar (sprites passam a
  subir 8 B/instância/frame no caso típico, em vez de 36 B).
- Suíte inteira verde (testes que usavam `batch.data` adaptados); pixel tests
  existentes passam sem afrouxar asserts (prova de que a quantização não muda a
  imagem nos casos testados).
- Release **0.3.0** ao final (tag + pre-release GitHub; PyPI via workflow).

## Modelo de custos (a semântica pública da otimização)

1. **Memória: fixa.** Todos os sprites têm todas as propriedades o tempo todo
   (~40 B/sprite na CPU, buffers correspondentes na GPU). Não existem propriedades
   opcionais.
2. **Upload por frame: sob demanda.** `spawn()` sobe tudo uma vez; depois,
   posições sobem sempre (mudam todo frame em app real — mesmo modelo do teto) e
   colunas frias (size/rot/color/kind) só sobem no frame em que foram tocadas.
3. **Granularidade: coluna × batch.** Tocar a rotação de 10 sprites sobe a coluna
   de rotação do batch inteiro naquele frame (quantizada); no frame seguinte volta
   a custar zero. Pior caso (tudo tocado todo frame) ≈ 18 B/instância — nunca pior
   que os 40 B atuais.

## Processo: lab primeiro

`benchmarks/lab/exp_soa_layout.py` (contexto standalone, N=100k, padrão dos labs):

- Cenário 1 — "frame típico": só posições mudam.
- Cenário 2 — "pior caso": todas as colunas mudam todo frame.
- Estratégias: **A** AoS atual (write total de 40 B/inst) — baseline;
  **B** SoA (pos f4 sempre; frias só quando sujas, sem quantização);
  **C** SoA + frias quantizadas (color→4×u8 normalizado, size/rot→f16, kind→f16).
- Variante extra: orphan-vs-write no perfil novo (o cenário de upload mudou desde o
  lab da Fase 1–3; reteste é legítimo por mudança de cenário).
- 5 execuções (lição do lab anterior: ruído run-to-run); decisão registrada em
  `RESULTS.md`; só o vencedor entra no renderer.

## Componentes

### 1. Layout SoA nos batches (`_batchcore.py`, `batch.py`, `shapes.py`)

- `data (capacity, N)` **morre**. Nascem arrays separados, **todos f4 na CPU**
  (o dtype que o usuário toca não muda): `pos (cap, 2)`, `size (cap, 2)`,
  `rot (cap,)`, `color (cap, 4)`; shapes adiciona `kind (cap,)`.
- A quantização é exclusivamente do lado do upload: converte a coluna fria *quando
  suja* (raro) — `color.astype`→u8, `size/rot`→f16. `g.color = (1, 0, 0, 1)`
  continua exatamente igual.
- Física fica mais rápida de graça: `g.pos` vira view contígua (hoje é strided
  sobre linhas de 40 B).
- `despawn` compacta coluna a coluna (uma cópia vetorizada por coluna — mesma
  passada O(cauda), 5 cópias em vez de 1). Regras de realocação de grupos
  inalteradas. `clear`/`spawn`/`despawn` marcam todas as colunas sujas.

### 2. Dirty tracking (conservador, automático)

- Flags por coluna no batch (`_dirty: set[str]` ou bools).
- `SpriteGroup` e as propriedades de batch (`batch.pos` etc. viram properties):
  **acessar** (getter ou setter) marca a coluna suja — conservador de propósito;
  falso-positivo só quando se lê sem escrever (custo: um upload a mais, nunca um
  bug visual de "mudei e não apareceu").
- `pos` não precisa de flag: sobe sempre.
- **Caveat documentado** (docstrings de SpriteGroup e dos batches): não guardar
  uma view entre frames e escrever nela sem reacessar — reacessar é O(1) e mantém
  o rastreamento correto.

### 3. Renderer (`core/renderer.py`, shaders, `shapes.py`)

- VAO com **um VBO por atributo** (pos f4; size/rot/color/kind nos formatos
  vencedores do lab — ex.: `"4f1"` para cor u8 normalizada, `"2f2"` para size f16).
- `render(...)` recebe os arrays + o conjunto de colunas sujas: sobe pos sempre e
  as sujas; limpa as flags após subir.
- Shaders: mesmos VS/FS (atributos normalizados chegam como float no shader —
  nenhuma mudança de matemática). Pixel tests atuais passam sem mudança.

### 4. Consumidores internos

- `SurfaceLayer`: instância única e estática — adapta para o novo renderer; sobe
  tudo uma vez e nunca mais (só a textura muda via `update()`).
- `bench_fastobjects.py`/exemplo pygame: nenhuma mudança de código (usam a API de
  grupos); ganham o novo caminho de graça.

### 5. Quebras (pré-1.0)

- `batch.data` removido (era `(capacity, N)` f4). Substituto: as propriedades
  `batch.pos/size/rot/color` (agora properties que marcam sujo) e as views dos
  grupos. Testes que indexavam `data` são adaptados no mesmo task.
- `SpriteGroup` muda por dentro (indexa os arrays SoA via um mapeamento
  coluna→array do batch); API externa idêntica (x/y/w/h/rot/pos/size/color,
  slicing, len, invalidação).
- `SpriteRenderer`/`_ShapeRenderer` mudam de assinatura (interno).

## Tratamento de erros

Sem novas classes de erro. Comportamentos existentes (capacity, despawn, grupos
inválidos, texturas) inalterados — as mensagens atuais são preservadas byte a byte.

## Testes

- Suíte atual (87) passa com adaptações mecânicas onde `batch.data` era usado —
  pixel tests intactos (asserts inalterados).
- Novos testes: dirty tracking (tocar color marca e o próximo draw reflete o valor
  na tela — pixel test; frame seguinte sem toque não re-sobe — verificado por
  contador interno de uploads exposto para teste, ex.: `_renderer.uploads`),
  quantização (cor u8 exata para 0/0.5/1; rotação f16 num pixel test de diagonal),
  despawn/clear/spawn marcam tudo, física em view contígua (semântica igual).
- Lab: `exp_soa_layout.py` roda 5x e imprime a tabela; resultado no RESULTS.md.
- Aceite final: benchmark_2d completo (foreground!) + arena `--save`.

## Fora de escopo

- `opaque=True` (blend opcional) — ganho não dominante; YAGNI por ora.
- Texture atlas, hosts pyglet/arcade/raylib, docs — fases próprias.

## Execução

Inline nesta sessão (superpowers:executing-plans), branch própria, sem subagentes
(pedido do usuário). Release 0.3.0 pós-merge (tag + pre-release via REST API;
PyPI automático).
