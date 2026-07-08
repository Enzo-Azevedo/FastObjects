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
