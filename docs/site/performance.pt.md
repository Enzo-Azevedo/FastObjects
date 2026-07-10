# Performance

## A arena de bunnymark

Toda biblioteca listada roda o *mesmo* bunnymark — física, timer e protocolo
de ramp idênticos — no próprio processo, então a renderização é a única
variável. Cada uma usa seu caminho rápido documentado. Sprites sustentados a
60 fps (AMD Radeon RX 580, Python 3.13, 2026-07-07):

| Framework | Sprites @ 60 fps | avg ms | p99 ms |
|---|---|---|---|
| **fastobjects** | **328.213** | 12,5 | 22,2 |
| arcade | 3.795 | 10,3 | 19,4 |
| raylib | 3.795 | 10,1 | 19,6 |
| pygame-ce | 2.530 | 11,6 | 20,8 |
| pyglet | 2.530 | 10,3 | 17,2 |

## Contra o teto da técnica

Um renderer `moderngl` mínimo escrito à mão (instancing cru, sem biblioteca,
sem rotação, sem blend) é o teto teórico desta técnica. Num varrimento de
escalabilidade (800×600, retângulos 6×6), o FastObjects alcança — e passa —
esse teto, porque escreve arrays contíguos direto enquanto a versão crua paga
cópias `astype`/`tobytes` por frame:

| Objetos | moderngl (cru) | fastobjects | % do teto |
|---|---|---|---|
| 1.000 | 1.084 fps | 1.293 fps | 119% |
| 10.000 | 1.025 fps | 1.286 fps | 125% |
| 100.000 | 353 fps | 384 fps | 109% |

## Velocidade de packing de atlas

Montar um texture atlas é um passo de load-time. Contra o
[PyTexturePacker](https://pypi.org/project/PyTexturePacker/) (um packer MaxRects
em Python puro), o shelf packing do FastObjects produz um atlas do **mesmo
tamanho** e é bem mais rápido em imagens de mesmo tamanho (spritesheets): 30x em
400 imagens, 77x em 800 — a lista de retângulos livres do MaxRects degenera em
grids uniformes. Em arte de tamanhos variados os dois empatam, e o FastObjects
escala linearmente. Números completos em
[`benchmarks/RESULTS.md`](https://github.com/Enzo-Azevedo/FastObjects/blob/main/benchmarks/RESULTS.md).
(o patlas foi descartado da comparação: não tem wheels além do Python 3.9 e o
sdist não compila.)

## Throughput de texto

Texto são sprites de um atlas de glifos em um draw call. Desenhando muitas
strings curtas, o FastObjects sustenta **145.873 strings @ 60 fps** — 3,4x o
pyglet (que também usa atlas de glifos, mas vertex lists por label) e 38x o
pygame (uma surface nova por string).

## Reproduza

```bash
# A arena completa (5 bibliotecas, salva uma seção datada no RESULTS.md)
python benchmarks/arena/run_all.py --save --label "meu-run"

# O varrimento de escalabilidade vs o teto do moderngl cru
python benchmarks/benchmark_2d.py --libs moderngl fastobjects
```

!!! warning "Rode benchmarks em foreground"
    O Windows estrangula a apresentação OpenGL de janelas de processos em
    background (~10 fps), o que arruína silenciosamente os números de
    benchmarks GL. O caminho por software do pygame não é afetado, então o
    desvio é fácil de passar despercebido. Sempre rode estes em foreground.

## A filosofia: nenhuma decisão sem benchmark

O FastObjects não toma decisão de performance por opinião — toda técnica
candidata precisa vencer nos números medidos, e os resultados (vencedores
*e* perdedores) ficam registrados com data e hardware em
[`benchmarks/RESULTS.md`](https://github.com/Enzo-Azevedo/FastObjects/blob/main/benchmarks/RESULTS.md).
Exemplos desse registro:

- **Estratégia de upload de buffer** — `write` simples vs `orphan` vs
  double-buffer: sem vencedor reproduzível, então o mais simples (`write`
  simples) foi mantido.
- **SoA vs AoS + quantização** — structure-of-arrays com um VBO por coluna
  venceu os arrays interleaved por 4x num frame típico; quantizar colunas
  frias para u8/f16 *perdeu* (a conversão na CPU custou mais que o upload
  que economizava) e foi rejeitada.

## Dicas práticas

- **Um batch por textura.** Sprites de um batch compartilham textura e draw
  call; agrupe sua arte de acordo.
- **Vetorize.** Atualize grupos inteiros com matemática de array
  (`grupo.pos += v * dt`), nunca um loop Python sobre sprites.
- **Prefira `despawn` a clear-and-respawn.** O `despawn` devolve capacity
  com uma compactação vetorizada e mantém os outros handles válidos.
- **Toque colunas frias só quando mudam.** As posições sobem todo frame de
  qualquer forma; reatribuir cor/tamanho/rotação todo frame quando são
  estáticos desperdiça uploads (continua correto, só mais lento).
