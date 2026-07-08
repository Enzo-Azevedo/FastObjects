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
