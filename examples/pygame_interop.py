"""FastObjects + pygame: janela/loop/eventos do pygame, objetos do fastobjects.

Requisitos: pygame-ce instalado (já vem com `pip install -e .[bench]` neste
repositório, ou `pip install pygame-ce`). Rode da raiz do repositório:

    .venv\\Scripts\\python examples/pygame_interop.py               # interativo
    .venv\\Scripts\\python examples/pygame_interop.py --frames 120  # auto-teste

Controles: clique esquerdo spawna 100 coelhos no cursor; D remove o último
grupo spawnado; ESC sai. O HUD (texto e círculo no cursor) é desenhado com a
API clássica do pygame numa Surface, composta na GPU pelo SurfaceLayer.
"""

import argparse
from pathlib import Path

import numpy as np
import pygame

import fastobjects as fo

WIDTH, HEIGHT = 1280, 720
BUNNY = Path(__file__).resolve().parent.parent / "benchmarks" / "arena" / "assets" / "bunny.png"
GRAVITY = 980.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--frames", type=int, default=0, help="roda N frames e sai (auto-teste)"
    )
    args = parser.parse_args()

    pygame.init()
    pygame.display.set_mode((WIDTH, HEIGHT), pygame.OPENGL | pygame.DOUBLEBUF)
    pygame.display.set_caption("fastobjects + pygame")

    ext = fo.attach(view_size=(WIDTH, HEIGHT))

    batch = fo.SpriteBatch(str(BUNNY), capacity=200_000)
    shapes = fo.ShapeBatch(capacity=64)
    shapes.lines(
        1, x1=0.0, y1=HEIGHT - 2.0, x2=float(WIDTH), y2=HEIGHT - 2.0,
        width=3.0, color=(0.2, 0.9, 0.2, 1.0),
    )

    hud_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    hud = fo.SurfaceLayer(hud_surface)
    font = pygame.font.Font(None, 28)

    rng = np.random.default_rng(42)
    groups: list[fo.SpriteGroup] = []
    velocities: list[np.ndarray] = []

    def spawn_at(x: float, y: float) -> None:
        n = 100
        groups.append(batch.spawn(n, x=x, y=y))
        v = np.empty((n, 2), dtype=np.float32)
        v[:, 0] = rng.uniform(-200, 200, n)
        v[:, 1] = rng.uniform(-300, 0, n)
        velocities.append(v)

    def despawn_last() -> None:
        if groups:
            batch.despawn(groups.pop())
            velocities.pop()

    spawn_at(WIDTH / 2, HEIGHT / 3)

    clock = pygame.time.Clock()
    frame = 0
    running = True
    while running:
        dt = min(clock.tick() / 1000.0, 1.0 / 30.0)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_d:
                    despawn_last()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                spawn_at(float(event.pos[0]), float(event.pos[1]))

        # física vetorizada direto nas views dos grupos (loop por GRUPO, não por sprite)
        for g, v in zip(groups, velocities):
            v[:, 1] += GRAVITY * dt
            g.pos += v * dt
            hit_floor = g.y > HEIGHT
            v[hit_floor, 1] *= -0.85
            g.y = np.minimum(g.y, HEIGHT)

        # HUD com a API clássica do pygame
        hud_surface.fill((0, 0, 0, 0))
        text = font.render(
            f"sprites: {batch.count}  |  clique: +100  |  D: remove grupo  |  ESC: sai",
            True,
            (255, 255, 255),
        )
        hud_surface.blit(text, (10, 10))
        mx, my = pygame.mouse.get_pos()
        pygame.draw.circle(hud_surface, (255, 200, 0), (mx, my), 12, width=2)

        # render fastobjects + composição, flip do pygame
        ext.clear(0.08, 0.08, 0.10)
        batch.draw()
        shapes.draw()
        hud.update()
        hud.draw()
        pygame.display.flip()

        frame += 1
        if args.frames:
            if frame == args.frames // 2:
                spawn_at(WIDTH / 4, HEIGHT / 4)  # exercita spawn no modo auto
            if frame == args.frames // 2 + 10:
                despawn_last()  # e despawn
            if frame >= args.frames:
                running = False

    count = batch.count
    ext.close()
    pygame.quit()
    print(f"interop ok: {frame} frames, {count} sprites")


if __name__ == "__main__":
    main()
