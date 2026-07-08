# Formas

`ShapeBatch` renderiza primitivas sem textura — retângulos, círculos e
linhas — com o mesmo modelo dos sprites: estado NumPy, grupos e **um draw
call instanciado para o batch inteiro**, formas misturadas incluídas.

```python
import fastobjects as fo

win = fo.Window(800, 600)
shapes = fo.ShapeBatch(capacity=1000)

bars = shapes.rects(3, x=[100.0, 200.0, 300.0], y=500.0, w=40.0, h=120.0,
                    color=(0.2, 0.8, 0.3, 1.0))
dots = shapes.circles(50, x=..., y=..., radius=6.0)
grid = shapes.lines(2, x1=[0.0, 400.0], y1=[300.0, 0.0],
                    x2=[800.0, 400.0], y2=[300.0, 600.0], width=1.0)
```

As três fábricas são vetorizadas como o `spawn` (escalares ou arrays de
tamanho `n`) e retornam o mesmo tipo `SpriteGroup` — `bars.rot += 0.1` e
`shapes.despawn(dots)` funcionam exatamente como com sprites.

## As três primitivas

**Retângulos** — `rects(n, x, y, w, h, rot=0.0, color=...)`. A posição é o
centro; `rot` em radianos.

**Círculos** — `circles(n, x, y, radius, color=...)`. Renderizados como
campo de distância (SDF) no fragment shader com bordas anti-aliased de
~1px — nítidos em qualquer tamanho, sem segmentos de polígono.
Internamente o bounding box guarda o diâmetro, então `grupo.size`
lê/escreve `2 * radius`.

**Linhas** — `lines(n, x1, y1, x2, y2, width=1.0, color=...)`. Linhas são
açúcar da API: os endpoints são convertidos (vetorizado) num retângulo
rotacionado com a largura dada. Mover uma linha depois significa mover o
centro (`grupo.pos`) ou recriá-la.

## Misturando formas

Primitivas diferentes compartilham o mesmo batch e o mesmo draw call:

```python
shapes.rects(1, x=400.0, y=100.0, w=200.0, h=20.0, color=(0.9, 0.2, 0.2, 1.0))
shapes.circles(1, x=400.0, y=300.0, radius=50.0, color=(0.2, 0.5, 0.9, 0.8))
shapes.draw()   # um draw call para as duas
```

O blending de alpha é o mesmo dos sprites (alpha reto).

## Um exemplo completo

```python
import fastobjects as fo

win = fo.Window(800, 600, title="guia de formas")
shapes = fo.ShapeBatch(capacity=64)

spinner = shapes.rects(1, x=400.0, y=300.0, w=160.0, h=24.0,
                       color=(1.0, 0.6, 0.1, 1.0))
shapes.circles(1, x=400.0, y=300.0, radius=8.0, color=(1.0, 1.0, 1.0, 1.0))

@win.frame
def update(dt: float) -> None:
    spinner.rot += 1.5 * dt
    win.clear(0.08, 0.08, 0.10)
    win.draw(shapes)
    if win.keys[fo.KEY_ESCAPE]:
        win.request_close()

win.run()
```
