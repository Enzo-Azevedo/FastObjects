"""Base interna dos batches: colunas SoA, registro de grupos, despawn e dirty."""

from __future__ import annotations

import weakref

import numpy as np

from fastobjects.errors import CapacityError
from fastobjects.group import SpriteGroup


class BatchCore:
    """Estado e ciclo de vida comuns a SpriteBatch e ShapeBatch.

    O estado vive em colunas SoA separadas (`_cols`: pos (cap, 2),
    size (cap, 2), rot (cap,), color (cap, 4) — e kind (cap,) nos shapes),
    todas float32 na CPU. Por frame, o draw sobe as posições sempre e as
    demais colunas apenas quando tocadas desde o último draw (dirty tracking
    conservador): você paga pela mudança, não pela existência. Layout
    decidido por benchmark — ver "Lab 2026-07-07: layout SoA" no RESULTS.md.

    Caveat de uso: não guarde uma view de propriedade entre frames para
    escrever nela depois — reacesse (`grupo.color`, `batch.rot`, ...) a cada
    frame; o acesso é O(1) e é ele que marca a coluna para upload.

    Args:
        capacity: número máximo de linhas do lote.
        unit: nome plural dos objetos nas mensagens de erro ("sprites"/"formas").
        kind: se True, adiciona a coluna `kind` (usada pelo ShapeBatch).
        uv: se True, adiciona a coluna `uv` (usada pelo SpriteBatch/atlas).
    """

    def __init__(
        self, capacity: int, unit: str, *, kind: bool = False, uv: bool = False
    ) -> None:
        if capacity <= 0:
            raise ValueError(
                f"capacity={capacity} inválida: use um valor > 0 "
                f"(quantidade máxima de {unit} do lote)."
            )
        self.capacity = capacity
        self.count = 0
        self._cols: dict[str, np.ndarray] = {
            "pos": np.zeros((capacity, 2), dtype="f4"),
            "size": np.zeros((capacity, 2), dtype="f4"),
            "rot": np.zeros(capacity, dtype="f4"),
            "color": np.zeros((capacity, 4), dtype="f4"),
        }
        if kind:
            self._cols["kind"] = np.zeros(capacity, dtype="f4")
        if uv:
            self._cols["uv"] = np.zeros((capacity, 4), dtype="f4")
        self._dirty: set[str] = set()
        self._groups: weakref.WeakSet[SpriteGroup] = weakref.WeakSet()

    # --- acesso público às colunas (capacity inteira) -----------------------

    @property
    def pos(self) -> np.ndarray:
        """Posições (capacity, 2) — view f4; sobe para a GPU todo frame."""
        return self._cols["pos"]

    @property
    def size(self) -> np.ndarray:
        """Tamanhos (capacity, 2) — acessar marca a coluna para upload."""
        self._dirty.add("size")
        return self._cols["size"]

    @property
    def rot(self) -> np.ndarray:
        """Rotações (capacity,) — acessar marca a coluna para upload."""
        self._dirty.add("rot")
        return self._cols["rot"]

    @property
    def color(self) -> np.ndarray:
        """Cores RGBA (capacity, 4) — acessar marca a coluna para upload."""
        self._dirty.add("color")
        return self._cols["color"]

    # --- ciclo de vida -------------------------------------------------------

    def _mark_all(self) -> None:
        """Marca todas as colunas frias para upload no próximo draw."""
        self._dirty.update(name for name in self._cols if name != "pos")

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
        self._mark_all()
        return s

    def _register(self, group: SpriteGroup) -> None:
        self._groups.add(group)

    def _make_group(self, s: slice) -> SpriteGroup:
        group = SpriteGroup(self, s)
        self._register(group)
        return group

    def despawn(self, group: SpriteGroup) -> None:
        """Remove as linhas do grupo, compactando (uma cópia vetorizada por coluna).

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
            new_count = self.count - n
            for arr in self._cols.values():
                arr[start:new_count] = arr[stop : self.count]
            self.count = new_count
            self._mark_all()
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
        self._mark_all()
        for group in list(self._groups):
            group._alive = False
        self._groups.clear()

    def draw(self) -> None:
        """Sobe posições + colunas tocadas e desenha o lote em um draw call."""
        self._renderer.render(self._cols, self.count, self._dirty)
        self._dirty.clear()
