# Usando dentro do pygame

O FastObjects pode renderizar **dentro de uma janela criada por outra
biblioteca**. O host (pygame aqui) é dono da janela, do loop de eventos, do
input e do som; o FastObjects é dono da inserção, atualização, remoção e
desenho dos objetos. O desenho clássico do pygame compõe por cima.

## O único requisito: uma janela OpenGL

O pygame precisa criar a janela com contexto OpenGL — é a única mudança em
relação a um setup pygame normal:

```python
import pygame
import fastobjects as fo

pygame.init()
pygame.display.set_mode((1280, 720), pygame.OPENGL | pygame.DOUBLEBUF)
ext = fo.attach(view_size=(1280, 720))
```

`fo.attach()` conecta o FastObjects ao contexto OpenGL corrente do host e o
registra como janela atual, então batches criados depois funcionam
exatamente como no modo nativo. Chame-o **uma vez por janela**. Se não
houver contexto GL, ele levanta um `RuntimeError` mandando adicionar a flag
`OPENGL`.

## Quem é dono de quê

| Responsabilidade | Dono |
|---|---|
| Janela, loop de eventos, `flip()` | pygame |
| Teclado, mouse, som | pygame |
| Estado de sprites/formas, update, render | FastObjects |
| Desenho 2D clássico (`pygame.draw`, `pygame.font`) | pygame → composto via `SurfaceLayer` |

O `ExternalWindow` (retornado por `attach`) expõe de propósito apenas
`.ctx`, `.width`, `.height`, `.clear(r, g, b)` e `.close()` — sem loop de
frames, sem input, porque isso pertence ao host.

## Compondo o desenho do pygame: SurfaceLayer

Desenhe seu HUD, texto ou arte vetorial numa `pygame.Surface` normal e
componha-a na GPU junto com os batches:

```python
hud_surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
hud = fo.SurfaceLayer(hud_surface)
font = pygame.font.Font(None, 28)

# a cada frame:
hud_surface.fill((0, 0, 0, 0))
hud_surface.blit(font.render("score: 42", True, (255, 255, 255)), (10, 10))
hud.update()   # sobe a surface para a GPU (um upload)
hud.draw()     # compõe (um draw call)
```

`update()` precisa do pygame instalado (importado de forma preguiçosa, então
o pygame nunca vira dependência do próprio FastObjects).

## Loop completo

```python
import pygame
import fastobjects as fo

pygame.init()
pygame.display.set_mode((1280, 720), pygame.OPENGL | pygame.DOUBLEBUF)
ext = fo.attach(view_size=(1280, 720))

batch = fo.SpriteBatch("player.png", capacity=200_000)
groups = []

hud_surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
hud = fo.SurfaceLayer(hud_surface)
font = pygame.font.Font(None, 28)

clock = pygame.time.Clock()
running = True
while running:
    dt = clock.tick() / 1000.0
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            groups.append(batch.spawn(100, x=float(event.pos[0]), y=float(event.pos[1])))
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_d and groups:
            batch.despawn(groups.pop())   # remoção real, devolve capacity

    hud_surface.fill((0, 0, 0, 0))
    hud_surface.blit(font.render(f"sprites: {batch.count}", True, (255, 255, 255)), (10, 10))

    ext.clear(0.08, 0.08, 0.10)
    batch.draw()
    hud.update()
    hud.draw()
    pygame.display.flip()

pygame.quit()
```

A versão completa executável é
[`examples/pygame_interop.py`](https://github.com/Enzo-Azevedo/FastObjects/blob/main/examples/pygame_interop.py).

!!! info "Por que não fazer blit do FastObjects sobre o pygame clássico?"
    Uma janela OpenGL assume a apresentação — a surface de software do SDL
    não chega mais à tela (isso vale para qualquer API de GPU, Vulkan
    incluído). Então a composição vai no sentido inverso: o pygame desenha
    numa Surface e o FastObjects a compõe. Você mantém todas as ferramentas
    de desenho do pygame; só apresenta via OpenGL.

## Outros hosts

O `fo.attach()` funciona com *qualquer* contexto OpenGL corrente, então o
pygame é só o exemplo documentado. Estes hosts foram validados com janela real
(o [spike](https://github.com/Enzo-Azevedo/FastObjects/blob/main/benchmarks/lab/spike_hosts.py)
está no repositório, resultados em `benchmarks/RESULTS.md`):

| Host | Status |
|---|---|
| pygame (OpenGL) | ✅ Suportado |
| pyglet | ✅ Suportado |
| arcade | ✅ Suportado |
| raylib (pyray) | ❌ Não suportado |

**pyglet** — uma janela pyglet já é OpenGL, então o `attach` simplesmente
funciona:

```python
import pyglet
import fastobjects as fo

win = pyglet.window.Window(900, 600)
ext = fo.attach(view_size=(900, 600))
batch = fo.SpriteBatch("player.png", capacity=10_000)
batch.spawn(1000, x=450, y=300)

while not win.has_exit:
    win.switch_to()
    win.dispatch_events()
    ext.clear(0.1, 0.1, 0.1)
    batch.draw()      # objetos do FastObjects
    win.flip()
```

Veja [`examples/pyglet_interop.py`](https://github.com/Enzo-Azevedo/FastObjects/blob/main/examples/pyglet_interop.py)
(coelhos quicando + um HUD nativo `pyglet.text.Label`).

**arcade** — desenhe os batches do FastObjects dentro do `on_draw`; o desenho
nativo do arcade (`arcade.Text`, formas) convive ao lado deles:

```python
import arcade
import fastobjects as fo

class Demo(arcade.Window):
    def __init__(self):
        super().__init__(900, 600, "fastobjects + arcade")
        self.ext = fo.attach(view_size=(900, 600))
        self.batch = fo.SpriteBatch("player.png", capacity=10_000)
        self.batch.spawn(1000, x=450, y=300)

    def on_draw(self):
        self.clear()
        self.batch.draw()   # objetos do FastObjects

Demo()
arcade.run()
```

Veja [`examples/arcade_interop.py`](https://github.com/Enzo-Azevedo/FastObjects/blob/main/examples/arcade_interop.py).

!!! warning "raylib não é suportado"
    O `attach` conecta ao contexto GL do raylib (um `clear` funciona), mas o
    draw instanciado do FastObjects não produz saída: a camada `rlgl` do
    raylib é dona do estado GL (pilha de matrizes, shader, VAO e sistema de
    batch próprios), e um segundo pipeline de renderização no mesmo contexto
    não renderiza. Reconciliar os dois exigiria patchar internals do raylib,
    o que está fora de escopo. Use pygame, pyglet ou arcade como host.
