"""SurfaceLayer: surfaces desenhadas por CPU (ex.: pygame) compostas pela GPU."""

from __future__ import annotations

import moderngl
import numpy as np

from fastobjects import _context
from fastobjects.core.renderer import SpriteRenderer


class SurfaceLayer:
    """Compõe uma pygame.Surface (desenho clássico por CPU) na cena.

    A surface é desenhada como um quad texturizado em (0, 0) cobrindo o seu
    próprio tamanho, com o mesmo blending dos sprites. Fluxo por frame:
    desenhe na surface com a API do pygame, chame update() (1 upload) e
    draw() (1 draw call) na ordem de composição desejada.

    Args:
        surface: pygame.Surface (tamanho fixo na criação).
        ctx: contexto moderngl; se None, usa o da janela atual.
        view_size: (largura, altura) do alvo de render em pixels;
            se None, usa o tamanho da janela atual.
    """

    def __init__(
        self,
        surface,
        *,
        ctx: moderngl.Context | None = None,
        view_size: tuple[int, int] | None = None,
    ) -> None:
        ctx, view_size = _context.resolve(ctx, view_size)
        self._surface = surface
        w, h = surface.get_size()
        if w <= 0 or h <= 0:
            raise ValueError(
                f"Surface de tamanho inválido {surface.get_size()} — use uma "
                "surface com largura e altura > 0."
            )
        self._size = (int(w), int(h))
        self._texture = ctx.texture(self._size, 4)
        self._renderer = SpriteRenderer(ctx, self._texture, 1, view_size)
        self._cols = {
            "pos": np.array([[w / 2.0, h / 2.0]], dtype="f4"),
            "size": np.array([[float(w), float(h)]], dtype="f4"),
            "rot": np.zeros(1, dtype="f4"),
            "color": np.ones((1, 4), dtype="f4"),
            "uv": np.array([[0.0, 0.0, 1.0, 1.0]], dtype="f4"),
        }
        self._dirty = {"size", "rot", "color", "uv"}  # 1º draw sobe tudo; depois só pos

    def update(self) -> None:
        """Sobe o conteúdo atual da surface para a GPU (1 upload).

        Raises:
            ImportError: se o pygame não estiver instalado.
            ValueError: se a surface tiver mudado de tamanho.
        """
        try:
            import pygame
        except ImportError as exc:
            raise ImportError(
                "SurfaceLayer precisa do pygame para ler a surface — "
                "instale com: pip install pygame-ce"
            ) from exc
        if self._surface.get_size() != self._size:
            raise ValueError(
                f"A surface mudou de tamanho: era {self._size}, agora "
                f"{self._surface.get_size()}. Crie um novo SurfaceLayer."
            )
        self._texture.write(pygame.image.tobytes(self._surface, "RGBA"))

    def draw(self) -> None:
        """Desenha a surface na tela (1 draw call)."""
        self._renderer.render(self._cols, 1, self._dirty)
        self._dirty = set()
