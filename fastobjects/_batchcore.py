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

    def despawn(self, group: SpriteGroup) -> None:
        """Remove as linhas do grupo, compactando o array (1 cópia vetorizada).

        Os demais grupos vivos são realocados automaticamente: grupos
        posteriores deslocam para a esquerda; um grupo que contém o trecho
        removido (pai de sub-grupo) encolhe. O grupo removido — e sub-grupos
        contidos nele — ficam inválidos. Sub-grupos que se sobrepõem
        parcialmente ao trecho removido também são invalidados.

        Raises:
            ValueError: se o grupo pertence a outro batch.
            RuntimeError: se o grupo já foi removido.
        """
        if group._batch is not self:
            raise ValueError(
                "despawn: o grupo pertence a outro batch — chame despawn "
                "no batch que o criou."
            )
        group._check_alive()
        start, stop = group._slice.start, group._slice.stop
        n = stop - start
        if n:
            self.data[start : self.count - n] = self.data[stop : self.count]
            self.count -= n
        for g in list(self._groups):
            gs, ge = g._slice.start, g._slice.stop
            if g is group or (gs >= start and ge <= stop):
                g._alive = False
                self._groups.discard(g)
            elif gs >= stop:
                g._slice = slice(gs - n, ge - n)
            elif gs <= start and ge >= stop:
                g._slice = slice(gs, ge - n)
            elif gs < stop and ge > start:
                # sobreposição parcial não-aninhada (irmãos de sub-slice):
                # realocação segura é impossível — invalida conservadoramente.
                g._alive = False
                self._groups.discard(g)
            # senão: termina antes do trecho removido — intacto.

    def clear(self) -> None:
        """Remove todos os objetos e invalida todos os handles de grupos."""
        self.count = 0
        for group in list(self._groups):
            group._alive = False
        self._groups.clear()

    def draw(self) -> None:
        """Sobe o estado atual e desenha o lote inteiro em um draw call."""
        self._renderer.render(self.data, self.count)
