"""SpriteGroup: fatia de um batch com views NumPy que escrevem nas colunas SoA."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from fastobjects._batchcore import BatchCore


class SpriteGroup:
    """Grupo de sprites contíguos de um batch. Um objeto por grupo, nunca por sprite.

    As propriedades são views das colunas SoA do batch: operações in-place
    (`group.y += v`) escrevem direto no estado, sem cópia. Acessar uma
    propriedade fria (w/h/size/rot/color) marca a coluna para upload no
    próximo draw — por isso, não guarde uma view entre frames para escrever
    nela depois: reacesse a propriedade a cada frame (é O(1)).

    Após `batch.despawn(grupo)` ou `batch.clear()`, o handle fica inválido:
    qualquer acesso levanta RuntimeError.

    Args:
        batch: dono das colunas (um BatchCore).
        s: slice absoluto das linhas deste grupo nas colunas do batch.
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
        """Slice absoluto das linhas deste grupo nas colunas do batch."""
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
        return self._batch._cols["pos"][self._slice, 0]

    @x.setter
    def x(self, value) -> None:
        self._check_alive()
        self._batch._cols["pos"][self._slice, 0] = value

    @property
    def y(self) -> np.ndarray:
        self._check_alive()
        return self._batch._cols["pos"][self._slice, 1]

    @y.setter
    def y(self, value) -> None:
        self._check_alive()
        self._batch._cols["pos"][self._slice, 1] = value

    @property
    def w(self) -> np.ndarray:
        self._check_alive()
        self._batch._dirty.add("size")
        return self._batch._cols["size"][self._slice, 0]

    @w.setter
    def w(self, value) -> None:
        self._check_alive()
        self._batch._dirty.add("size")
        self._batch._cols["size"][self._slice, 0] = value

    @property
    def h(self) -> np.ndarray:
        self._check_alive()
        self._batch._dirty.add("size")
        return self._batch._cols["size"][self._slice, 1]

    @h.setter
    def h(self, value) -> None:
        self._check_alive()
        self._batch._dirty.add("size")
        self._batch._cols["size"][self._slice, 1] = value

    @property
    def rot(self) -> np.ndarray:
        self._check_alive()
        self._batch._dirty.add("rot")
        return self._batch._cols["rot"][self._slice]

    @rot.setter
    def rot(self, value) -> None:
        self._check_alive()
        self._batch._dirty.add("rot")
        self._batch._cols["rot"][self._slice] = value

    # --- blocos ------------------------------------------------------------

    @property
    def pos(self) -> np.ndarray:
        self._check_alive()
        return self._batch._cols["pos"][self._slice]

    @pos.setter
    def pos(self, value) -> None:
        self._check_alive()
        self._batch._cols["pos"][self._slice] = value

    @property
    def size(self) -> np.ndarray:
        self._check_alive()
        self._batch._dirty.add("size")
        return self._batch._cols["size"][self._slice]

    @size.setter
    def size(self, value) -> None:
        self._check_alive()
        self._batch._dirty.add("size")
        self._batch._cols["size"][self._slice] = value

    @property
    def color(self) -> np.ndarray:
        self._check_alive()
        self._batch._dirty.add("color")
        return self._batch._cols["color"][self._slice]

    @color.setter
    def color(self, value) -> None:
        self._check_alive()
        self._batch._dirty.add("color")
        self._batch._cols["color"][self._slice] = value
