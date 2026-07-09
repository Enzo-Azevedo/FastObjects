"""SpriteBatch: sprites de um texture atlas, estado em colunas NumPy."""

from __future__ import annotations

from pathlib import Path

import moderngl
import numpy as np
from PIL import Image

from fastobjects import _context
from fastobjects._batchcore import BatchCore
from fastobjects.atlas import Atlas
from fastobjects.core.renderer import SpriteRenderer
from fastobjects.group import SpriteGroup


def _normalize_images(images):
    """Retorna (paths: list[str], names: dict[str, int] | None)."""
    if isinstance(images, str):
        return [images], None
    if isinstance(images, dict):
        keys = list(images.keys())
        return [images[k] for k in keys], {k: i for i, k in enumerate(keys)}
    return list(images), None


class SpriteBatch(BatchCore):
    """Lote de sprites desenhado em um draw call, de um ou vários assets (atlas).

    As imagens são empacotadas numa única textura na criação; cada sprite
    guarda o retângulo UV da sua sub-imagem. `spawn(image=i)` e `group.image = i`
    escolhem a imagem (índice inteiro, ou nome se `images` for um dict). Com uma
    única imagem, o comportamento é o de sempre (a sub-imagem cobre a textura).

    Args:
        images: caminho (str), lista de caminhos (índice por posição) ou dict
            nome->caminho.
        capacity: número máximo de sprites do lote.
        ctx: contexto moderngl; se None, usa o da janela atual.
        view_size: (largura, altura) do alvo de render; se None, usa a janela.
    """

    def __init__(
        self,
        images: str | list[str] | dict[str, str],
        capacity: int,
        *,
        ctx: moderngl.Context | None = None,
        view_size: tuple[int, int] | None = None,
    ) -> None:
        super().__init__(capacity, "sprites", uv=True)
        ctx, view_size = _context.resolve(ctx, view_size)
        paths, names = _normalize_images(images)
        pil = []
        for p in paths:
            path = Path(p)
            if not path.is_file():
                raise FileNotFoundError(
                    f"Textura não encontrada: {path.resolve()} — verifique o "
                    "caminho (relativo ao diretório de execução) ou use absoluto."
                )
            pil.append(Image.open(path).convert("RGBA"))
        atlas = Atlas(pil, max_size=ctx.info["GL_MAX_TEXTURE_SIZE"])
        self._uvs = atlas.uvs
        self._img_sizes = atlas.sizes
        self._names = names
        texture = ctx.texture(atlas.size, 4, data=atlas.pixels)
        self._renderer = SpriteRenderer(ctx, texture, capacity, view_size)

    def _resolve_image(self, image):
        """Escalar/array, int/str -> índice(s) inteiro(s) validado(s)."""
        if isinstance(image, str):
            if not self._names or image not in self._names:
                disponiveis = list(self._names) if self._names else "(nenhum nome)"
                raise ValueError(
                    f"Imagem '{image}' não existe — disponíveis: {disponiveis}."
                )
            return self._names[image]
        idx = np.asarray(image)
        n = len(self._uvs)
        if idx.min() < 0 or idx.max() >= n:
            raise ValueError(f"image={image} fora de faixa: use índices 0..{n - 1}.")
        return image

    def spawn(
        self,
        n: int,
        x: float | np.ndarray = 0.0,
        y: float | np.ndarray = 0.0,
        w: float | np.ndarray | None = None,
        h: float | np.ndarray | None = None,
        rot: float | np.ndarray = 0.0,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
        image: int | str | np.ndarray = 0,
    ) -> SpriteGroup:
        """Adiciona n sprites. Escalares ou arrays de tamanho n; `image` escolhe
        a sub-imagem (índice ou nome; `w`/`h` None usam o tamanho dela).

        Raises:
            ValueError: se n for negativo ou `image` for inválido.
            CapacityError: se n não couber; a mensagem diz a capacity necessária.
        """
        s = self._alloc(n, "spawn")
        idx = self._resolve_image(image)
        cols = self._cols
        cols["pos"][s, 0] = x
        cols["pos"][s, 1] = y
        cols["size"][s, 0] = self._img_sizes[idx, 0] if w is None else w
        cols["size"][s, 1] = self._img_sizes[idx, 1] if h is None else h
        cols["rot"][s] = rot
        cols["color"][s] = color
        cols["uv"][s] = self._uvs[idx]
        return self._make_group(s)

    def set_group_image(self, s: slice, image) -> None:
        """Re-textura as linhas do slice para a imagem dada (usado por group.image)."""
        idx = self._resolve_image(image)
        self._cols["uv"][s] = self._uvs[idx]
        self._dirty.add("uv")
