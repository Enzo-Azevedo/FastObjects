# Using inside pygame

FastObjects can render **inside a window created by another library**. The
host (pygame here) owns the window, the event loop, input, and sound;
FastObjects owns object insertion, update, removal, and rendering. Classic
pygame drawing composites on top.

## The one requirement: an OpenGL window

pygame must create its window with an OpenGL context — that is the only
change to a normal pygame setup:

```python
import pygame
import fastobjects as fo

pygame.init()
pygame.display.set_mode((1280, 720), pygame.OPENGL | pygame.DOUBLEBUF)
ext = fo.attach(view_size=(1280, 720))
```

`fo.attach()` connects FastObjects to the host's current OpenGL context and
registers it as the current window, so batches created afterwards work
exactly as in native mode. Call it **once per window**. If there is no GL
context, it raises a `RuntimeError` telling you to add the `OPENGL` flag.

## Who owns what

| Concern | Owner |
|---|---|
| Window, event loop, `flip()` | pygame |
| Keyboard, mouse, sound | pygame |
| Sprite/shape state, update, render | FastObjects |
| Classic 2D drawing (`pygame.draw`, `pygame.font`) | pygame → composited via `SurfaceLayer` |

`ExternalWindow` (returned by `attach`) intentionally exposes only `.ctx`,
`.width`, `.height`, `.clear(r, g, b)`, and `.close()` — no frame loop, no
input, because those belong to the host.

## Compositing pygame drawing: SurfaceLayer

Draw your HUD, text, or vector art onto a normal `pygame.Surface`, then
composite it on the GPU alongside the batches:

```python
hud_surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
hud = fo.SurfaceLayer(hud_surface)
font = pygame.font.Font(None, 28)

# each frame:
hud_surface.fill((0, 0, 0, 0))
hud_surface.blit(font.render("score: 42", True, (255, 255, 255)), (10, 10))
hud.update()   # upload the surface to the GPU (one upload)
hud.draw()     # composite it (one draw call)
```

`update()` needs pygame installed (it is imported lazily, so pygame never
becomes a dependency of FastObjects itself).

## Complete loop

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
            batch.despawn(groups.pop())   # real removal, frees capacity

    hud_surface.fill((0, 0, 0, 0))
    hud_surface.blit(font.render(f"sprites: {batch.count}", True, (255, 255, 255)), (10, 10))

    ext.clear(0.08, 0.08, 0.10)
    batch.draw()
    hud.update()
    hud.draw()
    pygame.display.flip()

pygame.quit()
```

The full runnable version is
[`examples/pygame_interop.py`](https://github.com/Enzo-Azevedo/FastObjects/blob/main/examples/pygame_interop.py).

!!! info "Why not blit FastObjects over classic pygame?"
    An OpenGL window takes over presentation — SDL's software surface no
    longer reaches the screen (this is true of any GPU API, Vulkan
    included). So the composition goes the other way: pygame draws onto a
    Surface and FastObjects composites it. You keep every pygame drawing
    tool; you just present through OpenGL.
