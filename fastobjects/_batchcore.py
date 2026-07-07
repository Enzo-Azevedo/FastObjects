"""Base interna dos batches: alocação, registro de grupos, despawn e clear."""

from __future__ import annotations

import weakref

import numpy as np

from fastobjects.errors import CapacityError
from fastobjects.group import SpriteGroup


class BatchCore:
    """Estado e ciclo de vida comuns a SpriteBatch e ShapeBatch.

    Mantém o array `data`, o contador `count` e um registro (weakrefs) dos
    grupos vivos — tocado apenas em spawn/despawn/clear, nunca no caminho
    quente de draw. Subclasses definem `_renderer` no próprio __init__.

    Args:
        capacity: número máximo de linhas do lote.
        floats: colunas de `data` (9 para sprites, 10 para formas).
        unit: nome plural dos objetos nas mensagens de erro ("sprites"/"formas").
    """

    def __init__(self, capacity: int, floats: int, unit: str) -> None:
        if capacity <= 0:
            raise ValueError(
                f"capacity={capacity} inválida: use um valor > 0 "
                f"(quantidade máxima de {unit} do lote)."
            )
        self.capacity = capacity
        self.count = 0
        self.data = np.zeros((capacity, floats), dtype="f4")
        self._groups: weakref.WeakSet[SpriteGroup] = weakref.WeakSet()

    def _alloc(self, n: int, method: str) -> slice:
        """Reserva n linhas contíguas; mensagens acionáveis."""
        if n < 0:
            raise ValueError(f"{method}({n}): n não pode ser negativo. Use n >= 0.")
        if self.count + n > self.capacity:
            raise CapacityError(
                f"{method}({n}) excede a capacidade: {self.count} usados de "
                f"{self.capacity}. Crie o batch com capacity={self.count + n} ou mais."
            )
        s = slice(self.count, self.count + n)
        self.count += n
        return s

    def _register(self, group: SpriteGroup) -> None:
        self._groups.add(group)

    def _make_group(self, s: slice) -> SpriteGroup:
        group = SpriteGroup(self, s)
        self._register(group)
        return group

    def clear(self) -> None:
        """Remove todos os objetos e invalida todos os handles de grupos."""
        self.count = 0
        for group in list(self._groups):
            group._alive = False
        self._groups.clear()

    def draw(self) -> None:
        """Sobe o estado atual e desenha o lote inteiro em um draw call."""
        self._renderer.render(self.data, self.count)
