"""SpriteGroup: fatia de um batch com views NumPy que escrevem no array base."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from fastobjects._batchcore import BatchCore


class SpriteGroup:
    """Grupo de sprites contíguos de um batch. Um objeto por grupo, nunca por sprite.

    As propriedades são views do array do batch: operações in-place
    (`group.y += v`) escrevem direto no estado, sem cópia. Funciona para
    qualquer batch cujo `data` tenha as colunas 0-8 no layout
    x, y, w, h, rot, r, g, b, a (SpriteBatch e ShapeBatch).

    Após `batch.despawn(grupo)` ou `batch.clear()`, o handle fica inválido:
    qualquer acesso levanta RuntimeError.

    Args:
        batch: dono do array `data` (um BatchCore).
        s: slice absoluto das linhas deste grupo em `batch.data`.
    """

    def __init__(self, batch: BatchCore, s: slice) -> None:
        self._batch = batch
        self._slice = s
        self._alive = True

    def _check_alive(self) -> None:
        if not self._alive:
            raise RuntimeError(
                "Grupo removido do batch (despawn/clear) — handles removidos "
                "não são reutilizáveis; use spawn() para criar novos objetos."
            )

    @property
    def slice(self) -> slice:
        """Slice absoluto das linhas deste grupo no array do batch."""
        self._check_alive()
        return self._slice

    def __len__(self) -> int:
        self._check_alive()
        return self._slice.stop - self._slice.start

    def __getitem__(self, sub: slice) -> SpriteGroup:
        self._check_alive()
        if not isinstance(sub, slice):
            raise TypeError(
                "SpriteGroup aceita apenas slices (grupo[a:b]); não há handle "
                "individual — para um sprite use grupo[i:i+1]."
            )
        start, stop, step = sub.indices(len(self))
        if step != 1:
            raise ValueError("SpriteGroup não suporta step em slices (use passo 1).")
        base = self._slice.start
        group = SpriteGroup(self._batch, slice(base + start, base + stop))
        self._batch._register(group)
        return group

    # --- colunas escalares -------------------------------------------------

    @property
    def x(self) -> np.ndarray:
        self._check_alive()
        return self._batch.data[self._slice, 0]

    @x.setter
    def x(self, value) -> None:
        self._check_alive()
        self._batch.data[self._slice, 0] = value

    @property
    def y(self) -> np.ndarray:
        self._check_alive()
        return self._batch.data[self._slice, 1]

    @y.setter
    def y(self, value) -> None:
        self._check_alive()
        self._batch.data[self._slice, 1] = value

    @property
    def w(self) -> np.ndarray:
        self._check_alive()
        return self._batch.data[self._slice, 2]

    @w.setter
    def w(self, value) -> None:
        self._check_alive()
        self._batch.data[self._slice, 2] = value

    @property
    def h(self) -> np.ndarray:
        self._check_alive()
        return self._batch.data[self._slice, 3]

    @h.setter
    def h(self, value) -> None:
        self._check_alive()
        self._batch.data[self._slice, 3] = value

    @property
    def rot(self) -> np.ndarray:
        self._check_alive()
        return self._batch.data[self._slice, 4]

    @rot.setter
    def rot(self, value) -> None:
        self._check_alive()
        self._batch.data[self._slice, 4] = value

    # --- blocos ------------------------------------------------------------

    @property
    def pos(self) -> np.ndarray:
        self._check_alive()
        return self._batch.data[self._slice, 0:2]

    @pos.setter
    def pos(self, value) -> None:
        self._check_alive()
        self._batch.data[self._slice, 0:2] = value

    @property
    def size(self) -> np.ndarray:
        self._check_alive()
        return self._batch.data[self._slice, 2:4]

    @size.setter
    def size(self, value) -> None:
        self._check_alive()
        self._batch.data[self._slice, 2:4] = value

    @property
    def color(self) -> np.ndarray:
        self._check_alive()
        return self._batch.data[self._slice, 5:9]

    @color.setter
    def color(self, value) -> None:
        self._check_alive()
        self._batch.data[self._slice, 5:9] = value
