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
