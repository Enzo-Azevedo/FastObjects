# FastObjects

A biblioteca de renderização de objetos 2D mais rápida do Python.

[**Documentação**](https://enzo-azevedo.github.io/FastObjects/) · [English](README.md)

Sprites sustentados a 60 fps na arena de bunnymark, medidos na mesma máquina
(AMD Radeon RX 580, Python 3.13, 2026-07-07) contra outras bibliotecas de
renderização do Python:

| Framework | Sprites @ 60 fps |
|---|---|
| **fastobjects** | **328.213** |
| arcade | 3.795 |
| raylib | 3.795 |
| pygame-ce | 2.530 |
| pyglet | 2.530 |

Isso é **86x** o concorrente mais próximo. Os números variam entre execuções
por um passo de ramp (±1,5x); veja [`benchmarks/RESULTS.md`](benchmarks/RESULTS.md)
para a série completa datada, a metodologia e o hardware antes de citar um
número como "atual".

## Instalação

```bash
pip install fastobjects
```

Requer Python ≥ 3.11 e OpenGL 3.3 core.

## Começo rápido

```python
import fastobjects as fo

win = fo.Window(800, 600, title="Demo FastObjects")

sprites = fo.SpriteBatch("player.png", capacity=1000)  # qualquer imagem
group = sprites.spawn(1, x=400, y=300)

@win.frame
def update(dt: float) -> None:
    if win.keys[fo.KEY_RIGHT]:
        group.pos[:, 0] += 200 * dt

    win.clear(0.1, 0.1, 0.1)
    win.draw(sprites)

    if win.keys[fo.KEY_ESCAPE]:
        win.request_close()

win.run()
```

- `Window` abre uma janela GLFW nativa com contexto OpenGL 3.3 core e
  comanda o loop de frames (`run()` chama seu callback `@win.frame` a cada
  frame com `dt`). `win.keys[fo.KEY_X]` e `win.mouse` expõem o estado de
  input por polling.
- `SpriteBatch` guarda até `capacity` sprites texturizados; `spawn()`
  retorna um `SpriteGroup` cujos `.pos`, `.size`, `.rot` e `.color` são
  views NumPy do batch — escrever nelas atualiza os sprites diretamente,
  sem overhead por objeto. `batch.despawn(group)` remove um grupo e devolve
  a capacity; os handles dos demais grupos continuam válidos.
- `ShapeBatch` funciona igual para retângulos, círculos e linhas
  (`batch.rects(...)`, `batch.circles(...)`, `batch.lines(...)`) — útil
  para overlays de debug ou geometria sem textura.
- `win.draw(*batches)` emite um draw call por batch, na ordem dada.

## Por que é rápido

Três decisões, cada uma validada por benchmark (todo experimento —
vencedores e perdedores — fica registrado em
[`benchmarks/RESULTS.md`](benchmarks/RESULTS.md)):

1. **Zero objetos Python por sprite.** O estado vive em colunas NumPy planas
   (structure-of-arrays); as atualizações são matemática vetorizada de
   arrays, nunca um loop por objeto.
2. **Um draw call instanciado por batch.** O quad é gerado no vertex shader;
   os atributos por instância vêm de um VBO por coluna.
3. **Você paga pela mudança, não pela existência.** Posições sobem todo
   frame; tamanho, rotação e cor sobem apenas nos frames em que você as
   toca (dirty tracking automático e conservador). Um frame típico sobe
   8 bytes por sprite em vez de 40.

O resultado: com 100.000 objetos em movimento, o FastObjects sustenta
**384 fps** — acima dos 353 fps de um renderer `moderngl` mínimo escrito à
mão, usado como teto de referência da técnica (que paga cópias extras de CPU
por frame que o FastObjects evita).

## Use dentro do pygame

O pygame é dono da janela, dos eventos, do input e do som; o FastObjects é
dono da inserção, atualização, remoção e desenho dos objetos. O desenho
clássico do pygame (`pygame.draw`, `pygame.font`) compõe por cima via
`SurfaceLayer`:

```python
import pygame
import fastobjects as fo

pygame.init()
pygame.display.set_mode((1280, 720), pygame.OPENGL | pygame.DOUBLEBUF)
ext = fo.attach(view_size=(1280, 720))

batch = fo.SpriteBatch("player.png", capacity=10_000)
group = batch.spawn(1000, x=640, y=360)

hud_surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
hud = fo.SurfaceLayer(hud_surface)

while True:
    for event in pygame.event.get():
        ...
    ext.clear(0.1, 0.1, 0.1)
    batch.draw()
    hud.update()
    hud.draw()
    pygame.display.flip()
```

Veja [`examples/pygame_interop.py`](examples/pygame_interop.py) para a
versão completa executável (clique spawna, D remove, HUD com fonte do
pygame).

## Exemplos

- [`examples/bunnymark.py`](examples/bunnymark.py) — 100 mil coelhos
  quicando, janela nativa, contador de FPS.
- [`examples/shapes_input.py`](examples/shapes_input.py) — formas + input
  de teclado/mouse por polling.
- [`examples/pygame_interop.py`](examples/pygame_interop.py) — FastObjects
  renderizando dentro de uma janela pygame.

## Desenvolvimento

Instale com as dependências de desenvolvimento:

```bash
pip install -e ".[dev,bench]"
```

Rode a suíte de testes (98 testes, verificados por pixel contra um contexto
OpenGL offscreen) com `pytest`, e a arena de benchmarks com
`python benchmarks/arena/run_all.py`.
