"""Gera o sprite do coelho usado por todos os benchmarks (determinístico)."""

from pathlib import Path

import pygame

OUT = Path(__file__).parent / "assets" / "bunny.png"


def main() -> None:
    pygame.init()
    surf = pygame.Surface((26, 37), pygame.SRCALPHA)
    white = (255, 255, 255, 255)
    pygame.draw.ellipse(surf, white, (3, 12, 20, 24))   # corpo
    pygame.draw.ellipse(surf, white, (6, 0, 6, 16))     # orelha esq
    pygame.draw.ellipse(surf, white, (14, 0, 6, 16))    # orelha dir
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surf, str(OUT))
    print(f"gerado: {OUT}")


if __name__ == "__main__":
    main()
