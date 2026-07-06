# Resultados de benchmarks

Registro histórico de toda medição do projeto. Nenhuma decisão de performance
existe sem uma entrada aqui. Formato: seções datadas, hardware explícito.

## Arena 2026-07-06

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
