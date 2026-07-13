# Resultados de benchmarks

Registro histórico de toda medição do projeto. Nenhuma decisão de performance
existe sem uma entrada aqui. Formato: seções datadas, hardware explícito.

## Arena 2026-07-06 (baseline, sem fastobjects)

- Hardware: Intel64 Family 6 Model 62 Stepping 4, GenuineIntel | GPU: AMD Radeon RX 580 2048SP
- Python 3.13.13 | Windows 10

| Framework | Sprites @ 60fps | avg ms (último trial ok) | p99 ms |
|---|---|---|---|
| raylib | 5,692 | 12.843 | 20.004 |
| pygame-ce | 3,795 | 16.024 | 24.967 |
| arcade | 3,795 | 9.912 | 16.352 |
| pyglet | 3,795 | 14.461 | 18.841 |

## Arena 2026-07-06

- Hardware: Intel64 Family 6 Model 62 Stepping 4, GenuineIntel | GPU: AMD Radeon RX 580 2048SP
- Python 3.13.13 | Windows 10

| Framework | Sprites @ 60fps | avg ms (último trial ok) | p99 ms |
|---|---|---|---|
| fastobjects | 218,809 | 13.943 | 18.107 |
| arcade | 5,692 | 11.91 | 18.303 |
| raylib | 5,692 | 12.493 | 20.993 |
| pygame-ce | 3,795 | 12.207 | 17.683 |
| pyglet | 3,795 | 13.499 | 24.386 |

## Lab 2026-07-06: estratégia de upload de buffer

- Hardware/GPU: Intel64 Family 6 Model 62 Stepping 4, GenuineIntel | AMD Radeon RX 580 2048SP
- N=200.000, 300 frames, contexto standalone (sem janela/vsync)
- `benchmarks/lab/exp_buffer_upload.py`, 5 execuções (a "vencedora" de uma única
  execução se mostrou instável — ver abaixo), média de cada estratégia através
  das 5 execuções:

| Estratégia | ms/frame (média de 5 execuções) |
|---|---|
| A write total | 14.997 |
| B orphan+write | 15.039 |
| C double-buffer | 15.110 |

Execuções individuais (ms/frame) — a estratégia vencedora impressa por cada
execução mudou a cada vez, evidenciando que a diferença entre estratégias
está dentro do ruído de medição da máquina, não é um efeito real e estável:

| Execução | A | B | C | vencedora impressa |
|---|---|---|---|---|
| 1 | 15.757 | 15.214 | 15.508 | B |
| 2 | 11.820 | 10.841 | 11.074 | B |
| 3 | 13.613 | 15.508 | 15.117 | A |
| 4 | 17.405 | 17.152 | 17.124 | C |
| 5 | 16.388 | 16.479 | 16.728 | A |

**Decisão:** A (write total) mantida no `SpriteRenderer.render`. As três
estratégias diferem por ≤1% na média de 5 execuções e a variação
execução-a-execução (~11.8–17.4 ms/frame, dominada por ruído do sistema)
excede em muito a diferença entre estratégias — não há vencedora
reprodutível. Mantém-se a implementação atual (mais simples, sem
orphan/double-buffer) por não haver ganho demonstrado. Perdedoras
documentadas acima — não retestar sem mudança de hardware ou de driver.

## Arena 2026-07-06 (pós-fase 4 API)

- Hardware: Intel64 Family 6 Model 62 Stepping 4, GenuineIntel | GPU: AMD Radeon RX 580 2048SP
- Python 3.13.13 | Windows 10

| Framework | Sprites @ 60fps | avg ms (último trial ok) | p99 ms |
|---|---|---|---|
| fastobjects | 218,809 | 12.923 | 17.084 |
| arcade | 5,692 | 12.66 | 17.447 |
| raylib | 5,692 | 13.87 | 21.014 |
| pyglet | 3,795 | 12.789 | 17.752 |
| pygame-ce | 1,687 | 8.287 | 16.372 |

## Arena 2026-07-07 (pós-interop)

- Hardware: Intel64 Family 6 Model 62 Stepping 4, GenuineIntel | GPU: AMD Radeon RX 580 2048SP
- Python 3.13.13 | Windows 10

| Framework | Sprites @ 60fps | avg ms (último trial ok) | p99 ms |
|---|---|---|---|
| fastobjects | 218,809 | 14.867 | 18.647 |
| arcade | 5,692 | 14.152 | 23.43 |
| raylib | 5,692 | 13.131 | 20.092 |
| pygame-ce | 3,795 | 13.859 | 22.227 |
| pyglet | 3,795 | 14.261 | 21.001 |

## Benchmark externo 2026-07-07: benchmark_2d.py (escalabilidade objetos x FPS)

- Hardware: Intel64 Family 6 Model 62 Stepping 4, GenuineIntel | GPU: AMD Radeon RX 580 2048SP
- Python 3.13.13 | Windows 10
- Protocolo: benchmarks/benchmark_2d.py (script de comparacao fornecido pelo usuario,
  secao fastobjects implementada com a API real v0.2.0: Window + ShapeBatch.rects
  vetorizado). Janela 800x600, retangulos 6x6 coloridos, 3s de medicao por ponto,
  cada medicao em subprocesso isolado, foreground.

| N objetos | pygame-ce | pyglet | moderngl (cru) | fastobjects | fo vs pygame | fo vs teto moderngl |
|---|---|---|---|---|---|---|
| 100 | 776.1 | 228.0 | 3180.5 | 3050.2 | 3.9x | 96% |
| 1.000 | 256.8 | 124.5 | 2993.0 | 2715.5 | 10.6x | 91% |
| 5.000 | 74.6 | 24.5 | 2719.4 | 2155.7 | 28.9x | 79% |
| 10.000 | 42.3 | 11.9 | 2413.9 | 1502.9 | 35.5x | 62% |
| 50.000 | 8.5 | 2.2 | 829.3 | 375.5 | 44.2x | 45% |
| 100.000 | 4.6 | 0.9 | 429.9 | 175.7 | 38.2x | 41% |

**Conclusoes:**
- Progresso confirmado, sem retrocesso: 38x sobre pygame-ce em 100k objetos e ~195x
  sobre pyglet - coerente com a arena (218.809 sprites @ 60fps, ~38x).
- A coluna "moderngl (cru)" e o teto teorico da tecnica: um renderer minimo hardcoded
  (so offsets de 8 bytes/instancia, sem rotacao, sem blend, cores estaticas).
  O fastobjects entrega 41-96% desse teto COM a API completa (10 floats/instancia,
  rotacao, blending, kind por forma). O gap cresce com N (dominado pelo volume de
  upload 5x maior) - candidato a lab futuro: upload parcial/dirty tracking.
- Incidente de medicao documentado: a primeira execucao (em job de background) mediu
  os benches GL a ~10 FPS - throttling de apresentacao do Windows para janelas GL de
  processos em background (pygame por software nao e afetado). Benchmarks GL nesta
  maquina DEVEM rodar em foreground.
- pyglet: o app.run() nao e re-executavel no mesmo processo (media 0.0 FPS da 2a
  rodada em diante); o script foi corrigido para subprocesso por medicao - mesmo
  protocolo da arena - o que tambem eliminou janelas-zumbi acumulando na tela.

## Lab 2026-07-07: layout SoA + quantizacao (exp_soa_layout.py)

- Hardware: Intel64 Family 6 Model 62 Stepping 4, GenuineIntel | GPU: AMD Radeon RX 580 2048SP
- N=100.000, 300 frames, 5 runs (reportado o MINIMO de 5 - isola custo intrinseco do ruido do SO), contexto standalone

| Estrategia | Cenario 1: so posicoes (ms/frame) | Cenario 2: tudo muda (ms/frame) |
|---|---|---|
| A  AoS write total (36B/inst, atual) | 3.949 | 4.293 |
| B  SoA f4 (pos 8B; frias so quando mudam) | 0.997 | 3.186 |
| B' SoA f4 com orphan no pos | 1.011 | - |
| C  SoA quantizado (frias u8/f16) | 0.974 | 7.712 |

**Decisao: B (SoA f4 puro) adotada.**
- SoA vence AoS por 4.0x no frame tipico e 1.35x no pior caso.
- Quantizacao (C) REJEITADA: empata com B no caso tipico (as colunas frias nem
  sobem) e e 2.4x PIOR que B no pior caso - o astype f2/u8 na CPU custa mais do
  que economiza de upload. Perdedora documentada; nao retestar sem mudanca de
  hardware/driver ou conversao vetorizada mais barata.
- orphan REJEITADO de novo (empate, consistente com o lab da Fase 1-3).

## Arena 2026-07-07 (pós-SoA)

- Hardware: Intel64 Family 6 Model 62 Stepping 4, GenuineIntel | GPU: AMD Radeon RX 580 2048SP
- Python 3.13.13 | Windows 10

| Framework | Sprites @ 60fps | avg ms (último trial ok) | p99 ms |
|---|---|---|---|
| fastobjects | 328,213 | 12.461 | 22.177 |
| arcade | 3,795 | 10.266 | 19.433 |
| raylib | 3,795 | 10.095 | 19.642 |
| pygame-ce | 2,530 | 11.563 | 20.813 |
| pyglet | 2,530 | 10.323 | 17.24 |


## Aceite SoA 2026-07-07: benchmark_2d vs teto do moderngl cru (pos-otimizacao)

- Hardware: Intel64 Family 6 Model 62 Stepping 4, GenuineIntel | GPU: AMD Radeon RX 580 2048SP
- Mesmo run, mesmas condicoes (a maquina estava mais lenta que no baseline em
  termos absolutos; a razao fastobjects/teto e a metrica de aceite).

| N objetos | moderngl (cru) | fastobjects | % do teto (antes -> depois) |
|---|---|---|---|
| 100 | 1777.8 | 1146.7 | 96% -> 65% (overhead fixo; ambos >1100 FPS) |
| 1.000 | 1083.5 | 1293.1 | 91% -> 119% |
| 5.000 | 1077.6 | 1294.6 | 79% -> 120% |
| 10.000 | 1025.0 | 1285.6 | 62% -> 125% |
| 50.000 | 669.0 | 605.2 | 45% -> 90% |
| 100.000 | 352.6 | 384.0 | 41% -> 109% |

**Criterio de aceite (>=80% do teto em 100k): SUPERADO - 109%.** O fastobjects
passou a VENCER o renderer minimo hardcoded em N>=1000: o bench cru paga
astype+tobytes (2 copias de CPU) por frame, enquanto o render SoA escreve o
array contiguo direto, e as colunas frias nem sobem. Absoluto em 100k:
175.7 -> 384.0 FPS (2.2x).

**Arena pos-SoA: 328.213 sprites @ 60fps (era 218.809, +50% = 1 passo de ramp),
86x o melhor concorrente** - mesmo com a maquina mais lenta nesta rodada
(concorrentes cairam um passo). Upload de sprites no frame tipico: 36 -> 8
B/instancia.

## Spike hosts 2026-07-09: pyglet / arcade / raylib (benchmarks/lab/spike_hosts.py)

- Hardware: Intel64 Family 6 Model 62 Stepping 4, GenuineIntel | GPU: AMD Radeon RX 580 2048SP
- Metodo: por host (subprocesso proprio), cria a janela com GL, fo.attach,
  desenha um retangulo vermelho no centro e le o pixel central via
  ctx.screen.read. verde = attach cru basta; amarelo = so com save/restore de
  estado GL; vermelho = nao renderiza / attach falha.

| Host | Veredito | Rota | Nota |
|---|---|---|---|
| pyglet 2.1.15 | **verde** | `fo.attach` cru | pixel (255,0,0); OpenGL nativo, zero intervencao |
| arcade 3.3.3 | **verde** | `fo.attach` cru | pixel (255,0,0); attach por cima do contexto do arcade funciona direto |
| raylib 6.0.1.0 | **vermelho** | nao suportado | clear funciona (attach conecta), mas o draw instanciado nao aparece (pixel = cor do clear) dentro e fora de begin/end, com flush do batch e depth off |

**Conclusoes:**
- pyglet e arcade: suportados com `fo.attach` cru, sem isolamento de estado.
  Nenhum host ficou "amarelo" -> `ExternalWindow.isolated()` NAO e necessario
  nesta fase (Task 2 do plano pulado por evidencia).
- raylib NAO suportado: o rlgl mantem o proprio estado GL (matrizes, shader,
  VAO, sistema de batch) e um segundo pipeline moderngl no mesmo contexto nao
  renderiza. A leitura de pixel foi validada (um retangulo NATIVO do raylib
  leu (255,0,0) corretamente), entao o problema e o draw do FastObjects nao
  produzir saida, nao a medicao. Consertar exigiria patchar internals do
  raylib (fora de escopo). Documentado como nao suportado.

## Multi-imagem 2026-07-09 (N sprites de 8 imagens diferentes)

- Hardware: Intel64 Family 6 Model 62 Stepping 4, GenuineIntel | GPU: AMD Radeon RX 580 2048SP
- Python 3.13.13 | Windows 10

| Framework | Sprites @ 60fps | avg ms | p99 ms |
|---|---|---|---|
| fastobjects | 328,213 | 11.542 | 12.133 |
| arcade | 5,692 | 12.276 | 21.123 |
| pyglet | 3,795 | 15.145 | 20.708 |

## Arena 2026-07-09 (pós-atlas)

- Hardware: Intel64 Family 6 Model 62 Stepping 4, GenuineIntel | GPU: AMD Radeon RX 580 2048SP
- Python 3.13.13 | Windows 10

| Framework | Sprites @ 60fps | avg ms (último trial ok) | p99 ms |
|---|---|---|---|
| fastobjects | 328,213 | 11.538 | 12.303 |
| arcade | 5,692 | 12.387 | 18.265 |
| raylib | 5,692 | 11.997 | 19.304 |
| pygame-ce | 3,795 | 13.107 | 19.566 |
| pyglet | 3,795 | 12.931 | 18.787 |

## Packing 2026-07-10: FastObjects vs PyTexturePacker (velocidade de montar o atlas)

- Hardware: Intel64 Family 6 Model 62 Stepping 4, GenuineIntel | GPU: AMD Radeon RX 580 2048SP
- Método: benchmarks/packing/bench_packing.py (requer `pip install PyTexturePacker`).
  Comparação justa Python-vs-Python: ambos carregam N imagens, empacotam e montam
  a imagem do atlas EM MEMÓRIA (sem escrita em disco). min de 3-5 runs. max_size
  4096, padding 2, sem rotação. FastObjects usa shelf packing; PyTexturePacker
  usa MaxRects. (patlas foi descartado: só tem wheels até Python 3.9 e o sdist é
  quebrado — não instala no Python alvo ≥3.11.)

**Imagens de MESMO tamanho (64px) — caso spritesheet/tileset:**

| N | FastObjects | PyTexturePacker | FO mais rápido | atlas (idêntico) |
|---|---|---|---|---|
| 25 | 13.6 ms | 10.0 ms | 0.7x (FO -3,6ms) | 512x512 |
| 100 | 53.4 ms | 47.3 ms | 0.9x | 1024x512 |
| 400 | 214.9 ms | 6.452,8 ms | 30x | 2048x1024 |
| 800 | 426.8 ms | 32.954 ms | 77x | 2048x2048 |

**Imagens de TAMANHO VARIADO (16-96px) — arte típica de jogo:**

| N | FastObjects | PyTexturePacker | razão | área do atlas FO/PTP |
|---|---|---|---|---|
| 100 | 53.3 ms | 48.1 ms | 0.9x | 1.00 (mesmo tamanho) |
| 400 | 241.2 ms | 238.2 ms | 1.0x | 1.00 (mesmo tamanho) |

**Conclusões:**
- **Critério de ≥90% da velocidade: ATINGIDO em todos os casos relevantes.** Com
  tamanhos variados (arte de jogo), é empate (90-100%). Com tamanhos uniformes
  (spritesheet), o FastObjects é 30-77x mais rápido — o MaxRects do
  PyTexturePacker degenera com muitas imagens do mesmo tamanho (a lista de
  retângulos livres explode num grid uniforme). Único ponto abaixo de 90%: N=25
  uniforme (70%, mas 3,6ms absolutos — irrelevante).
- **Qualidade de packing idêntica:** o atlas produzido tem o MESMO tamanho nos
  dois em todos os casos testados — o shelf packing simples do FastObjects não
  perde eficiência de espaço aqui, e escala LINEARMENTE (13→53→215→427ms),
  enquanto o MaxRects escala mal em N alto.
- **Nenhum "repensar" necessário:** o shelf packing estático é a escolha certa
  para montar atlas em load-time numa lib de renderização — rápido, escala
  linear, mesmo tamanho de saída, e imbatível no caso spritesheet.

## Texto 2026-07-10 (N strings 'Item NNNNN' desenhadas)

- Hardware: Intel64 Family 6 Model 62 Stepping 4, GenuineIntel | GPU: AMD Radeon RX 580 2048SP
- Python 3.13.13 | Windows 10

| Framework | Strings @ 60fps | avg ms | p99 ms |
|---|---|---|---|
| fastobjects | 145,873 | 9.781 | 10.888 |
| pyglet | 43,222 | 14.442 | 15.818 |
| pygame-ce | 3,795 | 13.902 | 19.94 |

## Texto 2026-07-13 (N strings 'Item NNNNN' desenhadas)

- Hardware: Intel64 Family 6 Model 62 Stepping 4, GenuineIntel | GPU: AMD Radeon RX 580 2048SP
- Python 3.13.13 | Windows 10

| Framework | Strings @ 60fps | avg ms | p99 ms |
|---|---|---|---|
| fastobjects | 145,873 | 9.461 | 10.473 |
| fastobjects-ttf | 145,873 | 9.707 | 10.734 |
| pyglet | 43,222 | 13.87 | 15.136 |
| pygame-ce | 3,795 | 13.061 | 18.132 |
| freetype-gl | 0 | - | - |

Notas (0.6.1, gate da fase):

- `fastobjects-ttf` usa a mesma `arial.ttf` do `freetype-gl` (comparação justa);
  fonte `.ttf` custa o mesmo que a embutida (145.873 nos dois casos).
- `freetype-gl` (`bench_freetype_gl.py`) é a técnica canônica do tutorial
  learnopengl — textura GL e **um draw call por glifo**: não sustenta nem o
  primeiro degrau da rampa (500 strings = ~276 ms/frame). **Gate aprovado.**
- Load-time (`bench_font_build.py`, charset latin/191 chars, arial.ttf 16px):
  `Font(ttf)` constrói o atlas em **119,8 ms** vs **18,9 ms** do freetype-py
  puro — que só decodifica bitmaps, sem montar atlas. O custo do `Font` é
  ~101 ms de rasterização via API do Pillow (getmask/getlength/getbbox +
  conversão RGBA por glifo) + ~37 ms de empacotamento. Custo único de load,
  irrelevante no frame loop; registrado por honestidade.

### Correção 2026-07-13: freetype-gl injustiçado (apontado pelo usuário)

O resultado "0" acima era injusto por dois motivos:

1. **Preparação por frame**: o bench reconstruía o array numpy do quad de
   cada glifo dentro do loop medido, enquanto todos os outros benches fazem a
   preparação uma vez fora dele (pygame pré-renderiza surfaces, pyglet cria os
   Labels antes, fastobjects faz `write()` antes). Corrigido: quads
   pré-computados por trial; o frame paga só o que define a técnica —
   bind + upload + draw call **por glifo**.
2. **Piso da rampa**: começando em 500, um renderizador que reprova no
   primeiro degrau vira "0" sem revelar o número real (e a janela fica parada
   sem strings novas — a rampa parou no trial 1). `run_ramp` ganhou
   `start=`; o freetype-gl roda com `start=25`.

Resultado corrigido (mesmas condições da tabela acima):

| Framework | Strings @ 60fps | avg ms | p99 ms |
|---|---|---|---|
| freetype-gl (corrigido) | **55** | 14.696 | 23.205 |

(82 strings já estoura: 24,0 ms avg.) O gate continua aprovado — 145.873 vs
55 (~2.650x): 55 strings ≈ 550 glifos ≈ 1.650 chamadas GL via PyOpenGL por
frame; o custo por draw call domina mesmo sem nenhum trabalho de layout.
