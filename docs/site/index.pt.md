# FastObjects

**A biblioteca de renderização de objetos 2D mais rápida do Python.** Sprites
e formas vivem em arrays NumPy planos — nunca um objeto Python por sprite —
e cada batch é desenhado com um único draw call OpenGL instanciado.

## Os números

Sprites sustentados a 60 fps na arena de bunnymark, mesma máquina
(AMD Radeon RX 580, Python 3.13, 2026-07-07):

| Framework | Sprites @ 60 fps |
|---|---|
| **fastobjects** | **328.213** |
| arcade | 3.795 |
| raylib | 3.795 |
| pygame-ce | 2.530 |
| pyglet | 2.530 |

**86x** o concorrente mais próximo. Todo número desta documentação vem de uma
entrada datada e reproduzível em
[`benchmarks/RESULTS.md`](https://github.com/Enzo-Azevedo/FastObjects/blob/main/benchmarks/RESULTS.md) —
incluindo os experimentos que *perderam*.

## Instalação

```bash
pip install fastobjects
```

## Por onde continuar

- [Começando](getting-started.md) — instalação e o primeiro programa.
- [Sprites & Grupos](guide/sprites.md) — batches, spawn/despawn vetorizados
  e o modelo de custos que traz a velocidade.
- [Formas](guide/shapes.md) — retângulos, círculos SDF e linhas.
- [Janela & Input](guide/window-input.md) — o loop de frames e o input por
  polling.
- [Usando dentro do pygame](guide/interop.md) — o pygame é dono da janela,
  o FastObjects é dono dos objetos.
- [Performance](performance.md) — os benchmarks e como reproduzi-los.
- [Referência da API](api.md) — todos os símbolos públicos.
